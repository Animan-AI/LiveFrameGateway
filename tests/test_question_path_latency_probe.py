import json
import os
import subprocess
import sys
from pathlib import Path


def _import_probe():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "benchmarks"))
    try:
        import question_path_latency_probe
    finally:
        sys.path.pop(0)
    return question_path_latency_probe


def test_question_path_probe_estimates_saved_latency_with_capture_upload():
    probe = _import_probe()
    rows = [
        {
            "traditional": {"question_to_vlm_ttft_ms": 320.0},
            "ready": {"question_to_vlm_ttft_ms": 260.0},
        },
        {
            "traditional": {"question_to_vlm_ttft_ms": 300.0},
            "ready": {"question_to_vlm_ttft_ms": 250.0},
        },
    ]

    summary = probe.summarize_question_path_rows(
        rows,
        capture_upload_ms=450.0,
        note="test",
    )

    assert summary["capture_upload_ms"] == 450.0
    assert summary["capture_upload_included"] is True
    assert summary["traditional_server_question_to_vlm_ttft_ms"]["p50"] == 310.0
    assert summary["traditional_estimated_user_question_to_vlm_ttft_ms"]["values"] == [770.0, 750.0]
    assert summary["ready_question_to_vlm_ttft_ms"]["values"] == [260.0, 250.0]
    assert summary["estimated_saved_to_vlm_ttft_ms"]["values"] == [510.0, 500.0]


def test_question_path_probe_summarizes_without_capture_upload_as_server_only():
    probe = _import_probe()
    rows = [
        {
            "traditional": {"question_to_vlm_ttft_ms": 320.0},
            "ready": {"question_to_vlm_ttft_ms": 260.0},
        }
    ]

    summary = probe.summarize_question_path_rows(rows, capture_upload_ms=None, note="test")

    assert summary["capture_upload_ms"] is None
    assert summary["capture_upload_included"] is False
    assert summary["traditional_estimated_user_question_to_vlm_ttft_ms"]["values"] == []
    assert summary["server_only_saved_to_vlm_ttft_ms"]["values"] == [60.0]


def test_question_path_probe_offline_mode_outputs_final_json():
    root = Path(__file__).resolve().parents[1]
    proc = subprocess.run(
        [
            sys.executable,
            str(root / "benchmarks" / "question_path_latency_probe.py"),
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
    assert payload["capture_upload_included"] is True
    assert "estimated_saved_to_vlm_ttft_ms" in payload
