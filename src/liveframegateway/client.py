from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import aiohttp


@dataclass
class FrameGatewayFrame:
    session_id: str = ""
    frame_uuid: str = ""
    frame_id: str = ""
    ts_ms: int = 0
    status: str = "ready"
    source: str = ""
    digest: str = ""
    image_url: str = ""
    device_id: str = ""
    user_id: str = ""
    seq: int | None = None
    robot_ext: dict[str, Any] = field(default_factory=dict)
    pose_state: dict[str, Any] = field(default_factory=dict)
    motion_state: dict[str, Any] = field(default_factory=dict)
    quality: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "FrameGatewayFrame":
        if not isinstance(payload, dict):
            payload = {}
        return cls(
            session_id=str(payload.get("session_id") or "").strip(),
            frame_uuid=str(payload.get("frame_uuid") or payload.get("uuid") or "").strip(),
            frame_id=str(payload.get("frame_id") or "").strip(),
            ts_ms=int(payload.get("ts_ms") or 0),
            status=str(payload.get("status") or "ready").strip().lower() or "ready",
            source=str(payload.get("source") or "").strip(),
            digest=str(payload.get("digest") or "").strip(),
            image_url=str(payload.get("image_url") or "").strip(),
            device_id=str(payload.get("device_id") or "").strip(),
            user_id=str(payload.get("user_id") or "").strip(),
            seq=_optional_int(payload.get("seq")),
            robot_ext=dict(payload.get("robot_ext") or {}) if isinstance(payload.get("robot_ext"), dict) else {},
            pose_state=dict(payload.get("pose_state") or {}) if isinstance(payload.get("pose_state"), dict) else {},
            motion_state=dict(payload.get("motion_state") or {}) if isinstance(payload.get("motion_state"), dict) else {},
            quality=dict(payload.get("quality") or {}) if isinstance(payload.get("quality"), dict) else {},
        )

    def to_dict(self) -> dict[str, Any]:
        return {key: value for key, value in self.__dict__.items() if value not in (None, "", [], {})}


class FrameGatewayClient:
    def __init__(self, base_url: str, timeout_s: float = 5.0):
        self.base_url = str(base_url or "").rstrip("/")
        self.timeout_s = max(1.0, float(timeout_s or 5.0))
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout_s))
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def ingest_frame(
        self,
        session_id: str,
        *,
        frame_uuid: str,
        ts_ms: int = 0,
        **kwargs: Any,
    ) -> FrameGatewayFrame | None:
        payload = {"frame_uuid": frame_uuid, "ts_ms": int(ts_ms or time.time() * 1000)}
        payload.update({key: value for key, value in kwargs.items() if value not in (None, "", [], {})})
        session = await self._get_session()
        async with session.post(f"{self.base_url}/sessions/{session_id}/frames", json=payload) as resp:
            if resp.status not in {200, 201, 202}:
                return None
            data = await resp.json()
        frame_payload = data.get("frame") if isinstance(data, dict) else data
        return FrameGatewayFrame.from_payload(frame_payload if isinstance(frame_payload, dict) else {})

    async def get_latest_frames(self, session_id: str, n: int = 1, status: str = "ready") -> list[FrameGatewayFrame]:
        session = await self._get_session()
        async with session.get(
            f"{self.base_url}/sessions/{session_id}/frames/latest",
            params={"limit": max(1, int(n or 1)), "status": status},
        ) as resp:
            if resp.status != 200:
                return []
            data = await resp.json()
        raw_frames = data.get("frames", []) if isinstance(data, dict) else []
        return [FrameGatewayFrame.from_payload(item) for item in raw_frames if isinstance(item, dict)]

    async def select_frames(
        self,
        session_id: str,
        n: int = 1,
        policy: str = "latest",
        status: str = "ready",
        min_speed: float = 0.01,
        min_angular_speed: float = 0.01,
    ) -> list[FrameGatewayFrame]:
        session = await self._get_session()
        async with session.get(
            f"{self.base_url}/sessions/{session_id}/frames/select",
            params={
                "limit": max(1, int(n or 1)),
                "policy": policy,
                "status": status,
                "min_speed": min_speed,
                "min_angular_speed": min_angular_speed,
            },
        ) as resp:
            if resp.status != 200:
                return []
            data = await resp.json()
        raw_frames = data.get("frames", []) if isinstance(data, dict) else []
        return [FrameGatewayFrame.from_payload(item) for item in raw_frames if isinstance(item, dict)]


def _optional_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
