from liveframegateway.client import FrameGatewayClient, FrameGatewayFrame
from liveframegateway.service import create_app


async def test_client_ingest_and_latest(aiohttp_server):
    app = create_app(ring_size=2)
    server = await aiohttp_server(app)
    base_url = f"http://{server.host}:{server.port}"
    client = FrameGatewayClient(base_url=base_url)
    try:
        frame = await client.ingest_frame(
            "sess",
            frame_uuid="f1",
            ts_ms=1,
            image_base64="ZmFrZQ==",
            pose_state={"body_yaw_deg": 1.0},
        )
        latest = await client.get_latest_frames("sess", n=1)
    finally:
        await client.close()

    assert frame is not None
    assert frame.frame_uuid == "f1"
    assert latest[0].frame_uuid == "f1"
    assert latest[0].pose_state["body_yaw_deg"] == 1.0


def test_frame_gateway_frame_uses_robot_ext():
    payload = {
        "session_id": "sess",
        "frame_uuid": "f1",
        "robot_ext": {"scan_phase": "sweep_left"},
        "pose_state": {"body_yaw_deg": 1.0},
    }

    frame = FrameGatewayFrame.from_payload(payload)

    assert frame.robot_ext == {"scan_phase": "sweep_left"}
    assert frame.pose_state == {"body_yaw_deg": 1.0}
    assert "robot_ext" in frame.to_dict()


async def test_client_select_frames(aiohttp_server):
    app = create_app(ring_size=3)
    server = await aiohttp_server(app)
    base_url = f"http://{server.host}:{server.port}"
    client = FrameGatewayClient(base_url=base_url)
    try:
        await client.ingest_frame("sess", frame_uuid="f1", ts_ms=1, quality={"blur_score": 0.8})
        await client.ingest_frame("sess", frame_uuid="f2", ts_ms=2, quality={"blur_score": 0.1})
        selected = await client.select_frames("sess", n=1, policy="quality")
    finally:
        await client.close()

    assert [frame.frame_uuid for frame in selected] == ["f2"]
