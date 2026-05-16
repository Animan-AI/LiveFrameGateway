__all__ = [
    "FrameGatewayClient",
    "FrameGatewayFrame",
    "FrameRingBufferStore",
    "inject_openai_messages",
]


def __getattr__(name):
    if name in {"FrameGatewayClient", "FrameGatewayFrame"}:
        from .client import FrameGatewayClient, FrameGatewayFrame

        return {"FrameGatewayClient": FrameGatewayClient, "FrameGatewayFrame": FrameGatewayFrame}[name]
    if name == "FrameRingBufferStore":
        from .store import FrameRingBufferStore

        return FrameRingBufferStore
    if name == "inject_openai_messages":
        from .injection import inject_openai_messages

        return inject_openai_messages
    raise AttributeError(name)
