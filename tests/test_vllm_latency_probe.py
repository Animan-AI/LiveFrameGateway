import json
import os
import subprocess
import sys
from pathlib import Path


def test_vllm_latency_probe_helpers_build_expected_image_items():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "benchmarks"))
    try:
        import vllm_latency_probe
    finally:
        sys.path.pop(0)

    image_url = "data:image/jpeg;base64,abc"
    assert vllm_latency_probe.build_image_item(image_url) == {
        "type": "image_url",
        "image_url": {"url": image_url},
    }
    assert vllm_latency_probe.build_image_item(image_url, frame_uuid="f1") == {
        "type": "image_url",
        "image_url": {"url": image_url},
        "uuid": "f1",
    }
    assert vllm_latency_probe.build_uuid_only_item("f1") == {
        "type": "image_url",
        "image_url": {},
        "uuid": "f1",
    }


def test_vllm_latency_probe_summarizes_empty_and_numeric_samples():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "benchmarks"))
    try:
        import vllm_latency_probe
    finally:
        sys.path.pop(0)

    assert vllm_latency_probe.summarize_values([]) == {
        "p50": None,
        "p95": None,
        "values": [],
    }
    assert vllm_latency_probe.summarize_values([10.0, 20.0, 30.0]) == {
        "p50": 20.0,
        "p95": 30.0,
        "values": [10.0, 20.0, 30.0],
    }


def test_vllm_latency_probe_offline_mode_outputs_final_json():
    root = Path(__file__).resolve().parents[1]
    proc = subprocess.run(
        [
            sys.executable,
            str(root / "benchmarks" / "vllm_latency_probe.py"),
            "--offline-demo",
        ],
        cwd=root,
        env={**os.environ, "PYTHONPATH": str(root / "src")},
        text=True,
        capture_output=True,
        check=True,
    )

    final_line = proc.stdout.strip().splitlines()[-1]
    assert final_line.startswith("SUMMARY ")
    payload = json.loads(final_line.removeprefix("SUMMARY "))
    assert payload["mode"] == "offline_demo"
    assert payload["note"].startswith("Offline")
    assert "direct_ttft_ms" in payload
    assert "uuid_only_first_statuses" in payload
