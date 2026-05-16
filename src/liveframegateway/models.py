from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any


ROBOT_METADATA_KEYS = (
    "device_id",
    "user_id",
    "seq",
    "behavior_chunk_id",
    "behavior_episode_id",
    "scan_plan_id",
    "scan_phase",
    "coverage_bin",
    "target_pose",
    "pose_state",
    "motion_state",
    "quality",
)


@dataclass
class FrameRecord:
    session_id: str
    frame_uuid: str
    frame_id: str = ""
    ts_ms: int = 0
    status: str = "ready"
    source: str = ""
    digest: str = ""
    image_url: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "session_id": self.session_id,
            "frame_uuid": self.frame_uuid,
            "frame_id": self.frame_id,
            "ts_ms": self.ts_ms,
            "status": self.status,
            "source": self.source,
            "digest": self.digest,
            "image_url": self.image_url,
        }
        payload.update(deepcopy(self.metadata))
        return payload


def normalize_frame_payload(session_id: str, payload: dict[str, Any]) -> FrameRecord:
    if not isinstance(payload, dict):
        payload = {}

    normalized_session_id = str(session_id or "").strip()
    if not normalized_session_id:
        raise ValueError("session_id is required")

    frame_uuid = str(payload.get("frame_uuid") or payload.get("uuid") or "").strip()
    if not frame_uuid:
        raise ValueError("frame_uuid is required")

    mime_type = str(payload.get("mime_type") or "image/jpeg").strip() or "image/jpeg"
    image_url = str(payload.get("image_url") or "").strip()
    image_base64 = str(payload.get("image_base64") or "").strip()
    if not image_url and image_base64:
        image_url = f"data:{mime_type};base64,{image_base64}"

    metadata = {}
    for key in ROBOT_METADATA_KEYS:
        value = payload.get(key)
        if value not in (None, "", [], {}):
            metadata[key] = deepcopy(value)

    return FrameRecord(
        session_id=normalized_session_id,
        frame_uuid=frame_uuid,
        frame_id=str(payload.get("frame_id") or "").strip(),
        ts_ms=int(payload.get("ts_ms") or 0),
        status=str(payload.get("status") or "ready").strip().lower() or "ready",
        source=str(payload.get("source") or "").strip(),
        digest=str(payload.get("digest") or "").strip(),
        image_url=image_url,
        metadata=metadata,
    )
