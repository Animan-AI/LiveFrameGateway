# LiveFrameGateway

**Live Visual Context Infrastructure for Embodied Agents.**

LiveFrameGateway is a lightweight, backend-agnostic frame lifecycle layer for real-time VLM and embodied-agent applications.

**Not an encoder cache. Not a model proxy.** It manages live visual context before a model call: capture, normalize, retain, select, prime, evict, and inject frames so the user's question path does less work.

## Why This Exists

Live camera agents often pay avoidable latency after a user asks a visual question: locating a recent frame, validating it, converting it, sending it through a primer or encoder path, then building the VLM request.

LiveFrameGateway moves that work earlier. Frame producers continuously push frames into a bounded session ring. When the agent needs vision, it can fetch the latest ready frames and inject them directly into a model request.

The open-source positioning is deliberately conservative:

> A lightweight, backend-agnostic real-time frame gateway for VLM and embodied agents, combining session-scoped ready-frame rings, OpenAI-compatible frame injection, optional encoder-cache priming, eviction hooks, and robot observation metadata.

## How It Relates To Omni Or Realtime Multimodal Models

Omni and realtime multimodal models are strong at low-latency conversation and model-side audio/visual understanding. LiveFrameGateway is complementary infrastructure: it manages which live frames are available, ready, selected, traceable, and attached before the model call.

For embodied agents, the useful boundary is not "another chat model." The boundary is a live visual context layer that can preserve pose, motion, quality, and robot-specific observation metadata while staying independent of the model backend.

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

## Select Frames By Policy

```bash
curl -s 'http://127.0.0.1:8095/sessions/demo/frames/select?limit=2&policy=quality'
```

Supported policies:

- `latest`: latest K ready frames
- `quality`: prefers low `quality.blur_score` and high `quality.confidence`
- `motion`: prefers frames where `motion_state.speed` or `motion_state.angular_speed` exceeds a threshold

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
- `pose_state`
- `motion_state`
- `quality`
- `robot_ext`: optional extension object for robot-specific fields such as `scan_phase`, `coverage_bin`, `target_pose`, and `behavior_episode_id`

`GET /sessions/{session_id}/frames/latest?limit=K&status=ready`

Returns the latest K frames in old-to-new order within the returned window.

`GET /sessions/{session_id}/frames/select?limit=K&policy=quality`

Returns ready frames selected by policy.

## Benchmark

Run a synthetic replay benchmark:

```bash
python benchmarks/replay_latency.py --frames 120 --queries 20 --frame-bytes 4096 --select-k 3 --policy quality
```

Example local output from this repository:

```text
LiveFrameGateway synthetic replay benchmark
frames=120 queries=20 select_k=3 policy=quality
inline request prep p50/p95: 3.770 / 4.026 ms
gateway request prep p50/p95: 2.523 / 2.618 ms
gateway fetch p50/p95: 2.428 / 2.519 ms
```

This is a synthetic request-preparation benchmark, not a model latency benchmark. Its purpose is to measure how much work can be moved out of the user question path before a VLM call.

## Mock Primer Lifecycle Demo

Terminal 1:

```bash
python examples/mock_primer_service.py --host 127.0.0.1 --port 18096 --cache-root /tmp/liveframegateway-ec
```

Terminal 2:

```bash
liveframegateway serve --host 127.0.0.1 --port 18095 --ring-size 1 \
  --primer-url http://127.0.0.1:18096/prime \
  --ec-shared-storage-path /tmp/liveframegateway-ec
```

Ingest two frames into the same session. The second frame overflows the ring and the first frame's mock cache directory is removed by the eviction hook.

## Deployment

The gateway must be reachable by frame producers and VLM or agent consumers. It does not require a dedicated cloud server.

Practical deployment options:

- cloud sidecar next to an agent and VLM runtime
- robot-local service
- edge box on the local network
- in-process Python library for demos and tests

## Non-Goals

The first release does not include LightMe ASR, TTS, memory, MCP tools, motion control, proactive planning, llama.cpp embedding files, `/v1/chat/completions_cached`, a semantic router, persistent frame database, or browser UI.
