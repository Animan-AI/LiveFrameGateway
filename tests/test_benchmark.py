import json
import os
import subprocess
import sys
from pathlib import Path


def test_replay_latency_benchmark_smoke_outputs_final_json():
    root = Path(__file__).resolve().parents[1]
    proc = subprocess.run(
        [
            sys.executable,
            str(root / "benchmarks" / "replay_latency.py"),
            "--frames",
            "8",
            "--queries",
            "3",
            "--frame-bytes",
            "128",
            "--select-k",
            "2",
            "--policy",
            "quality",
        ],
        cwd=root,
        env={**os.environ, "PYTHONPATH": str(root / "src")},
        text=True,
        capture_output=True,
        check=True,
    )

    final_line = proc.stdout.strip().splitlines()[-1]
    payload = json.loads(final_line)
    assert payload["frames"] == 8
    assert payload["queries"] == 3
    assert payload["frame_bytes"] == 128
    assert payload["select_k"] == 2
    assert payload["policy"] == "quality"
    assert isinstance(payload["fps"], (int, float))
    assert "synthetic" in payload["note"].lower()
    assert "not a model latency benchmark" in payload["note"]
    for key in [
        "inline_request_prep_ms_p50",
        "inline_request_prep_ms_p95",
        "gateway_request_prep_ms_p50",
        "gateway_request_prep_ms_p95",
        "gateway_fetch_ms_p50",
        "gateway_fetch_ms_p95",
        "selected_frame_age_ms_p50",
        "selected_frame_age_ms_p95",
    ]:
        assert key in payload
        assert payload[key] >= 0.0
