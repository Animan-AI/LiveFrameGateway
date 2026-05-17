# LiveFrameGateway Design

## Purpose

LiveFrameGateway is a standalone Python package and CLI service for live VLM and embodied-agent applications. It provides a backend-agnostic frame gateway: clients continuously ingest camera frames into per-session ready-frame rings, and an agent runtime later selects the latest K frames and injects them into OpenAI-compatible multimodal requests.

The project targets two audiences:

- General VLM developers who need a small service between a live camera stream and a VLM backend.
- Embodied robotics developers who need robot observation metadata, pose-tagged frame history, and bounded frame lifecycle management.

The first release is a reusable product, not a full robot assistant. It intentionally excludes ASR, TTS, memory, tool execution, motion control, proactive planning, private model backends, and lower-level encoder-cache implementations.

## Originality Positioning

LiveFrameGateway should not claim to be the first ViT cache or encoder cache system. Existing systems cover lower-level encoder-output caching.

The defensible open-source positioning is:

> A lightweight, backend-agnostic real-time frame gateway for VLM and embodied agents, combining session-scoped ready-frame rings, OpenAI-compatible frame injection, optional encoder-cache priming, eviction hooks, and robot observation metadata.

The practical contribution is reducing perceived latency in live camera interactions by moving frame capture, frame normalization, frame readiness, selection, and optional encoder priming out of the user's query path. When the user asks a visual question, the agent can inject an already available frame window instead of first locating, validating, uploading, or encoding the relevant frames.

## Product Shape

Repository path:

```text
/home/meng/LiveFrameGateway
```

Install and run:

```bash
pip install -e .
liveframegateway serve --host 0.0.0.0 --port 8095 --ring-size 20
```

The package exposes:

- an aiohttp HTTP service
- a small Python client
- message injection helpers for OpenAI-compatible VLM requests
- optional encoder-primer adapters
- tests and examples

The architecture requires a gateway runtime that both frame producers and VLM or agent consumers can reach. It does not require a dedicated cloud server. The same package can run as a cloud sidecar, on a robot, on a local edge box, or in-process as a Python library.

## Core API

### Ingest Frame

```http
POST /sessions/{session_id}/frames
```

Request fields:

- `frame_uuid`: required stable frame identifier
- `frame_id`: optional human-readable or upstream frame id
- `ts_ms`: frame timestamp in milliseconds
- `image_base64` or `image_url`: image source
- `mime_type`: defaults to `image/jpeg` when base64 is supplied
- `source`: such as `camera`, `robot_stream`, `app_upload`, `surface_attachment`
- `digest`: optional content hash
- robot metadata: `device_id`, `user_id`, `seq`, `pose_state`, `motion_state`, `quality`
- `robot_ext`: optional extension object for robot-specific fields such as `scan_phase`, `coverage_bin`, `target_pose`, and `behavior_episode_id`

Response:

```json
{
  "status": "ready",
  "frame": {
    "session_id": "sess_1",
    "frame_uuid": "frame_001",
    "frame_id": "sess_1::frame_001",
    "ts_ms": 1778880000000,
    "status": "ready",
    "image_url": "data:image/jpeg;base64,..."
  }
}
```

Status values:

- `pending`: accepted but encoder priming has not completed
- `ready`: usable for VLM injection
- `failed`: encoder primer failed or input is invalid
- `expired`: reserved for future persistent stores

### Latest Ready Frames

```http
GET /sessions/{session_id}/frames/latest?limit=K&status=ready
```

Response:

```json
{
  "frames": [
    {
      "session_id": "sess_1",
      "frame_uuid": "frame_001",
      "ts_ms": 1778880000000,
      "status": "ready",
      "image_url": "data:image/jpeg;base64,..."
    }
  ]
}
```

Ordering is old-to-new within the returned latest K window. This makes direct multi-frame VLM injection natural for change-detection prompts.

### Select Frames By Policy

```http
GET /sessions/{session_id}/frames/select?limit=K&policy=quality
```

Response:

```json
{
  "policy": "quality",
  "frames": [
    {
      "session_id": "sess_1",
      "frame_uuid": "frame_001",
      "ts_ms": 1778880000000,
      "status": "ready",
      "image_url": "data:image/jpeg;base64,..."
    }
  ]
}
```

Supported policies are `latest`, `quality`, and `motion`.

### Health

```http
GET /health
```

Response:

```json
{"status": "ok"}
```

## Architecture

### Service

The HTTP service owns a `FrameRingBufferStore`.

Responsibilities:

- validate frame ingest payloads
- normalize `image_base64` into a data URL
- store frames in a per-session bounded ring
- deduplicate by `frame_uuid` within the same session
- return latest ready frames
- run optional encoder primer logic
- invoke eviction cleanup hooks for external encoder-cache files or directories

### Store

The store maintains:

```python
dict[str, deque[FrameRecord]]
```

Each session gets its own ring. The ring size is global in the first release. When a session ring overflows, the oldest record is evicted and the configured cleanup hook is called.

The store also tracks `session_last_seen` and prunes stale sessions on a bounded interval. Stale session pruning evicts all records for that session and runs the same cleanup hook.

### Selection Policies

Frame selection operates over ready frames in the session ring:

- `latest`: returns the latest K ready frames in old-to-new order within the returned window.
- `quality`: prefers frames with low `quality.blur_score` and high `quality.confidence`.
- `motion`: prefers frames where `motion_state.speed` or `motion_state.angular_speed` exceeds a threshold.

### Encoder Primer

The first release supports a generic HTTP primer adapter.

The primer is optional. When configured, it is called during ingest with the normalized frame payload. A successful primer marks the frame `ready`; a failed primer returns HTTP 502 from ingest and does not add a ready frame.

This synchronous primer behavior is intentionally simple for the MVP. A later async mode can store `pending`, run the primer in the background, then update the record to `ready` or `failed`.

The core package does not include a full ViT encoder service. A production deployment can attach a separate encoder-only service through the primer hook, but the exact cache format and retrieval semantics belong to that backend. For example, a vLLM-compatible encoder producer can write an external `encoder_cache.safetensors` file keyed by `frame_uuid`, while a consumer backend may still require image bytes unless its request path can resolve uuid-only inputs from that external cache.

Therefore, public claims should distinguish:

- gateway-level readiness: the frame is captured, uploaded, normalized, selected, and available before the user asks
- primer-level readiness: an optional backend has completed its encoder priming work
- consumer-level cache hit: the final VLM request can actually consume the prepared frame or encoder cache without re-uploading or re-encoding image bytes

### Message Injection

The package provides:

```python
inject_openai_messages(messages, frames, user_text)
```

It returns a new message list whose final user message contains image items followed by the user text:

```json
[
  {
    "type": "image_url",
    "image_url": {"url": "data:image/jpeg;base64,..."},
    "uuid": "frame_001"
  },
  {
    "type": "text",
    "text": "What changed?"
  }
]
```

The helper does not call a model. Agent runtimes remain responsible for deciding whether vision is needed, how many frames to select, and which VLM backend to call.

### Benchmark Scope

The replay benchmark measures synthetic request-preparation latency, not model latency. It compares inline request preparation against a gateway path where frame ingest, normalization, selection, and readiness work can happen before the user asks a visual question.

Benchmark output in the README is local example output from this repository. It should not be presented as a universal model latency claim.

The live vLLM probe measures a real OpenAI-compatible backend if one is already running. It intentionally separates direct image requests, `image_url + uuid` requests, fresh `uuid-only` requests, and `uuid-only` requests after the consumer has seen the same UUID. This prevents over-claiming: `uuid-only` success after a local consumer-cache warmup is not the same thing as fresh external encoder-cache consumption.

The question-path probe estimates perceived latency more directly. Without device-side timestamps, it measures only the server-side portion after an image is already available. With a real `capture_upload_ms` measurement from the robot or edge client, it can estimate the traditional user path:

```text
question -> capture -> encode -> upload -> VLM first token
```

and compare it with the ready-frame path:

```text
question -> fetch latest ready frame -> VLM first token
```

This distinction is required for honest reporting. Server-side VLM numbers alone do not include camera exposure, image encoding, network upload, or device playback.

## Roadmap

- richer frame selection policies: latest-K, motion-aware, coverage-aware, scene-change-aware
- async primer mode for heavy VLM encoder paths
- replay and benchmark tools to measure perceived latency reduction
- visual context trace for debugging frame choice and injection
- privacy and edge-first modes, including local-only retention policies
- adapters for popular VLM runtimes without becoming a model proxy

## Success Criteria

- `liveframegateway serve` starts a local service.
- A client can ingest frames into one session and query the latest ready frames.
- Ring overflow evicts the oldest frame and triggers cleanup.
- `inject_openai_messages()` produces a valid OpenAI-compatible multimodal user message.
- Robot metadata survives ingest and latest-frame retrieval.
- Tests pass with `pytest`.
