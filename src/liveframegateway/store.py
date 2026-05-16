from __future__ import annotations

import asyncio
import time
from collections import deque
from copy import deepcopy
from typing import Any, Awaitable, Callable

from .models import FrameRecord, normalize_frame_payload
from .selection import select_frames

EvictCallable = Callable[[dict[str, Any]], Awaitable[None] | None]
PrimerCallable = Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]]


class FrameRingBufferStore:
    def __init__(
        self,
        ring_size: int = 20,
        primer: PrimerCallable | None = None,
        on_evict: EvictCallable | None = None,
        stale_session_ttl_s: float = 900.0,
        prune_interval_s: float = 30.0,
        now_fn: Callable[[], float] | None = None,
    ):
        self.ring_size = max(1, int(ring_size or 20))
        self.primer = primer
        self.on_evict = on_evict
        self.stale_session_ttl_s = max(0.0, float(stale_session_ttl_s or 0.0))
        self.prune_interval_s = max(1.0, float(prune_interval_s or 1.0))
        self.now_fn = now_fn or time.monotonic
        self._sessions: dict[str, deque[FrameRecord]] = {}
        self._session_last_seen: dict[str, float] = {}
        self._last_prune_at = 0.0
        self._lock = asyncio.Lock()

    async def _handle_evict(self, record: FrameRecord | None) -> None:
        if record is None or self.on_evict is None:
            return
        result = self.on_evict(record.to_dict())
        if asyncio.iscoroutine(result):
            await result

    async def _prune_stale_sessions(self, *, now: float, keep_session_ids: set[str]) -> None:
        if self.stale_session_ttl_s <= 0:
            return
        if self._last_prune_at and now - self._last_prune_at < self.prune_interval_s:
            return
        self._last_prune_at = now

        evicted = []
        async with self._lock:
            stale = [
                session_id
                for session_id, last_seen in self._session_last_seen.items()
                if session_id not in keep_session_ids and now - last_seen > self.stale_session_ttl_s
            ]
            for session_id in stale:
                bucket = self._sessions.pop(session_id, deque())
                self._session_last_seen.pop(session_id, None)
                evicted.extend(bucket)

        for record in evicted:
            await self._handle_evict(record)

    async def ingest(self, session_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        record = normalize_frame_payload(session_id, payload)
        if self.primer is not None and record.image_url:
            primer_result = await self.primer(record.session_id, record.to_dict())
            if isinstance(primer_result, dict):
                merged = record.to_dict()
                for key, value in primer_result.items():
                    if value not in (None, ""):
                        merged[key] = deepcopy(value)
                record = normalize_frame_payload(record.session_id, merged)
                record.status = str(merged.get("status") or "ready").strip().lower() or "ready"

        now = float(self.now_fn())
        evicted_record = None
        async with self._lock:
            bucket = self._sessions.setdefault(record.session_id, deque(maxlen=self.ring_size))
            deduped_items = [item for item in bucket if item.frame_uuid != record.frame_uuid]
            if len(deduped_items) >= self.ring_size:
                evicted_record = deduped_items[0]
                deduped_items = deduped_items[-(self.ring_size - 1) :] if self.ring_size > 1 else []
            new_bucket = deque(deduped_items, maxlen=self.ring_size)
            new_bucket.append(record)
            self._sessions[record.session_id] = new_bucket
            self._session_last_seen[record.session_id] = now

        await self._handle_evict(evicted_record)
        await self._prune_stale_sessions(now=now, keep_session_ids={record.session_id})
        return record.to_dict()

    async def get_latest_frames(self, session_id: str, limit: int = 1, status: str = "ready") -> list[dict[str, Any]]:
        normalized_session_id = str(session_id or "").strip()
        if not normalized_session_id:
            return []
        normalized_status = str(status or "").strip().lower()
        async with self._lock:
            bucket = list(self._sessions.get(normalized_session_id, ()))
        if normalized_status:
            bucket = [item for item in bucket if item.status == normalized_status]
        effective_limit = max(1, int(limit or 1))
        return [item.to_dict() for item in bucket[-effective_limit:]]

    async def select_frames(
        self,
        session_id: str,
        limit: int = 1,
        policy: str = "latest",
        status: str = "ready",
        min_speed: float = 0.01,
        min_angular_speed: float = 0.01,
    ) -> list[dict[str, Any]]:
        normalized_session_id = str(session_id or "").strip()
        if not normalized_session_id:
            return []
        normalized_status = str(status or "").strip().lower()
        async with self._lock:
            bucket = list(self._sessions.get(normalized_session_id, ()))
        if normalized_status:
            bucket = [item for item in bucket if item.status == normalized_status]
        frames = [item.to_dict() for item in bucket]
        return select_frames(
            frames,
            limit=limit,
            policy=policy,
            min_speed=min_speed,
            min_angular_speed=min_angular_speed,
        )
