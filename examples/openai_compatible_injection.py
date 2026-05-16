import asyncio

from liveframegateway.client import FrameGatewayClient
from liveframegateway.injection import inject_openai_messages


async def main() -> None:
    client = FrameGatewayClient("http://127.0.0.1:8095")
    try:
        await client.ingest_frame(
            "demo",
            frame_uuid="frame_001",
            ts_ms=1778880000000,
            image_base64="ZmFrZQ==",
            pose_state={"body_yaw_deg": 12.5},
            source="robot_stream",
        )
        frames = [frame.to_dict() for frame in await client.get_latest_frames("demo", n=1)]
    finally:
        await client.close()

    messages = inject_openai_messages(
        [{"role": "system", "content": "You are a concise robot vision assistant."}],
        frames,
        "What is in front of the robot?",
    )
    print(messages)


if __name__ == "__main__":
    asyncio.run(main())
