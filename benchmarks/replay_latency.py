from __future__ import annotations

import argparse
import asyncio
import base64
import json
import time
from typing import Any

from aiohttp.test_utils import TestClient, TestServer

from liveframegateway.injection import inject_openai_messages
from liveframegateway.models import normalize_frame_payload
from liveframegateway.selection import select_frames
from liveframegateway.service import create_app


def make_frames(count: int, frame_bytes: int, fps: float, session_id: str) -> list[dict[str, Any]]:
    frame_interval_ms = int(1000.0 / max(1.0, fps))
    base_ts_ms = int(time.time() * 1000) - count * frame_interval_ms
    image_base64 = base64.b64encode(b"x" * max(1, frame_bytes)).decode("ascii")
    frames = []
    for idx in range(count):
        frames.append(
            {
                "frame_uuid": f"frame_{idx:06d}",
                "ts_ms": base_ts_ms + idx * frame_interval_ms,
                "image_base64": image_base64,
                "pose_state": {"body_yaw_deg": float(idx % 360)},
                "motion_state": {"speed": float(idx % 3) * 0.05, "angular_speed": float(idx % 5) * 0.02},
                "quality": {
                    "blur_score": float((idx * 7) % 100) / 100.0,
                    "confidence": 1.0 - float(idx % 10) / 20.0,
                },
                "robot_ext": {"scan_phase": "replay"},
            }
        )
    return frames


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((pct / 100.0) * (len(ordered) - 1)))))
    return ordered[index]


def summarize(values: list[float]) -> tuple[float, float]:
    return percentile(values, 50), percentile(values, 95)


def selected_frame_age_ms(frames: list[dict[str, Any]]) -> float:
    if not frames:
        return 0.0
    now_ms = int(time.time() * 1000)
    newest_ts = max(int(frame.get("ts_ms") or 0) for frame in frames)
    return float(max(0, now_ms - newest_ts))


def inline_prepare(
    raw_frames: list[dict[str, Any]],
    *,
    session_id: str,
    select_k: int,
    policy: str,
    user_text: str,
) -> tuple[list[dict[str, Any]], float]:
    normalized = [normalize_frame_payload(session_id, frame).to_dict() for frame in raw_frames]
    selected = select_frames(normalized, limit=select_k, policy=policy)
    messages = inject_openai_messages([], selected, user_text)
    frame_age_ms = selected_frame_age_ms(selected)
    return messages, frame_age_ms


async def gateway_prepare(
    client: TestClient,
    *,
    session_id: str,
    select_k: int,
    policy: str,
    user_text: str,
) -> tuple[list[dict[str, Any]], float, float]:
    started = time.perf_counter()
    resp = await client.get(
        f"/sessions/{session_id}/frames/select",
        params={"limit": str(select_k), "policy": policy, "status": "ready"},
    )
    fetch_ms = (time.perf_counter() - started) * 1000.0
    if resp.status != 200:
        raise RuntimeError(f"select failed with status {resp.status}")
    payload = await resp.json()
    frames = payload.get("frames", []) if isinstance(payload, dict) else []
    messages = inject_openai_messages([], frames, user_text)
    frame_age_ms = selected_frame_age_ms(frames)
    return messages, fetch_ms, frame_age_ms


async def run_benchmark(args: argparse.Namespace) -> dict[str, Any]:
    frames = make_frames(args.frames, args.frame_bytes, args.fps, args.session_id)
    app = create_app(ring_size=max(args.frames, args.select_k))
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()
    try:
        for frame in frames:
            resp = await client.post(f"/sessions/{args.session_id}/frames", json=frame)
            if resp.status != 200:
                raise RuntimeError(f"ingest failed with status {resp.status}")

        inline_ms = []
        gateway_ms = []
        gateway_fetch_ms = []
        selected_age_ms = []
        for query_idx in range(args.queries):
            user_text = f"What changed in query {query_idx}?"

            started = time.perf_counter()
            inline_prepare(
                frames,
                session_id=args.session_id,
                select_k=args.select_k,
                policy=args.policy,
                user_text=user_text,
            )
            inline_ms.append((time.perf_counter() - started) * 1000.0)

            started = time.perf_counter()
            _messages, fetch_ms, age_ms = await gateway_prepare(
                client,
                session_id=args.session_id,
                select_k=args.select_k,
                policy=args.policy,
                user_text=user_text,
            )
            gateway_ms.append((time.perf_counter() - started) * 1000.0)
            gateway_fetch_ms.append(fetch_ms)
            selected_age_ms.append(age_ms)
    finally:
        await client.close()

    inline_p50, inline_p95 = summarize(inline_ms)
    gateway_p50, gateway_p95 = summarize(gateway_ms)
    fetch_p50, fetch_p95 = summarize(gateway_fetch_ms)
    age_p50, age_p95 = summarize(selected_age_ms)
    return {
        "frames": args.frames,
        "queries": args.queries,
        "frame_bytes": args.frame_bytes,
        "fps": args.fps,
        "select_k": args.select_k,
        "policy": args.policy,
        "inline_request_prep_ms_p50": inline_p50,
        "inline_request_prep_ms_p95": inline_p95,
        "gateway_request_prep_ms_p50": gateway_p50,
        "gateway_request_prep_ms_p95": gateway_p95,
        "gateway_fetch_ms_p50": fetch_p50,
        "gateway_fetch_ms_p95": fetch_p95,
        "selected_frame_age_ms_p50": age_p50,
        "selected_frame_age_ms_p95": age_p95,
        "note": "Synthetic local request-preparation benchmark; not a model latency benchmark.",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay latency benchmark for LiveFrameGateway")
    parser.add_argument("--frames", type=int, default=120)
    parser.add_argument("--queries", type=int, default=20)
    parser.add_argument("--frame-bytes", type=int, default=4096)
    parser.add_argument("--fps", type=float, default=10.0)
    parser.add_argument("--session-id", default="bench")
    parser.add_argument("--select-k", type=int, default=3)
    parser.add_argument("--policy", default="latest", choices=["latest", "quality", "motion"])
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = asyncio.run(run_benchmark(args))
    print("LiveFrameGateway synthetic replay benchmark")
    print(
        f"frames={result['frames']} queries={result['queries']} "
        f"select_k={result['select_k']} policy={result['policy']}"
    )
    print(
        "inline request prep p50/p95: "
        f"{result['inline_request_prep_ms_p50']:.3f} / {result['inline_request_prep_ms_p95']:.3f} ms"
    )
    print(
        "gateway request prep p50/p95: "
        f"{result['gateway_request_prep_ms_p50']:.3f} / {result['gateway_request_prep_ms_p95']:.3f} ms"
    )
    print(
        "gateway fetch p50/p95: "
        f"{result['gateway_fetch_ms_p50']:.3f} / {result['gateway_fetch_ms_p95']:.3f} ms"
    )
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
