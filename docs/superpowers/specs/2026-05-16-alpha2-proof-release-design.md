# LiveFrameGateway Alpha2 Proof Release Design

## Purpose

The alpha2 release turns LiveFrameGateway from a clean reference implementation into a more defensible open-source project. It directly addresses the current weak points: the MVP can look like a small ring-buffer helper, its latency benefit is not measured, the primer path is abstract, and selection is only latest-K.

The release goal is not to claim algorithmic novelty. The goal is to demonstrate a useful, reusable system boundary:

> Not an encoder cache. Not a model proxy. A live frame lifecycle layer for embodied agents.

Alpha2 should make that claim verifiable with a benchmark, a non-trivial selection policy, a primer lifecycle demo, and a cleaner robot metadata schema.

## Scope

Alpha2 includes four workstreams:

- replay latency benchmark
- frame selection policies
- reference mock primer and eviction lifecycle example
- schema cleanup and positioning rewrite

Alpha2 does not include real model serving, real ViT/SigLIP/CLIP embedding computation, WebRTC, camera capture, persistence, auth, or a browser UI.

## Benchmark

Add `benchmarks/replay_latency.py`.

The benchmark compares two request-preparation paths:

- `inline`: when a visual question arrives, select recent frames from an in-process list, normalize image payloads, and build OpenAI-compatible messages in the same path.
- `gateway`: continuously ingest frames into a local LiveFrameGateway app, then when a visual question arrives, fetch selected frames from the gateway and build OpenAI-compatible messages.

The benchmark uses synthetic frame payloads by default so it is deterministic and does not require a camera or model backend. It should support configurable frame count, frame size, FPS, session id, selected K, and selection policy.

Required output metrics:

- `inline_request_prep_ms_p50`
- `inline_request_prep_ms_p95`
- `gateway_request_prep_ms_p50`
- `gateway_request_prep_ms_p95`
- `gateway_fetch_ms_p50`
- `gateway_fetch_ms_p95`
- `selected_frame_age_ms_p50`
- `selected_frame_age_ms_p95`

The benchmark should print both human-readable text and a final JSON object. README will include a clearly labeled example result from one local run, not a universal performance claim.

## Selection Policies

Add `src/liveframegateway/selection.py`.

Supported policies:

- `latest`: current latest-K behavior, old-to-new within the selected window.
- `quality`: prefer frames with lower blur and higher confidence when `quality` metadata is present, then return selected frames in chronological order.
- `motion`: prefer frames where `motion_state.speed` or `motion_state.angular_speed` exceeds a threshold, then return selected frames in chronological order. If no motion-qualified frames exist, fall back to latest.

Add a new service route:

```http
GET /sessions/{session_id}/frames/select?limit=K&policy=quality
```

Optional query parameters:

- `status`: defaults to `ready`
- `min_speed`: used by `motion`, defaults to `0.01`
- `min_angular_speed`: used by `motion`, defaults to `0.01`

The existing latest route remains for compatibility:

```http
GET /sessions/{session_id}/frames/latest?limit=K&status=ready
```

The Python client adds:

```python
await client.select_frames("sess", n=3, policy="quality")
```

## Reference Primer

Add `examples/mock_primer_service.py`.

This example service accepts primer POST requests from LiveFrameGateway, creates a mock external cache artifact, and returns a ready status:

```text
/tmp/liveframegateway-ec/{session_id}::{frame_uuid}/encoder_cache.json
```

The artifact contains frame uuid, session id, timestamp, and a fake embedding digest. It does not claim to be a real encoder cache.

The README should show a demo flow:

```bash
python examples/mock_primer_service.py --host 127.0.0.1 --port 18096 --cache-root /tmp/liveframegateway-ec
liveframegateway serve --host 127.0.0.1 --port 18095 --ring-size 1 \
  --primer-url http://127.0.0.1:18096/prime \
  --ec-shared-storage-path /tmp/liveframegateway-ec
```

Then ingest two frames and show that the first frame's cache directory is removed after ring overflow.

## Schema Cleanup

Core normalized fields stay top-level:

- `session_id`
- `frame_uuid`
- `frame_id`
- `ts_ms`
- `status`
- `source`
- `digest`
- `image_url`
- `device_id`
- `user_id`
- `seq`
- `pose_state`
- `motion_state`
- `quality`
- `robot_ext`

The previous specialized robot fields move into `robot_ext` during normalization:

- `behavior_chunk_id`
- `behavior_episode_id`
- `scan_plan_id`
- `scan_phase`
- `coverage_bin`
- `target_pose`

Backward compatibility requirement: existing clients may still send those fields at the top level. The server normalizes them into `robot_ext` in returned frames.

`FrameGatewayFrame` mirrors this structure by exposing `robot_ext` instead of top-level scan and behavior fields. Tests should verify backward-compatible ingest.

## Documentation

README updates:

- Add a top tagline: `Live Visual Context Infrastructure for Embodied Agents`.
- Add a visible boundary statement: `Not an encoder cache. Not a model proxy.`
- Add a short comparison with omni or realtime multimodal models: LiveFrameGateway complements them by managing live visual context before model calls.
- Add benchmark instructions and one local example output.
- Add selection policy examples.
- Add mock primer lifecycle demo.
- Update metadata examples to use `robot_ext`.

`docs/design.md` updates:

- Move originality positioning near the top.
- Document selection policies.
- Document benchmark scope and limitations.
- Document the schema cleanup.

## Testing

Add tests for:

- `selection.py` latest, quality, and motion behavior.
- service `/frames/select` route.
- client `select_frames()`.
- schema normalization from legacy top-level fields into `robot_ext`.
- mock primer helper functions where practical without starting a long-running process.
- benchmark smoke run with tiny input, verifying it exits and prints final JSON.

Full suite must pass with:

```bash
.venv/bin/pytest -q
```

CLI smoke checks must pass:

```bash
.venv/bin/liveframegateway --help
.venv/bin/python -m liveframegateway --help
```

## Acceptance Criteria

- Benchmark script exists and produces text plus final JSON metrics.
- README includes a benchmark result explicitly labeled as local example output.
- `/frames/select` supports `latest`, `quality`, and `motion`.
- Client supports `select_frames()`.
- Mock primer demo creates cache artifacts and ring eviction can remove them.
- Specialized robot metadata is returned under `robot_ext`.
- Existing `/frames/latest` and ingest APIs remain compatible.
- Tests cover the new behavior and pass.

## Deferred

- Real encoder-cache adapters.
- Async primer mode.
- Persistent frame store.
- Camera/WebRTC producer.
- Metrics endpoint.
- Auth or multi-tenant controls.
