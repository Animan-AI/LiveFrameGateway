# LiveFrameGateway

LiveFrameGateway is a lightweight, backend-agnostic frame gateway for real-time VLM and embodied-agent applications.

It keeps per-session ready-frame rings, preserves robot observation metadata, optionally primes encoder caches, and helps inject latest-K frames into OpenAI-compatible multimodal messages.

It is not an encoder cache implementation. It manages live visual context lifecycle before the VLM call: capture, normalize, retain, select, and inject frames so the user question path does less work.

## Why This Exists

Live camera agents often pay avoidable latency after a user asks a visual question: locating a recent frame, validating it, converting it, sending it through a primer or encoder path, then building the VLM request.

LiveFrameGateway moves that work earlier. Frame producers continuously push frames into a bounded session ring. When the agent needs vision, it can fetch the latest ready frames and inject them directly into a model request.

The open-source positioning is deliberately conservative:

> A lightweight, backend-agnostic real-time frame gateway for VLM and embodied agents, combining session-scoped ready-frame rings, OpenAI-compatible frame injection, optional encoder-cache priming, eviction hooks, and robot observation metadata.

## Install

```bash
pip install -e ".[dev]"
```

## Run

```bash
liveframegateway serve --host 0.0.0.0 --port 8095 --ring-size 20
```

## Ingest A Frame

```bash
curl -s http://127.0.0.1:8095/sessions/demo/frames \
  -H 'content-type: application/json' \
  -d '{"frame_uuid":"frame_001","ts_ms":1778880000000,"image_base64":"ZmFrZQ==","pose_state":{"body_yaw_deg":12.5}}'
```

Response:

```json
{
  "status": "ready",
  "frame": {
    "session_id": "demo",
    "frame_uuid": "frame_001",
    "ts_ms": 1778880000000,
    "status": "ready",
    "image_url": "data:image/jpeg;base64,ZmFrZQ==",
    "pose_state": {"body_yaw_deg": 12.5}
  }
}
```

## Fetch Latest Ready Frames

```bash
curl -s 'http://127.0.0.1:8095/sessions/demo/frames/latest?limit=1&status=ready'
```

## Python Injection

```python
from liveframegateway.injection import inject_openai_messages

messages = [{"role": "system", "content": "You are concise."}]
frames = [{"frame_uuid": "frame_001", "image_url": "data:image/jpeg;base64,ZmFrZQ=="}]
messages = inject_openai_messages(messages, frames, "What is in front of the robot?")
```

The final user message becomes OpenAI-compatible multimodal content:

```json
[
  {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,ZmFrZQ=="}, "uuid": "frame_001"},
  {"type": "text", "text": "What is in front of the robot?"}
]
```

## HTTP API

`GET /health`

Returns `{"status":"ok"}`.

`POST /sessions/{session_id}/frames`

Required field:

- `frame_uuid`

Common optional fields:

- `frame_id`
- `ts_ms`
- `image_base64`
- `image_url`
- `mime_type`
- `source`
- `digest`
- `device_id`
- `user_id`
- `seq`
- `behavior_chunk_id`
- `behavior_episode_id`
- `scan_plan_id`
- `scan_phase`
- `coverage_bin`
- `target_pose`
- `pose_state`
- `motion_state`
- `quality`

`GET /sessions/{session_id}/frames/latest?limit=K&status=ready`

Returns the latest K frames in old-to-new order within the returned window.

## Deployment

The gateway must be reachable by frame producers and VLM or agent consumers. It does not require a dedicated cloud server.

Practical deployment options:

- cloud sidecar next to an agent and VLM runtime
- robot-local service
- edge box on the local network
- in-process Python library for demos and tests

## Non-Goals

The first release does not include LightMe ASR, TTS, memory, MCP tools, motion control, proactive planning, llama.cpp embedding files, `/v1/chat/completions_cached`, a semantic router, persistent frame database, or browser UI.
