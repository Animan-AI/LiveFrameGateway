from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from aiohttp import web

from .primer import HttpPrimer
from .store import FrameRingBufferStore, PrimerCallable

FRAME_STORE_KEY = web.AppKey("frame_store", FrameRingBufferStore)


def _resolve_ec_cache_path(root_path: str, record: dict[str, Any]) -> Path | None:
    root_text = str(root_path or "").strip()
    if not root_text:
        return None
    root = Path(root_text).expanduser().resolve()
    names = []
    session_id = str(record.get("session_id") or "").strip()
    frame_uuid = str(record.get("frame_uuid") or "").strip()
    frame_id = str(record.get("frame_id") or "").strip()
    if session_id and frame_uuid:
        names.append(f"{session_id}::{frame_uuid}")
    if frame_id:
        names.append(frame_id)
    if frame_uuid:
        names.append(frame_uuid)
    for name in names:
        candidate = (root / name).resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            continue
        if candidate.exists():
            return candidate
    return None


def _build_ec_cache_cleanup(root_path: str):
    def cleanup(record: dict[str, Any]) -> None:
        target = _resolve_ec_cache_path(root_path, record)
        if target is None or not target.exists():
            return
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()

    return cleanup


def create_app(
    *,
    store: FrameRingBufferStore | None = None,
    ring_size: int = 20,
    stale_session_ttl_s: float = 900.0,
    ec_shared_storage_path: str = "",
    primer: PrimerCallable | None = None,
    primer_url: str = "",
    primer_timeout_s: float = 5.0,
) -> web.Application:
    app = web.Application()

    async def startup(app_: web.Application) -> None:
        effective_primer = primer
        if effective_primer is None and primer_url:
            effective_primer = HttpPrimer(primer_url, timeout_s=primer_timeout_s)
        app_[FRAME_STORE_KEY] = store or FrameRingBufferStore(
            ring_size=ring_size,
            primer=effective_primer,
            stale_session_ttl_s=stale_session_ttl_s,
            on_evict=_build_ec_cache_cleanup(ec_shared_storage_path) if ec_shared_storage_path else None,
        )

    async def health(_request: web.Request) -> web.Response:
        return web.json_response({"status": "ok"})

    async def ingest(request: web.Request) -> web.Response:
        session_id = str(request.match_info.get("session_id") or "").strip()
        try:
            payload = await request.json()
            if not isinstance(payload, dict):
                payload = {}
            record = await request.app[FRAME_STORE_KEY].ingest(session_id, payload)
        except ValueError as exc:
            return web.json_response({"error": str(exc)}, status=400)
        except Exception as exc:
            return web.json_response({"error": str(exc), "status": "failed"}, status=502)
        return web.json_response({"status": record.get("status", "ready"), "frame": record})

    async def latest(request: web.Request) -> web.Response:
        session_id = str(request.match_info.get("session_id") or "").strip()
        try:
            limit = max(1, int(request.query.get("limit", "1")))
        except (TypeError, ValueError):
            limit = 1
        status = str(request.query.get("status", "ready") or "ready").strip()
        frames = await request.app[FRAME_STORE_KEY].get_latest_frames(session_id, limit=limit, status=status)
        return web.json_response({"frames": frames})

    app.router.add_get("/health", health)
    app.router.add_post("/sessions/{session_id}/frames", ingest)
    app.router.add_get("/sessions/{session_id}/frames/latest", latest)
    app.on_startup.append(startup)
    return app
