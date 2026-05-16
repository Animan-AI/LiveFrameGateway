import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from examples.mock_primer_service import build_cache_artifact, sanitize_cache_name


def test_sanitize_cache_name_rejects_path_separators():
    with pytest.raises(ValueError, match="cache name must not contain path separators"):
        sanitize_cache_name("sess/../frame")
    with pytest.raises(ValueError, match="cache name must not contain path separators"):
        sanitize_cache_name("sess\\frame")


def test_sanitize_cache_name_allows_gateway_cache_name():
    assert sanitize_cache_name("sess::frame") == "sess::frame"


def test_build_cache_artifact_creates_encoder_cache_json(tmp_path: Path):
    frame = {"frame_uuid": "f1", "ts_ms": 123, "image_url": "data:image/jpeg;base64,abc"}

    artifact_path = build_cache_artifact(tmp_path, "sess", frame)

    assert artifact_path == tmp_path / "sess::f1" / "encoder_cache.json"
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert payload["session_id"] == "sess"
    assert payload["frame_uuid"] == "f1"
    assert payload["ts_ms"] == 123
    assert payload["kind"] == "mock_encoder_cache"
    assert payload["embedding_digest"]
