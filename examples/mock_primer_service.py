from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path
from typing import Any

from aiohttp import web


def sanitize_cache_name(value: str) -> str:
    cache_name = str(value or "")
    if "/" in cache_name or "\\" in cache_name:
        raise ValueError("cache name must not contain path separators")
    return cache_name


def build_cache_artifact(cache_root: Path, session_id: str, frame: dict[str, Any]) -> Path:
    frame_uuid = str(frame.get("frame_uuid") or frame.get("uuid") or "").strip()
    if not frame_uuid:
        raise ValueError("frame_uuid is required")
    safe_name = sanitize_cache_name(f"{session_id}::{frame_uuid}")
    artifact_dir = cache_root / safe_name
    artifact_dir.mkdir(parents=True, exist_ok=True)
    image_url = str(frame.get("image_url") or "")
    digest = hashlib.sha256(image_url.encode("utf-8")).hexdigest()
    payload = {
        "kind": "mock_encoder_cache",
        "session_id": session_id,
        "frame_uuid": frame_uuid,
        "ts_ms": int(frame.get("ts_ms") or 0),
        "created_at_ms": int(time.time() * 1000),
        "embedding_digest": digest,
    }
    artifact_path = artifact_dir / "encoder_cache.json"
    artifact_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return artifact_path


def create_app(cache_root: Path) -> web.Application:
    app = web.Application()
    cache_root = Path(cache_root).expanduser().resolve()

    async def health(_request: web.Request) -> web.Response:
        return web.json_response({"status": "ok"})

    async def prime(request: web.Request) -> web.Response:
        try:
            payload = await request.json()
            if not isinstance(payload, dict):
                payload = {}
            session_id = str(payload.get("session_id") or "").strip()
            frame = payload.get("frame") if isinstance(payload.get("frame"), dict) else {}
            if not session_id:
                raise ValueError("session_id is required")
            artifact_path = build_cache_artifact(cache_root, session_id, frame)
        except ValueError as exc:
            return web.json_response({"status": "failed", "error": str(exc)}, status=400)
        return web.json_response({"status": "ready", "mock_cache_path": str(artifact_path)})

    app.router.add_get("/health", health)
    app.router.add_post("/prime", prime)
    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="Mock LiveFrameGateway primer service")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=18096)
    parser.add_argument("--cache-root", default="/tmp/liveframegateway-ec")
    args = parser.parse_args()
    web.run_app(create_app(Path(args.cache_root)), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
