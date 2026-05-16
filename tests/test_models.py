from liveframegateway.models import normalize_frame_payload


def test_normalize_moves_specialized_robot_fields_into_robot_ext():
    record = normalize_frame_payload(
        "sess",
        {
            "frame_uuid": "f1",
            "pose_state": {"body_yaw_deg": 12.5},
            "motion_state": {"speed": 0.3},
            "quality": {"blur_score": 0.2},
            "scan_phase": "sweep_left",
            "coverage_bin": "yaw_1",
            "behavior_episode_id": "episode_7",
            "target_pose": {"x": 1.0},
        },
    )

    payload = record.to_dict()
    assert payload["pose_state"]["body_yaw_deg"] == 12.5
    assert payload["motion_state"]["speed"] == 0.3
    assert payload["quality"]["blur_score"] == 0.2
    assert payload["robot_ext"] == {
        "scan_phase": "sweep_left",
        "coverage_bin": "yaw_1",
        "behavior_episode_id": "episode_7",
        "target_pose": {"x": 1.0},
    }
    assert "scan_phase" not in payload
    assert "coverage_bin" not in payload
    assert "behavior_episode_id" not in payload
    assert "target_pose" not in payload


def test_normalize_merges_existing_robot_ext_with_legacy_fields():
    record = normalize_frame_payload(
        "sess",
        {
            "frame_uuid": "f1",
            "robot_ext": {"custom": "value", "scan_phase": "from_ext"},
            "scan_phase": "from_legacy",
            "coverage_bin": "yaw_2",
        },
    )

    payload = record.to_dict()
    assert payload["robot_ext"] == {
        "custom": "value",
        "scan_phase": "from_legacy",
        "coverage_bin": "yaw_2",
    }
