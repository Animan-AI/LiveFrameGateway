from liveframegateway.client import FrameGatewayClient
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
