from __future__ import annotations

from copy import deepcopy
from typing import Any


def inject_openai_messages(
    messages: list[dict[str, Any]],
    frames: list[dict[str, Any]],
    user_text: str,
) -> list[dict[str, Any]]:
    content = []
    for frame in frames or []:
        if not isinstance(frame, dict):
            continue
        image_url = str(frame.get("image_url") or "").strip()
        if not image_url:
            continue
        item = {"type": "image_url", "image_url": {"url": image_url}}
        frame_uuid = str(frame.get("frame_uuid") or frame.get("uuid") or "").strip()
        if frame_uuid:
            item["uuid"] = frame_uuid
        content.append(item)
    if not content:
        return deepcopy(messages or [])
    content.append({"type": "text", "text": str(user_text or "").strip()})

    updated = deepcopy(messages or [])
    user_message = {"role": "user", "content": content}
    if updated and updated[-1].get("role") == "user":
        updated[-1] = user_message
    else:
        updated.append(user_message)
    return updated
