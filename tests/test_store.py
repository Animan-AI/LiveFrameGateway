import asyncio

from liveframegateway.store import FrameRingBufferStore


def test_store_keeps_latest_ready_frames_per_session():
    async def run():
        store = FrameRingBufferStore(ring_size=3)
        await store.ingest("sess_a", {"frame_uuid": "a1", "ts_ms": 1, "status": "ready"})
        await store.ingest("sess_b", {"frame_uuid": "b1", "ts_ms": 2, "status": "ready"})
        await store.ingest("sess_a", {"frame_uuid": "a2", "ts_ms": 3, "status": "pending"})
        await store.ingest("sess_a", {"frame_uuid": "a3", "ts_ms": 4, "status": "ready"})
        return await store.get_latest_frames("sess_a", limit=5, status="ready")

    frames = asyncio.run(run())
    assert [frame["frame_uuid"] for frame in frames] == ["a1", "a3"]


def test_store_overflow_evicts_oldest_and_calls_hook():
    async def run():
        evicted = []

        async def on_evict(record):
            evicted.append(record["frame_uuid"])

        store = FrameRingBufferStore(ring_size=2, on_evict=on_evict)
        await store.ingest("sess", {"frame_uuid": "f1", "ts_ms": 1})
        await store.ingest("sess", {"frame_uuid": "f2", "ts_ms": 2})
        await store.ingest("sess", {"frame_uuid": "f3", "ts_ms": 3})
        frames = await store.get_latest_frames("sess", limit=5)
        return frames, evicted

    frames, evicted = asyncio.run(run())
    assert [frame["frame_uuid"] for frame in frames] == ["f2", "f3"]
    assert evicted == ["f1"]


def test_same_uuid_update_does_not_evict():
    async def run():
        evicted = []
        store = FrameRingBufferStore(ring_size=2, on_evict=lambda record: evicted.append(record["frame_uuid"]))
        await store.ingest("sess", {"frame_uuid": "f1", "frame_id": "old", "ts_ms": 1})
        await store.ingest("sess", {"frame_uuid": "f1", "frame_id": "new", "ts_ms": 2})
        frames = await store.get_latest_frames("sess", limit=5)
        return frames, evicted

    frames, evicted = asyncio.run(run())
    assert [frame["frame_id"] for frame in frames] == ["new"]
    assert evicted == []


def test_robot_metadata_survives_round_trip():
    async def run():
        store = FrameRingBufferStore(ring_size=2)
        await store.ingest(
            "sess",
            {
                "frame_uuid": "f1",
                "ts_ms": 1,
                "pose_state": {"body_yaw_deg": 12.5},
                "scan_phase": "sweep_left",
                "coverage_bin": "yaw_1",
                "quality": {"blur_score": 0.2},
            },
        )
        return await store.get_latest_frames("sess", limit=1)

    frames = asyncio.run(run())
    assert frames[0]["pose_state"]["body_yaw_deg"] == 12.5
    assert frames[0]["scan_phase"] == "sweep_left"
    assert frames[0]["coverage_bin"] == "yaw_1"
    assert frames[0]["quality"]["blur_score"] == 0.2
