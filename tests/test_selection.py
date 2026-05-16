from liveframegateway.selection import select_frames


FRAMES = [
    {"frame_uuid": "f1", "ts_ms": 1, "quality": {"blur_score": 0.9, "confidence": 0.4}},
    {"frame_uuid": "f2", "ts_ms": 2, "quality": {"blur_score": 0.1, "confidence": 0.8}},
    {"frame_uuid": "f3", "ts_ms": 3, "quality": {"blur_score": 0.2, "confidence": 0.9}},
    {"frame_uuid": "f4", "ts_ms": 4, "motion_state": {"speed": 0.0, "angular_speed": 0.0}},
    {"frame_uuid": "f5", "ts_ms": 5, "motion_state": {"speed": 0.2, "angular_speed": 0.0}},
]


def test_latest_policy_returns_latest_window_old_to_new():
    selected = select_frames(FRAMES, limit=2, policy="latest")
    assert [frame["frame_uuid"] for frame in selected] == ["f4", "f5"]


def test_quality_policy_prefers_low_blur_and_high_confidence_then_returns_chronological():
    selected = select_frames(FRAMES, limit=2, policy="quality")
    assert [frame["frame_uuid"] for frame in selected] == ["f2", "f3"]


def test_motion_policy_prefers_moving_frames_then_returns_chronological():
    selected = select_frames(FRAMES, limit=1, policy="motion", min_speed=0.01, min_angular_speed=0.01)
    assert [frame["frame_uuid"] for frame in selected] == ["f5"]


def test_motion_policy_ranks_by_strongest_motion_before_returning_chronological():
    frames = [
        {"frame_uuid": "f1", "ts_ms": 1, "motion_state": {"speed": 0.1, "angular_speed": 0.0}},
        {"frame_uuid": "f2", "ts_ms": 2, "motion_state": {"speed": 0.6, "angular_speed": 0.0}},
        {"frame_uuid": "f3", "ts_ms": 3, "motion_state": {"speed": 0.2, "angular_speed": 0.7}},
        {"frame_uuid": "f4", "ts_ms": 4, "motion_state": {"speed": 0.5, "angular_speed": 0.0}},
    ]

    selected = select_frames(frames, limit=1, policy="motion", min_speed=0.01, min_angular_speed=0.01)

    assert [frame["frame_uuid"] for frame in selected] == ["f3"]


def test_motion_policy_falls_back_to_latest_when_no_motion_qualified_frames():
    frames = [
        {"frame_uuid": "f1", "ts_ms": 1, "motion_state": {"speed": 0.0}},
        {"frame_uuid": "f2", "ts_ms": 2, "motion_state": {"speed": 0.0}},
    ]
    selected = select_frames(frames, limit=1, policy="motion", min_speed=0.5, min_angular_speed=0.5)
    assert [frame["frame_uuid"] for frame in selected] == ["f2"]


def test_unknown_policy_uses_latest():
    selected = select_frames(FRAMES, limit=2, policy="unknown")
    assert [frame["frame_uuid"] for frame in selected] == ["f4", "f5"]
