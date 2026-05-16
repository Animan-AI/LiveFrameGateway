from pathlib import Path

from liveframegateway.service import create_app


async def test_service_ingest_and_latest(aiohttp_client):
    app = create_app(ring_size=3)
    client = await aiohttp_client(app)

    resp = await client.post(
        "/sessions/sess/frames",
        json={"frame_uuid": "f1", "ts_ms": 1, "image_base64": "ZmFrZQ=="},
    )
    assert resp.status == 200
    payload = await resp.json()
    assert payload["status"] == "ready"
    assert payload["frame"]["image_url"].startswith("data:image/jpeg;base64,")

    resp = await client.get("/sessions/sess/frames/latest", params={"limit": "1", "status": "ready"})
    assert resp.status == 200
    latest = await resp.json()
    assert [frame["frame_uuid"] for frame in latest["frames"]] == ["f1"]


async def test_service_ring_overflow_cleans_ec_cache(tmp_path: Path, aiohttp_client):
    ec_root = tmp_path / "ec"
    (ec_root / "f1").mkdir(parents=True)
    (ec_root / "f1" / "encoder_cache.bin").write_bytes(b"fake")

    app = create_app(ring_size=1, ec_shared_storage_path=str(ec_root))
    client = await aiohttp_client(app)
    await client.post("/sessions/sess/frames", json={"frame_uuid": "f1", "ts_ms": 1})
    await client.post("/sessions/sess/frames", json={"frame_uuid": "f2", "ts_ms": 2})

    assert not (ec_root / "f1").exists()


async def test_service_primer_failure_returns_502(aiohttp_client):
    async def failing_primer(_session_id, _frame):
        raise RuntimeError("primer failed")

    app = create_app(ring_size=2, primer=failing_primer)
    client = await aiohttp_client(app)
    resp = await client.post(
        "/sessions/sess/frames",
        json={"frame_uuid": "f1", "image_base64": "ZmFrZQ=="},
    )
    assert resp.status == 502


async def test_service_select_frames_by_quality(aiohttp_client):
    app = create_app(ring_size=5)
    client = await aiohttp_client(app)
    await client.post(
        "/sessions/sess/frames",
        json={"frame_uuid": "f1", "ts_ms": 1, "quality": {"blur_score": 0.9, "confidence": 0.2}},
    )
    await client.post(
        "/sessions/sess/frames",
        json={"frame_uuid": "f2", "ts_ms": 2, "quality": {"blur_score": 0.1, "confidence": 0.8}},
    )
    await client.post(
        "/sessions/sess/frames",
        json={"frame_uuid": "f3", "ts_ms": 3, "quality": {"blur_score": 0.2, "confidence": 0.9}},
    )

    resp = await client.get("/sessions/sess/frames/select", params={"limit": "2", "policy": "quality"})

    assert resp.status == 200
    payload = await resp.json()
    assert payload["policy"] == "quality"
    assert [frame["frame_uuid"] for frame in payload["frames"]] == ["f2", "f3"]
