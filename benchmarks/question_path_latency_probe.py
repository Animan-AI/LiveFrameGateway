from __future__ import annotations

import argparse
import asyncio
import json
import time
from typing import Any

import aiohttp

from vllm_latency_probe import (
    build_image_item,
    fetch_latest_frames,
    post_chat,
    summarize_values,
)


def _values(rows: list[dict[str, Any]], path: list[str]) -> list[float]:
    values: list[float] = []
    for row in rows:
        current: Any = row
        for key in path:
            if not isinstance(current, dict):
                current = None
                break
            current = current.get(key)
        if isinstance(current, (int, float)):
            values.append(float(current))
    return values


def _subtract(left: list[float], right: list[float]) -> list[float]:
    return [float(a) - float(b) for a, b in zip(left, right)]


def _add(values: list[float], delta: float | None) -> list[float]:
    if delta is None:
        return []
    return [float(item) + float(delta) for item in values]


def summarize_question_path_rows(
    rows: list[dict[str, Any]],
    *,
    capture_upload_ms: float | None,
    note: str,
    mode: str = "question_path_probe",
) -> dict[str, Any]:
    traditional_ttft = _values(rows, ["traditional", "question_to_vlm_ttft_ms"])
    traditional_total = _values(rows, ["traditional", "question_to_vlm_total_ms"])
    ready_ttft = _values(rows, ["ready", "question_to_vlm_ttft_ms"])
    ready_total = _values(rows, ["ready", "question_to_vlm_total_ms"])
    estimated_traditional_ttft = _add(traditional_ttft, capture_upload_ms)
    estimated_saved_ttft = _subtract(estimated_traditional_ttft, ready_ttft)
    server_only_saved_ttft = _subtract(traditional_ttft, ready_ttft)

    return {
        "mode": mode,
        "iterations": len(rows),
        "capture_upload_ms": None if capture_upload_ms is None else round(float(capture_upload_ms), 1),
        "capture_upload_included": capture_upload_ms is not None,
        "traditional_server_question_to_vlm_ttft_ms": summarize_values(traditional_ttft),
        "traditional_server_question_to_vlm_total_ms": summarize_values(traditional_total),
        "traditional_estimated_user_question_to_vlm_ttft_ms": summarize_values(estimated_traditional_ttft),
        "ready_question_to_vlm_ttft_ms": summarize_values(ready_ttft),
        "ready_question_to_vlm_total_ms": summarize_values(ready_total),
        "server_only_saved_to_vlm_ttft_ms": summarize_values(server_only_saved_ttft),
        "estimated_saved_to_vlm_ttft_ms": summarize_values(estimated_saved_ttft),
        "ready_frame_age_ms": summarize_values(_values(rows, ["ready", "frame_age_ms"])),
        "note": note,
    }


def _frame_age_ms(frame: dict[str, Any]) -> float | None:
    try:
        ts_ms = int(frame.get("ts_ms") or 0)
    except (TypeError, ValueError):
        return None
    if ts_ms <= 0:
        return None
    return float(max(0, int(time.time() * 1000) - ts_ms))


async def run_probe(args: argparse.Namespace) -> dict[str, Any]:
    chat_url = f"{args.consumer_base_url.rstrip('/')}/chat/completions"
    rows: list[dict[str, Any]] = []
    timeout = aiohttp.ClientTimeout(total=max(1.0, float(args.timeout_s)))
    async with aiohttp.ClientSession(timeout=timeout) as session:
        for idx in range(max(1, int(args.iterations))):
            frames, latest_fetch_ms = await fetch_latest_frames(
                session,
                gateway_base_url=args.gateway_base_url,
                session_id=args.session_id,
                limit=max(1, int(args.latest_limit)),
            )
            ready_frame = frames[-1] if frames else {}
            ready_image_url = str(ready_frame.get("image_url") or "").strip()
            ready_frame_uuid = str(ready_frame.get("frame_uuid") or "").strip()
            if not ready_image_url:
                raise RuntimeError("ready-frame path requires latest frame image_url")

            traditional_frame = ready_frame
            traditional_image_url = str(args.traditional_image_url or "").strip() or ready_image_url
            traditional = await post_chat(
                session,
                chat_url=chat_url,
                model=args.model,
                image_item=build_image_item(traditional_image_url),
                prompt=args.prompt,
                stream=True,
                timeout_s=args.timeout_s,
            )
            ready = await post_chat(
                session,
                chat_url=chat_url,
                model=args.model,
                image_item=build_image_item(ready_image_url, frame_uuid=ready_frame_uuid),
                prompt=args.prompt,
                stream=True,
                timeout_s=args.timeout_s,
            )
            row = {
                "iteration": idx,
                "traditional": {
                    "server_mode": "image_upload_already_available",
                    "image_url_chars": len(traditional_image_url),
                    "question_to_vlm_ttft_ms": traditional.get("ttft_ms"),
                    "question_to_vlm_total_ms": traditional.get("total_ms"),
                    "status": traditional.get("status"),
                },
                "ready": {
                    "server_mode": "latest_ready_frame",
                    "latest_fetch_ms": round(latest_fetch_ms, 1),
                    "frame_uuid": ready_frame_uuid,
                    "frame_age_ms": _frame_age_ms(ready_frame),
                    "image_url_chars": len(ready_image_url),
                    "question_to_vlm_ttft_ms": ready.get("ttft_ms"),
                    "question_to_vlm_total_ms": ready.get("total_ms"),
                    "status": ready.get("status"),
                },
            }
            rows.append(row)
            print(json.dumps(row, ensure_ascii=False, sort_keys=True))
            if idx < int(args.iterations) - 1:
                await asyncio.sleep(max(0.0, float(args.sleep_s)))

    return summarize_question_path_rows(
        rows,
        capture_upload_ms=args.capture_upload_ms,
        note=(
            "Server-side question-path probe. The traditional server metric starts "
            "after an image is already available on the server. Pass "
            "--capture-upload-ms from a real device measurement to include camera "
            "capture, image encode, and upload in the estimated user-perceived path."
        ),
    )


def offline_demo_summary() -> dict[str, Any]:
    rows = [
        {
            "traditional": {
                "question_to_vlm_ttft_ms": 320.0,
                "question_to_vlm_total_ms": 345.0,
            },
            "ready": {
                "question_to_vlm_ttft_ms": 260.0,
                "question_to_vlm_total_ms": 280.0,
                "frame_age_ms": 180.0,
            },
        }
    ]
    return summarize_question_path_rows(
        rows,
        capture_upload_ms=450.0,
        mode="offline_demo",
        note="Offline demo summary; no network, camera, upload, model, or TTS request was made.",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Question-path latency probe for ready-frame VLM systems")
    parser.add_argument("--offline-demo", action="store_true")
    parser.add_argument("--gateway-base-url", default="http://127.0.0.1:8095")
    parser.add_argument("--consumer-base-url", default="http://127.0.0.1:8201/v1")
    parser.add_argument("--model", default="qwen36-35b-a3b-awq")
    parser.add_argument("--session-id", default="")
    parser.add_argument("--iterations", type=int, default=3)
    parser.add_argument("--latest-limit", type=int, default=1)
    parser.add_argument("--sleep-s", type=float, default=0.5)
    parser.add_argument("--timeout-s", type=float, default=180.0)
    parser.add_argument("--prompt", default="Answer with one word: ok")
    parser.add_argument(
        "--capture-upload-ms",
        type=float,
        default=None,
        help="Real device measurement for capture + image encode + upload after a question.",
    )
    parser.add_argument(
        "--traditional-image-url",
        default="",
        help="Optional data URL for the traditional path; defaults to the latest ready frame image.",
    )
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
