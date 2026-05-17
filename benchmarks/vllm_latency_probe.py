from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
from pathlib import Path
from typing import Any

import aiohttp


def build_image_item(image_url: str, *, frame_uuid: str = "") -> dict[str, Any]:
    item: dict[str, Any] = {
        "type": "image_url",
        "image_url": {"url": str(image_url or "")},
    }
    if frame_uuid:
        item["uuid"] = str(frame_uuid)
    return item


def build_uuid_only_item(frame_uuid: str) -> dict[str, Any]:
    return {
        "type": "image_url",
        "image_url": {},
        "uuid": str(frame_uuid or ""),
    }


def summarize_values(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"p50": None, "p95": None, "values": []}
    ordered = sorted(float(item) for item in values)
    p95_index = min(len(ordered) - 1, max(0, round(0.95 * (len(ordered) - 1))))
    return {
        "p50": round(float(statistics.median(ordered)), 1),
        "p95": round(float(ordered[p95_index]), 1),
        "values": [round(float(item), 1) for item in values],
    }


def _compact_http_result(result: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in result.items()
        if key in {"status", "ms", "ttfb_ms", "ttft_ms", "total_ms", "body_prefix"}
    }


async def fetch_latest_frames(
    session: aiohttp.ClientSession,
    *,
    gateway_base_url: str,
    session_id: str,
    limit: int,
) -> tuple[list[dict[str, Any]], float]:
    started = time.perf_counter()
    async with session.get(
        f"{gateway_base_url.rstrip('/')}/sessions/{session_id}/frames/latest",
        params={"limit": str(max(1, int(limit or 1))), "status": "ready"},
    ) as resp:
        payload = await resp.json()
    fetch_ms = (time.perf_counter() - started) * 1000.0
    frames = payload.get("frames", []) if isinstance(payload, dict) else []
    return [item for item in frames if isinstance(item, dict)], fetch_ms


async def post_chat(
    session: aiohttp.ClientSession,
    *,
    chat_url: str,
    model: str,
    image_item: dict[str, Any],
    prompt: str,
    stream: bool,
    timeout_s: float,
) -> dict[str, Any]:
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    image_item,
                    {"type": "text", "text": prompt},
                ],
            }
        ],
        "max_tokens": 4,
        "temperature": 0,
        "stream": bool(stream),
        "enable_thinking": False,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    started = time.perf_counter()
    if not stream:
        async with session.post(
            chat_url,
            json=payload,
            timeout=aiohttp.ClientTimeout(total=timeout_s),
        ) as resp:
            text = await resp.text()
            return {
                "status": resp.status,
                "ms": (time.perf_counter() - started) * 1000.0,
                "body_prefix": text[:220],
            }

    first_event_ms = None
    first_content_ms = None
    body_prefix: list[str] = []
    async with session.post(
        chat_url,
        json=payload,
        timeout=aiohttp.ClientTimeout(total=timeout_s),
    ) as resp:
        status = resp.status
        async for raw in resp.content:
            now = time.perf_counter()
            if first_event_ms is None:
                first_event_ms = (now - started) * 1000.0
            text = raw.decode(errors="ignore")
            if len("".join(body_prefix)) < 300:
                body_prefix.append(text)
            for line in text.splitlines():
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if not data or data == "[DONE]":
                    continue
                try:
                    chunk = json.loads(data)
                except json.JSONDecodeError:
                    continue
                delta = (chunk.get("choices") or [{}])[0].get("delta") or {}
                if delta.get("content") and first_content_ms is None:
                    first_content_ms = (now - started) * 1000.0
    return {
        "status": status,
        "ttfb_ms": first_event_ms,
        "ttft_ms": first_content_ms,
        "total_ms": (time.perf_counter() - started) * 1000.0,
        "body_prefix": "".join(body_prefix)[:220],
    }


def _frame_age_ms(frame: dict[str, Any]) -> float | None:
    try:
        ts_ms = int(frame.get("ts_ms") or 0)
    except (TypeError, ValueError):
        return None
    if ts_ms <= 0:
        return None
    return float(max(0, int(time.time() * 1000) - ts_ms))


def _ec_file_exists(cache_root: str, frame_uuid: str) -> bool | None:
    if not cache_root:
        return None
    if not frame_uuid:
        return False
    return (Path(cache_root) / frame_uuid / "encoder_cache.safetensors").exists()


def summarize_rows(rows: list[dict[str, Any]], *, mode: str, note: str) -> dict[str, Any]:
    return {
        "mode": mode,
        "iterations": len(rows),
        "direct_ttft_ms": summarize_values(
            [
                float(row["direct"]["ttft_ms"])
                for row in rows
                if isinstance(row.get("direct", {}).get("ttft_ms"), (int, float))
            ]
        ),
        "direct_total_ms": summarize_values(
            [
                float(row["direct"]["total_ms"])
                for row in rows
                if isinstance(row.get("direct", {}).get("total_ms"), (int, float))
            ]
        ),
        "image_url_plus_uuid_ttft_ms": summarize_values(
            [
                float(row["image_url_plus_uuid"]["ttft_ms"])
                for row in rows
                if isinstance(row.get("image_url_plus_uuid", {}).get("ttft_ms"), (int, float))
            ]
        ),
        "image_url_plus_uuid_total_ms": summarize_values(
            [
                float(row["image_url_plus_uuid"]["total_ms"])
                for row in rows
                if isinstance(row.get("image_url_plus_uuid", {}).get("total_ms"), (int, float))
            ]
        ),
        "uuid_only_first_statuses": [
            row.get("uuid_only_first", {}).get("status") for row in rows
        ],
        "uuid_only_after_local_cache_statuses": [
            row.get("uuid_only_after_local_cache", {}).get("status") for row in rows
        ],
        "frame_age_ms": summarize_values(
            [
                float(row["frame_age_ms"])
                for row in rows
                if isinstance(row.get("frame_age_ms"), (int, float))
            ]
        ),
        "all_ec_files_existed": all(
            row.get("ec_file_exists") is True
            for row in rows
            if row.get("ec_file_exists") is not None
        ),
        "note": note,
    }


async def run_probe(args: argparse.Namespace) -> dict[str, Any]:
    chat_url = f"{args.consumer_base_url.rstrip('/')}/chat/completions"
    rows: list[dict[str, Any]] = []
    timeout = aiohttp.ClientTimeout(total=max(1.0, float(args.timeout_s)))
    async with aiohttp.ClientSession(timeout=timeout) as session:
        for idx in range(max(1, int(args.iterations))):
            frames, fetch_ms = await fetch_latest_frames(
                session,
                gateway_base_url=args.gateway_base_url,
                session_id=args.session_id,
                limit=max(1, int(args.latest_limit)),
            )
            frame = frames[-1] if frames else {}
            frame_uuid = str(frame.get("frame_uuid") or "").strip()
            image_url = str(frame.get("image_url") or "").strip()
            if not frame_uuid or not image_url:
                raise RuntimeError("latest ready frame must include frame_uuid and image_url")

            uuid_only_first = await post_chat(
                session,
                chat_url=chat_url,
                model=args.model,
                image_item=build_uuid_only_item(frame_uuid),
                prompt=args.prompt,
                stream=False,
                timeout_s=args.timeout_s,
            )
            direct = await post_chat(
                session,
                chat_url=chat_url,
                model=args.model,
                image_item=build_image_item(image_url),
                prompt=args.prompt,
                stream=True,
                timeout_s=args.timeout_s,
            )
            image_url_plus_uuid = await post_chat(
                session,
                chat_url=chat_url,
                model=args.model,
                image_item=build_image_item(image_url, frame_uuid=frame_uuid),
                prompt=args.prompt,
                stream=True,
                timeout_s=args.timeout_s,
            )
            uuid_only_after_local_cache = await post_chat(
                session,
                chat_url=chat_url,
                model=args.model,
                image_item=build_uuid_only_item(frame_uuid),
                prompt=args.prompt,
                stream=False,
                timeout_s=args.timeout_s,
            )

            row = {
                "iteration": idx,
                "frame_uuid": frame_uuid,
                "latest_fetch_ms": round(fetch_ms, 1),
                "frame_age_ms": _frame_age_ms(frame),
                "image_url_chars": len(image_url),
                "ec_file_exists": _ec_file_exists(args.ec_cache_root, frame_uuid),
                "uuid_only_first": _compact_http_result(uuid_only_first),
                "direct": _compact_http_result(direct),
                "image_url_plus_uuid": _compact_http_result(image_url_plus_uuid),
                "uuid_only_after_local_cache": _compact_http_result(uuid_only_after_local_cache),
            }
            rows.append(row)
            print(json.dumps(row, ensure_ascii=False, sort_keys=True))
            if idx < int(args.iterations) - 1:
                await asyncio.sleep(max(0.0, float(args.sleep_s)))

    return summarize_rows(
        rows,
        mode="live_vllm_probe",
        note=(
            "Live backend probe. direct sends image bytes on the question path; "
            "image_url_plus_uuid still sends image bytes but allows backend cache keys; "
            "uuid_only_first tests whether a fresh ready frame can be consumed without "
            "sending image bytes. Interpret results for this backend only."
        ),
    )


def offline_demo_summary() -> dict[str, Any]:
    rows = [
        {
            "direct": {"ttft_ms": 300.0, "total_ms": 320.0},
            "image_url_plus_uuid": {"ttft_ms": 245.0, "total_ms": 270.0},
            "uuid_only_first": {"status": 400},
            "uuid_only_after_local_cache": {"status": 200},
            "frame_age_ms": 150.0,
            "ec_file_exists": True,
        }
    ]
    return summarize_rows(
        rows,
        mode="offline_demo",
        note="Offline demo summary; no network or model request was made.",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Live vLLM latency probe for ready-frame gateways")
    parser.add_argument("--offline-demo", action="store_true", help="Print a deterministic no-network demo summary")
    parser.add_argument("--gateway-base-url", default="http://127.0.0.1:8095")
    parser.add_argument("--consumer-base-url", default="http://127.0.0.1:8201/v1")
    parser.add_argument("--model", default="qwen36-35b-a3b-awq")
    parser.add_argument("--session-id", required=False, default="")
    parser.add_argument("--ec-cache-root", default="")
    parser.add_argument("--iterations", type=int, default=3)
    parser.add_argument("--latest-limit", type=int, default=1)
    parser.add_argument("--sleep-s", type=float, default=0.5)
    parser.add_argument("--timeout-s", type=float, default=180.0)
    parser.add_argument("--prompt", default="Answer with one word: ok")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.offline_demo:
        summary = offline_demo_summary()
    else:
        if not str(args.session_id or "").strip():
            raise SystemExit("--session-id is required unless --offline-demo is used")
        summary = asyncio.run(run_probe(args))
    print("SUMMARY " + json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
