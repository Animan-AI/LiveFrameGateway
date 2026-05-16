from liveframegateway.injection import inject_openai_messages


def test_inject_openai_messages_replaces_last_user_message():
    messages = [{"role": "system", "content": "You are concise."}, {"role": "user", "content": "old"}]
    frames = [{"frame_uuid": "f1", "image_url": "data:image/jpeg;base64,abc"}]

    result = inject_openai_messages(messages, frames, "What changed?")

    assert result[-1] == {
        "role": "user",
        "content": [
            {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,abc"}, "uuid": "f1"},
            {"type": "text", "text": "What changed?"},
        ],
    }
    assert messages[-1]["content"] == "old"


def test_inject_openai_messages_ignores_frames_without_image_url():
    result = inject_openai_messages([], [{"frame_uuid": "f1"}], "Describe")
    assert result == []
