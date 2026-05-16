from __future__ import annotations

from typing import Any


def select_frames(
    frames: list[dict[str, Any]],
    limit: int = 1,
    policy: str = "latest",
    min_speed: float = 0.01,
    min_angular_speed: float = 0.01,
) -> list[dict[str, Any]]:
    effective_limit = max(1, int(limit or 1))
    normalized_policy = str(policy or "latest").strip().lower()
    if normalized_policy == "quality":
        return _select_quality(frames, effective_limit)
    if normalized_policy == "motion":
        return _select_motion(frames, effective_limit, min_speed, min_angular_speed)
    return _select_latest(frames, effective_limit)


def _select_latest(frames: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    return list(frames[-limit:])


def _select_quality(frames: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    selected = sorted(frames, key=_quality_rank)[:limit]
    return sorted(selected, key=_timestamp)


def _select_motion(
    frames: list[dict[str, Any]],
    limit: int,
    min_speed: float,
    min_angular_speed: float,
) -> list[dict[str, Any]]:
    moving = [
        frame
        for frame in frames
        if abs(_float_value(_dict_value(frame, "motion_state").get("speed"))) >= min_speed
        or abs(_float_value(_dict_value(frame, "motion_state").get("angular_speed"))) >= min_angular_speed
    ]
    if not moving:
        return _select_latest(frames, limit)
    selected = sorted(moving, key=_motion_rank)[:limit]
    return sorted(selected, key=_timestamp)


def _quality_rank(frame: dict[str, Any]) -> tuple[float, float, int]:
    quality = _dict_value(frame, "quality")
    return (
        _float_value(quality.get("blur_score"), default=float("inf")),
        -_float_value(quality.get("confidence")),
        _timestamp(frame),
    )


def _motion_rank(frame: dict[str, Any]) -> tuple[float, int]:
    motion_state = _dict_value(frame, "motion_state")
    speed = abs(_float_value(motion_state.get("speed")))
    angular_speed = abs(_float_value(motion_state.get("angular_speed")))
    return (-max(speed, angular_speed), _timestamp(frame))


def _dict_value(frame: dict[str, Any], key: str) -> dict[str, Any]:
    value = frame.get(key)
    return value if isinstance(value, dict) else {}


def _float_value(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _timestamp(frame: dict[str, Any]) -> int:
    try:
        return int(frame.get("ts_ms") or 0)
    except (TypeError, ValueError):
        return 0
