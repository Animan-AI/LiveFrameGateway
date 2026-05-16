# Alpha2 Proof Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the alpha2 proof-oriented release for LiveFrameGateway with measured latency, non-trivial frame selection, a mock primer lifecycle demo, cleaner robot metadata schema, and stronger open-source positioning.

**Architecture:** Keep LiveFrameGateway backend-agnostic. Add selection as a pure policy module used by store/service/client, keep benchmark and mock primer as examples/tools outside the core package, and keep existing ingest/latest APIs compatible while moving specialized robot metadata into `robot_ext`.

**Tech Stack:** Python 3.10+, aiohttp, pytest, pytest-aiohttp, pytest-asyncio, dataclasses, argparse, standard-library subprocess/json/time/statistics.

---

## File Structure

- Modify `/home/meng/LiveFrameGateway/src/liveframegateway/models.py`: schema cleanup, `robot_ext` normalization, backward-compatible ingest for legacy robot fields.
- Modify `/home/meng/LiveFrameGateway/src/liveframegateway/store.py`: add `select_frames()` using policy functions while keeping `get_latest_frames()`.
- Create `/home/meng/LiveFrameGateway/src/liveframegateway/selection.py`: pure latest/quality/motion selection policies.
- Modify `/home/meng/LiveFrameGateway/src/liveframegateway/service.py`: add `/frames/select` route.
- Modify `/home/meng/LiveFrameGateway/src/liveframegateway/client.py`: replace specialized top-level robot fields with `robot_ext`, add `select_frames()`.
- Create `/home/meng/LiveFrameGateway/examples/mock_primer_service.py`: small aiohttp primer service that creates mock cache artifacts.
- Create `/home/meng/LiveFrameGateway/benchmarks/replay_latency.py`: synthetic replay benchmark with text and final JSON output.
- Modify `/home/meng/LiveFrameGateway/README.md`: alpha2 positioning, benchmark, selection, mock primer demo, metadata examples.
- Modify `/home/meng/LiveFrameGateway/docs/design.md`: alpha2 architecture details.
- Modify tests under `/home/meng/LiveFrameGateway/tests/`: schema, selection, service, client, mock primer, benchmark smoke tests.

## Task 1: Schema Cleanup

**Files:**
- Modify: `/home/meng/LiveFrameGateway/src/liveframegateway/models.py`
- Modify: `/home/meng/LiveFrameGateway/src/liveframegateway/client.py`
- Modify: `/home/meng/LiveFrameGateway/tests/test_store.py`
- Create: `/home/meng/LiveFrameGateway/tests/test_models.py`
- Modify: `/home/meng/LiveFrameGateway/tests/test_client.py`

- [ ] **Step 1: Write schema normalization tests**

Create `/home/meng/LiveFrameGateway/tests/test_models.py`:

```python
from liveframegateway.models import normalize_frame_payload


def test_normalize_moves_specialized_robot_fields_into_robot_ext():
    record = normalize_frame_payload(
        "sess",
        {
            "frame_uuid": "f1",
            "pose_state": {"body_yaw_deg": 12.5},
            "motion_state": {"speed": 0.3},
            "quality": {"blur_score": 0.2},
            "scan_phase": "sweep_left",
            "coverage_bin": "yaw_1",
            "behavior_episode_id": "episode_7",
            "target_pose": {"x": 1.0},
        },
    )

    payload = record.to_dict()
    assert payload["pose_state"]["body_yaw_deg"] == 12.5
    assert payload["motion_state"]["speed"] == 0.3
    assert payload["quality"]["blur_score"] == 0.2
    assert payload["robot_ext"] == {
        "scan_phase": "sweep_left",
        "coverage_bin": "yaw_1",
        "behavior_episode_id": "episode_7",
        "target_pose": {"x": 1.0},
    }
    assert "scan_phase" not in payload
    assert "coverage_bin" not in payload
    assert "behavior_episode_id" not in payload
    assert "target_pose" not in payload


def test_normalize_merges_existing_robot_ext_with_legacy_fields():
    record = normalize_frame_payload(
        "sess",
        {
            "frame_uuid": "f1",
            "robot_ext": {"custom": "value", "scan_phase": "from_ext"},
            "scan_phase": "from_legacy",
            "coverage_bin": "yaw_2",
        },
    )

    payload = record.to_dict()
    assert payload["robot_ext"] == {
        "custom": "value",
        "scan_phase": "from_legacy",
        "coverage_bin": "yaw_2",
    }
```

- [ ] **Step 2: Update store metadata test for `robot_ext`**

Replace `test_robot_metadata_survives_round_trip()` in `/home/meng/LiveFrameGateway/tests/test_store.py` with:

```python
def test_robot_metadata_survives_round_trip():
    async def run():
        store = FrameRingBufferStore(ring_size=2)
        await store.ingest(
            "sess",
            {
                "frame_uuid": "f1",
                "ts_ms": 1,
                "pose_state": {"body_yaw_deg": 12.5},
                "motion_state": {"speed": 0.4},
                "scan_phase": "sweep_left",
                "coverage_bin": "yaw_1",
                "quality": {"blur_score": 0.2},
            },
        )
        return await store.get_latest_frames("sess", limit=1)

    frames = asyncio.run(run())
    assert frames[0]["pose_state"]["body_yaw_deg"] == 12.5
    assert frames[0]["motion_state"]["speed"] == 0.4
    assert frames[0]["robot_ext"]["scan_phase"] == "sweep_left"
    assert frames[0]["robot_ext"]["coverage_bin"] == "yaw_1"
    assert frames[0]["quality"]["blur_score"] == 0.2
    assert "scan_phase" not in frames[0]
    assert "coverage_bin" not in frames[0]
```

- [ ] **Step 3: Update client schema test**

Append to `/home/meng/LiveFrameGateway/tests/test_client.py`:

```python

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
```

Also change the import at the top of `/home/meng/LiveFrameGateway/tests/test_client.py` to:

```python
from liveframegateway.client import FrameGatewayClient, FrameGatewayFrame
from liveframegateway.service import create_app
```

- [ ] **Step 4: Run schema tests and verify they fail**

Run:

```bash
cd /home/meng/LiveFrameGateway
.venv/bin/pytest tests/test_models.py tests/test_store.py::test_robot_metadata_survives_round_trip tests/test_client.py::test_frame_gateway_frame_uses_robot_ext -q
```

Expected:

- `test_normalize_moves_specialized_robot_fields_into_robot_ext` fails because legacy fields are still top-level.
- `test_frame_gateway_frame_uses_robot_ext` fails because `FrameGatewayFrame` has no `robot_ext`.

- [ ] **Step 5: Implement schema normalization**

Replace the metadata key constants and metadata construction in `/home/meng/LiveFrameGateway/src/liveframegateway/models.py` with:

```python
CORE_METADATA_KEYS = (
    "device_id",
    "user_id",
    "seq",
    "pose_state",
    "motion_state",
    "quality",
)

ROBOT_EXT_KEYS = (
    "behavior_chunk_id",
    "behavior_episode_id",
    "scan_plan_id",
    "scan_phase",
    "coverage_bin",
    "target_pose",
)
```

Inside `normalize_frame_payload()`, replace the current `metadata = {}` block with:

```python
    metadata = {}
    for key in CORE_METADATA_KEYS:
        value = payload.get(key)
        if value not in (None, "", [], {}):
            metadata[key] = deepcopy(value)

    robot_ext = {}
    if isinstance(payload.get("robot_ext"), dict):
        robot_ext.update(deepcopy(payload["robot_ext"]))
    for key in ROBOT_EXT_KEYS:
        value = payload.get(key)
        if value not in (None, "", [], {}):
            robot_ext[key] = deepcopy(value)
    if robot_ext:
        metadata["robot_ext"] = robot_ext
```

- [ ] **Step 6: Implement client `robot_ext` field**

In `/home/meng/LiveFrameGateway/src/liveframegateway/client.py`, replace these fields in `FrameGatewayFrame`:

```python
    behavior_chunk_id: str = ""
    behavior_episode_id: str = ""
    scan_plan_id: str = ""
    scan_phase: str = ""
    coverage_bin: str = ""
    target_pose: dict[str, Any] = field(default_factory=dict)
```

with:

```python
    robot_ext: dict[str, Any] = field(default_factory=dict)
```

In `FrameGatewayFrame.from_payload()`, replace these constructor arguments:

```python
            behavior_chunk_id=str(payload.get("behavior_chunk_id") or "").strip(),
            behavior_episode_id=str(payload.get("behavior_episode_id") or "").strip(),
            scan_plan_id=str(payload.get("scan_plan_id") or "").strip(),
            scan_phase=str(payload.get("scan_phase") or "").strip(),
            coverage_bin=str(payload.get("coverage_bin") or "").strip(),
            target_pose=dict(payload.get("target_pose") or {}) if isinstance(payload.get("target_pose"), dict) else {},
```

with:

```python
            robot_ext=dict(payload.get("robot_ext") or {}) if isinstance(payload.get("robot_ext"), dict) else {},
```

- [ ] **Step 7: Run schema tests and verify they pass**

Run:

```bash
cd /home/meng/LiveFrameGateway
.venv/bin/pytest tests/test_models.py tests/test_store.py tests/test_client.py::test_frame_gateway_frame_uses_robot_ext -q
```

Expected: all selected tests pass.

- [ ] **Step 8: Commit schema cleanup**

Run:

```bash
cd /home/meng/LiveFrameGateway
git add src/liveframegateway/models.py src/liveframegateway/client.py tests/test_models.py tests/test_store.py tests/test_client.py
git commit -m "feat: normalize robot metadata into robot_ext"
```

Expected: commit succeeds.

## Task 2: Frame Selection Policies

**Files:**
- Create: `/home/meng/LiveFrameGateway/src/liveframegateway/selection.py`
- Modify: `/home/meng/LiveFrameGateway/src/liveframegateway/store.py`
- Modify: `/home/meng/LiveFrameGateway/src/liveframegateway/service.py`
- Modify: `/home/meng/LiveFrameGateway/src/liveframegateway/client.py`
- Create: `/home/meng/LiveFrameGateway/tests/test_selection.py`
- Modify: `/home/meng/LiveFrameGateway/tests/test_service.py`
- Modify: `/home/meng/LiveFrameGateway/tests/test_client.py`

- [ ] **Step 1: Write selection policy tests**

Create `/home/meng/LiveFrameGateway/tests/test_selection.py`:

```python
from liveframegateway.selection import select_frames


FRAMES = [
    {"frame_uuid": "f1", "ts_ms": 1, "quality": {"blur_score": 0.9, "confidence": 0.4}},
    {"frame_uuid": "f2", "ts_ms": 2, "quality": {"blur_score": 0.1, "confidence": 0.8}},
    {"frame_uuid": "f3", "ts_ms": 3, "quality": {"blur_score": 0.2, "confidence": 0.9}},
    {"frame_uuid": "f4", "ts_ms": 4, "motion_state": {"speed": 0.0, "angular_speed": 0.0}},
    {"frame_uuid": "f5", "ts_ms": 5, "motion_state": {"speed": 0.2, "angular_speed": 0.0}},
]


def test_latest_policy_returns_latest_window_old_to_new():
    selected = select_frames(FRAMES, limit=2, policy="latest")
    assert [frame["frame_uuid"] for frame in selected] == ["f4", "f5"]


def test_quality_policy_prefers_low_blur_and_high_confidence_then_returns_chronological():
    selected = select_frames(FRAMES, limit=2, policy="quality")
    assert [frame["frame_uuid"] for frame in selected] == ["f2", "f3"]


def test_motion_policy_prefers_moving_frames_then_returns_chronological():
    selected = select_frames(FRAMES, limit=1, policy="motion", min_speed=0.01, min_angular_speed=0.01)
    assert [frame["frame_uuid"] for frame in selected] == ["f5"]


def test_motion_policy_falls_back_to_latest_when_no_motion_qualified_frames():
    frames = [
        {"frame_uuid": "f1", "ts_ms": 1, "motion_state": {"speed": 0.0}},
        {"frame_uuid": "f2", "ts_ms": 2, "motion_state": {"speed": 0.0}},
    ]
    selected = select_frames(frames, limit=1, policy="motion", min_speed=0.5, min_angular_speed=0.5)
    assert [frame["frame_uuid"] for frame in selected] == ["f2"]


def test_unknown_policy_uses_latest():
    selected = select_frames(FRAMES, limit=2, policy="unknown")
    assert [frame["frame_uuid"] for frame in selected] == ["f4", "f5"]
```

- [ ] **Step 2: Add service selection route test**

Append to `/home/meng/LiveFrameGateway/tests/test_service.py`:

```python

async def test_service_select_frames_by_quality(aiohttp_client):
    app = create_app(ring_size=5)
    client = await aiohttp_client(app)
    await client.post(
        "/sessions/sess/frames",
        json={"frame_uuid": "f1", "ts_ms": 1, "quality": {"blur_score": 0.9, "confidence": 0.2}},
    )
    await client.post(
        "/sessions/sess/frames",
        json={"frame_uuid": "f2", "ts_ms": 2, "quality": {"blur_score": 0.1, "confidence": 0.8}},
    )
    await client.post(
        "/sessions/sess/frames",
        json={"frame_uuid": "f3", "ts_ms": 3, "quality": {"blur_score": 0.2, "confidence": 0.9}},
    )

    resp = await client.get("/sessions/sess/frames/select", params={"limit": "2", "policy": "quality"})

    assert resp.status == 200
    payload = await resp.json()
    assert payload["policy"] == "quality"
    assert [frame["frame_uuid"] for frame in payload["frames"]] == ["f2", "f3"]
```

- [ ] **Step 3: Add client selection test**

Append to `/home/meng/LiveFrameGateway/tests/test_client.py`:

```python

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
```

- [ ] **Step 4: Run selection tests and verify they fail**

Run:

```bash
cd /home/meng/LiveFrameGateway
.venv/bin/pytest tests/test_selection.py tests/test_service.py::test_service_select_frames_by_quality tests/test_client.py::test_client_select_frames -q
```

Expected:

- import failure for `liveframegateway.selection`
- service route test returns 404 or import failure
- client test fails because `select_frames()` does not exist

- [ ] **Step 5: Implement selection policy module**

Create `/home/meng/LiveFrameGateway/src/liveframegateway/selection.py`:

```python
from __future__ import annotations

from typing import Any


def select_frames(
    frames: list[dict[str, Any]],
    *,
    limit: int = 1,
    policy: str = "latest",
    min_speed: float = 0.01,
    min_angular_speed: float = 0.01,
) -> list[dict[str, Any]]:
    effective_limit = max(1, int(limit or 1))
    normalized_policy = str(policy or "latest").strip().lower()
    candidates = [frame for frame in frames or [] if isinstance(frame, dict)]
    if normalized_policy == "quality":
        return _select_quality(candidates, effective_limit)
    if normalized_policy == "motion":
        return _select_motion(candidates, effective_limit, min_speed=min_speed, min_angular_speed=min_angular_speed)
    return _select_latest(candidates, effective_limit)


def _select_latest(frames: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    return frames[-limit:]


def _select_quality(frames: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    ranked = sorted(frames, key=lambda frame: (_blur_score(frame), -_confidence(frame), _timestamp(frame)))
    return sorted(ranked[:limit], key=_timestamp)


def _select_motion(
    frames: list[dict[str, Any]],
    limit: int,
    *,
    min_speed: float,
    min_angular_speed: float,
) -> list[dict[str, Any]]:
    moving = [
        frame
        for frame in frames
        if _motion_speed(frame) >= float(min_speed) or _motion_angular_speed(frame) >= float(min_angular_speed)
    ]
    if not moving:
        return _select_latest(frames, limit)
    ranked = sorted(moving, key=lambda frame: max(_motion_speed(frame), _motion_angular_speed(frame)), reverse=True)
    return sorted(ranked[:limit], key=_timestamp)


def _timestamp(frame: dict[str, Any]) -> int:
    try:
        return int(frame.get("ts_ms") or 0)
    except (TypeError, ValueError):
        return 0


def _blur_score(frame: dict[str, Any]) -> float:
    quality = frame.get("quality")
    if not isinstance(quality, dict):
        return 1.0
    try:
        return float(quality.get("blur_score", 1.0))
    except (TypeError, ValueError):
        return 1.0


def _confidence(frame: dict[str, Any]) -> float:
    quality = frame.get("quality")
    if not isinstance(quality, dict):
        return 0.0
    try:
        return float(quality.get("confidence", 0.0))
    except (TypeError, ValueError):
        return 0.0


def _motion_speed(frame: dict[str, Any]) -> float:
    motion = frame.get("motion_state")
    if not isinstance(motion, dict):
        return 0.0
    try:
        return abs(float(motion.get("speed", 0.0)))
    except (TypeError, ValueError):
        return 0.0


def _motion_angular_speed(frame: dict[str, Any]) -> float:
    motion = frame.get("motion_state")
    if not isinstance(motion, dict):
        return 0.0
    try:
        return abs(float(motion.get("angular_speed", 0.0)))
    except (TypeError, ValueError):
        return 0.0
```

- [ ] **Step 6: Add store `select_frames()`**

In `/home/meng/LiveFrameGateway/src/liveframegateway/store.py`, add import:

```python
from .selection import select_frames
```

Add this method to `FrameRingBufferStore` after `get_latest_frames()`:

```python
    async def select_frames(
        self,
        session_id: str,
        limit: int = 1,
        status: str = "ready",
        policy: str = "latest",
        min_speed: float = 0.01,
        min_angular_speed: float = 0.01,
    ) -> list[dict[str, Any]]:
        normalized_session_id = str(session_id or "").strip()
        if not normalized_session_id:
            return []
        normalized_status = str(status or "").strip().lower()
        async with self._lock:
            bucket = [item.to_dict() for item in self._sessions.get(normalized_session_id, ())]
        if normalized_status:
            bucket = [item for item in bucket if item.get("status") == normalized_status]
        return select_frames(
            bucket,
            limit=limit,
            policy=policy,
            min_speed=min_speed,
            min_angular_speed=min_angular_speed,
        )
```

- [ ] **Step 7: Add service route**

In `/home/meng/LiveFrameGateway/src/liveframegateway/service.py`, add this handler after `latest()`:

```python
    async def select(request: web.Request) -> web.Response:
        session_id = str(request.match_info.get("session_id") or "").strip()
        try:
            limit = max(1, int(request.query.get("limit", "1")))
        except (TypeError, ValueError):
            limit = 1
        try:
            min_speed = float(request.query.get("min_speed", "0.01"))
        except (TypeError, ValueError):
            min_speed = 0.01
        try:
            min_angular_speed = float(request.query.get("min_angular_speed", "0.01"))
        except (TypeError, ValueError):
            min_angular_speed = 0.01
        status = str(request.query.get("status", "ready") or "ready").strip()
        policy = str(request.query.get("policy", "latest") or "latest").strip()
        frames = await request.app[FRAME_STORE_KEY].select_frames(
            session_id,
            limit=limit,
            status=status,
            policy=policy,
            min_speed=min_speed,
            min_angular_speed=min_angular_speed,
        )
        return web.json_response({"policy": policy, "frames": frames})
```

Register the route after the latest route:

```python
    app.router.add_get("/sessions/{session_id}/frames/select", select)
```

- [ ] **Step 8: Add client `select_frames()`**

In `/home/meng/LiveFrameGateway/src/liveframegateway/client.py`, add this method after `get_latest_frames()`:

```python
    async def select_frames(
        self,
        session_id: str,
        n: int = 1,
        policy: str = "latest",
        status: str = "ready",
        min_speed: float = 0.01,
        min_angular_speed: float = 0.01,
    ) -> list[FrameGatewayFrame]:
        session = await self._get_session()
        async with session.get(
            f"{self.base_url}/sessions/{session_id}/frames/select",
            params={
                "limit": max(1, int(n or 1)),
                "policy": policy,
                "status": status,
                "min_speed": min_speed,
                "min_angular_speed": min_angular_speed,
            },
        ) as resp:
            if resp.status != 200:
                return []
            data = await resp.json()
        raw_frames = data.get("frames", []) if isinstance(data, dict) else []
        return [FrameGatewayFrame.from_payload(item) for item in raw_frames if isinstance(item, dict)]
```

- [ ] **Step 9: Run selection tests and verify they pass**

Run:

```bash
cd /home/meng/LiveFrameGateway
.venv/bin/pytest tests/test_selection.py tests/test_service.py::test_service_select_frames_by_quality tests/test_client.py::test_client_select_frames -q
```

Expected: all selected tests pass.

- [ ] **Step 10: Commit selection policies**

Run:

```bash
cd /home/meng/LiveFrameGateway
git add src/liveframegateway/selection.py src/liveframegateway/store.py src/liveframegateway/service.py src/liveframegateway/client.py tests/test_selection.py tests/test_service.py tests/test_client.py
git commit -m "feat: add frame selection policies"
```

Expected: commit succeeds.

## Task 3: Mock Primer Lifecycle Example

**Files:**
- Create: `/home/meng/LiveFrameGateway/examples/mock_primer_service.py`
- Create: `/home/meng/LiveFrameGateway/tests/test_mock_primer_service.py`

- [ ] **Step 1: Write mock primer tests**

Create `/home/meng/LiveFrameGateway/tests/test_mock_primer_service.py`:

```python
import json
from pathlib import Path

from examples.mock_primer_service import build_cache_artifact, sanitize_cache_name


def test_sanitize_cache_name_rejects_path_separators():
    assert sanitize_cache_name("sess/../frame") == "sess_.._frame"
    assert sanitize_cache_name("sess::frame") == "sess::frame"


def test_build_cache_artifact_creates_encoder_cache_json(tmp_path: Path):
    frame = {"frame_uuid": "f1", "ts_ms": 123, "image_url": "data:image/jpeg;base64,abc"}

    artifact_path = build_cache_artifact(tmp_path, "sess", frame)

    assert artifact_path == tmp_path / "sess::f1" / "encoder_cache.json"
    payload = json.loads(artifact_path.read_text())
    assert payload["session_id"] == "sess"
    assert payload["frame_uuid"] == "f1"
    assert payload["ts_ms"] == 123
    assert payload["kind"] == "mock_encoder_cache"
    assert payload["embedding_digest"]
```

- [ ] **Step 2: Run mock primer tests and verify they fail**

Run:

```bash
cd /home/meng/LiveFrameGateway
.venv/bin/pytest tests/test_mock_primer_service.py -q
```

Expected: import failure because `examples/mock_primer_service.py` does not exist.

- [ ] **Step 3: Implement mock primer service**

Create `/home/meng/LiveFrameGateway/examples/mock_primer_service.py`:

```python
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path
from typing import Any

from aiohttp import web


def sanitize_cache_name(value: str) -> str:
    return str(value or "").replace("/", "_").replace("\\", "_")


def build_cache_artifact(cache_root: Path, session_id: str, frame: dict[str, Any]) -> Path:
    frame_uuid = str(frame.get("frame_uuid") or frame.get("uuid") or "").strip()
    if not frame_uuid:
        raise ValueError("frame_uuid is required")
    safe_name = sanitize_cache_name(f"{session_id}::{frame_uuid}")
    artifact_dir = cache_root / safe_name
    artifact_dir.mkdir(parents=True, exist_ok=True)
    image_url = str(frame.get("image_url") or "")
    digest = hashlib.sha256(image_url.encode("utf-8")).hexdigest()
    payload = {
        "kind": "mock_encoder_cache",
        "session_id": session_id,
        "frame_uuid": frame_uuid,
        "ts_ms": int(frame.get("ts_ms") or 0),
        "created_at_ms": int(time.time() * 1000),
        "embedding_digest": digest,
    }
    artifact_path = artifact_dir / "encoder_cache.json"
    artifact_path.write_text(json.dumps(payload, indent=2, sort_keys=True))
    return artifact_path


def create_app(cache_root: Path) -> web.Application:
    app = web.Application()
    cache_root = Path(cache_root).expanduser().resolve()

    async def health(_request: web.Request) -> web.Response:
        return web.json_response({"status": "ok"})

    async def prime(request: web.Request) -> web.Response:
        try:
            payload = await request.json()
            if not isinstance(payload, dict):
                payload = {}
            session_id = str(payload.get("session_id") or "").strip()
            frame = payload.get("frame") if isinstance(payload.get("frame"), dict) else {}
            if not session_id:
                raise ValueError("session_id is required")
            artifact_path = build_cache_artifact(cache_root, session_id, frame)
        except ValueError as exc:
            return web.json_response({"status": "failed", "error": str(exc)}, status=400)
        return web.json_response({"status": "ready", "mock_cache_path": str(artifact_path)})

    app.router.add_get("/health", health)
    app.router.add_post("/prime", prime)
    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="Mock LiveFrameGateway primer service")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=18096)
    parser.add_argument("--cache-root", default="/tmp/liveframegateway-ec")
    args = parser.parse_args()
    web.run_app(create_app(Path(args.cache_root)), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run mock primer tests and verify they pass**

Run:

```bash
cd /home/meng/LiveFrameGateway
.venv/bin/pytest tests/test_mock_primer_service.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit mock primer example**

Run:

```bash
cd /home/meng/LiveFrameGateway
git add examples/mock_primer_service.py tests/test_mock_primer_service.py
git commit -m "feat: add mock primer lifecycle example"
```

Expected: commit succeeds.

## Task 4: Replay Latency Benchmark

**Files:**
- Create: `/home/meng/LiveFrameGateway/benchmarks/replay_latency.py`
- Create: `/home/meng/LiveFrameGateway/tests/test_benchmark.py`

- [ ] **Step 1: Write benchmark smoke test**

Create `/home/meng/LiveFrameGateway/tests/test_benchmark.py`:

```python
import json
import subprocess
import sys
from pathlib import Path


def test_replay_latency_benchmark_smoke_outputs_final_json():
    root = Path(__file__).resolve().parents[1]
    proc = subprocess.run(
        [
            sys.executable,
            str(root / "benchmarks" / "replay_latency.py"),
            "--frames",
            "8",
            "--queries",
            "3",
            "--frame-bytes",
            "128",
            "--select-k",
            "2",
            "--policy",
            "quality",
        ],
        cwd=root,
        text=True,
        capture_output=True,
        check=True,
    )

    final_line = proc.stdout.strip().splitlines()[-1]
    payload = json.loads(final_line)
    assert payload["frames"] == 8
    assert payload["queries"] == 3
    assert payload["policy"] == "quality"
    for key in [
        "inline_request_prep_ms_p50",
        "inline_request_prep_ms_p95",
        "gateway_request_prep_ms_p50",
        "gateway_request_prep_ms_p95",
        "gateway_fetch_ms_p50",
        "gateway_fetch_ms_p95",
        "selected_frame_age_ms_p50",
        "selected_frame_age_ms_p95",
    ]:
        assert key in payload
        assert payload[key] >= 0.0
```

- [ ] **Step 2: Run benchmark smoke test and verify it fails**

Run:

```bash
cd /home/meng/LiveFrameGateway
.venv/bin/pytest tests/test_benchmark.py -q
```

Expected: subprocess fails because `benchmarks/replay_latency.py` does not exist.

- [ ] **Step 3: Implement benchmark script**

Create directory:

```bash
cd /home/meng/LiveFrameGateway
mkdir -p benchmarks
```

Create `/home/meng/LiveFrameGateway/benchmarks/replay_latency.py`:

```python
from __future__ import annotations

import argparse
import asyncio
import base64
import json
import statistics
import time
from typing import Any

from aiohttp.test_utils import TestClient, TestServer

from liveframegateway.injection import inject_openai_messages
from liveframegateway.models import normalize_frame_payload
from liveframegateway.selection import select_frames
from liveframegateway.service import create_app


def make_frames(count: int, frame_bytes: int, fps: float, session_id: str) -> list[dict[str, Any]]:
    frame_interval_ms = int(1000.0 / max(1.0, fps))
    base_ts_ms = int(time.time() * 1000) - count * frame_interval_ms
    image_base64 = base64.b64encode(b"x" * max(1, frame_bytes)).decode("ascii")
    frames = []
    for idx in range(count):
        frames.append(
            {
                "frame_uuid": f"frame_{idx:06d}",
                "ts_ms": base_ts_ms + idx * frame_interval_ms,
                "image_base64": image_base64,
                "pose_state": {"body_yaw_deg": float(idx % 360)},
                "motion_state": {"speed": float(idx % 3) * 0.05, "angular_speed": float(idx % 5) * 0.02},
                "quality": {"blur_score": float((idx * 7) % 100) / 100.0, "confidence": 1.0 - float(idx % 10) / 20.0},
                "robot_ext": {"scan_phase": "replay"},
            }
        )
    return frames


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((pct / 100.0) * (len(ordered) - 1)))))
    return ordered[index]


def summarize(values: list[float]) -> tuple[float, float]:
    return percentile(values, 50), percentile(values, 95)


def inline_prepare(
    raw_frames: list[dict[str, Any]],
    *,
    session_id: str,
    select_k: int,
    policy: str,
    user_text: str,
) -> tuple[list[dict[str, Any]], float]:
    normalized = [normalize_frame_payload(session_id, frame).to_dict() for frame in raw_frames]
    selected = select_frames(normalized, limit=select_k, policy=policy)
    messages = inject_openai_messages([], selected, user_text)
    frame_age_ms = selected_frame_age_ms(selected)
    return messages, frame_age_ms


async def gateway_prepare(
    client: TestClient,
    *,
    session_id: str,
    select_k: int,
    policy: str,
    user_text: str,
) -> tuple[list[dict[str, Any]], float, float]:
    started = time.perf_counter()
    resp = await client.get(
        f"/sessions/{session_id}/frames/select",
        params={"limit": str(select_k), "policy": policy, "status": "ready"},
    )
    fetch_ms = (time.perf_counter() - started) * 1000.0
    payload = await resp.json()
    frames = payload.get("frames", []) if isinstance(payload, dict) else []
    messages = inject_openai_messages([], frames, user_text)
    frame_age_ms = selected_frame_age_ms(frames)
    return messages, fetch_ms, frame_age_ms


def selected_frame_age_ms(frames: list[dict[str, Any]]) -> float:
    if not frames:
        return 0.0
    now_ms = int(time.time() * 1000)
    newest_ts = max(int(frame.get("ts_ms") or 0) for frame in frames)
    return float(max(0, now_ms - newest_ts))


async def run_benchmark(args: argparse.Namespace) -> dict[str, Any]:
    frames = make_frames(args.frames, args.frame_bytes, args.fps, args.session_id)
    app = create_app(ring_size=max(args.frames, args.select_k))
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()
    try:
        for frame in frames:
            resp = await client.post(f"/sessions/{args.session_id}/frames", json=frame)
            if resp.status != 200:
                raise RuntimeError(f"ingest failed with status {resp.status}")

        inline_ms = []
        gateway_ms = []
        gateway_fetch_ms = []
        selected_age_ms = []
        for query_idx in range(args.queries):
            user_text = f"What changed in query {query_idx}?"

            started = time.perf_counter()
            inline_prepare(
                frames,
                session_id=args.session_id,
                select_k=args.select_k,
                policy=args.policy,
                user_text=user_text,
            )
            inline_ms.append((time.perf_counter() - started) * 1000.0)

            started = time.perf_counter()
            _messages, fetch_ms, age_ms = await gateway_prepare(
                client,
                session_id=args.session_id,
                select_k=args.select_k,
                policy=args.policy,
                user_text=user_text,
            )
            gateway_ms.append((time.perf_counter() - started) * 1000.0)
            gateway_fetch_ms.append(fetch_ms)
            selected_age_ms.append(age_ms)
    finally:
        await client.close()

    inline_p50, inline_p95 = summarize(inline_ms)
    gateway_p50, gateway_p95 = summarize(gateway_ms)
    fetch_p50, fetch_p95 = summarize(gateway_fetch_ms)
    age_p50, age_p95 = summarize(selected_age_ms)
    return {
        "frames": args.frames,
        "queries": args.queries,
        "frame_bytes": args.frame_bytes,
        "fps": args.fps,
        "select_k": args.select_k,
        "policy": args.policy,
        "inline_request_prep_ms_p50": inline_p50,
        "inline_request_prep_ms_p95": inline_p95,
        "gateway_request_prep_ms_p50": gateway_p50,
        "gateway_request_prep_ms_p95": gateway_p95,
        "gateway_fetch_ms_p50": fetch_p50,
        "gateway_fetch_ms_p95": fetch_p95,
        "selected_frame_age_ms_p50": age_p50,
        "selected_frame_age_ms_p95": age_p95,
        "note": "Synthetic local request-preparation benchmark; not a model latency benchmark.",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay latency benchmark for LiveFrameGateway")
    parser.add_argument("--frames", type=int, default=120)
    parser.add_argument("--queries", type=int, default=20)
    parser.add_argument("--frame-bytes", type=int, default=4096)
    parser.add_argument("--fps", type=float, default=10.0)
    parser.add_argument("--session-id", default="bench")
    parser.add_argument("--select-k", type=int, default=3)
    parser.add_argument("--policy", default="latest", choices=["latest", "quality", "motion"])
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = asyncio.run(run_benchmark(args))
    print("LiveFrameGateway synthetic replay benchmark")
    print(f"frames={result['frames']} queries={result['queries']} select_k={result['select_k']} policy={result['policy']}")
    print(f"inline request prep p50/p95: {result['inline_request_prep_ms_p50']:.3f} / {result['inline_request_prep_ms_p95']:.3f} ms")
    print(f"gateway request prep p50/p95: {result['gateway_request_prep_ms_p50']:.3f} / {result['gateway_request_prep_ms_p95']:.3f} ms")
    print(f"gateway fetch p50/p95: {result['gateway_fetch_ms_p50']:.3f} / {result['gateway_fetch_ms_p95']:.3f} ms")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run benchmark smoke test and verify it passes**

Run:

```bash
cd /home/meng/LiveFrameGateway
.venv/bin/pytest tests/test_benchmark.py -q
```

Expected: test passes.

- [ ] **Step 5: Run benchmark manually for README numbers**

Run:

```bash
cd /home/meng/LiveFrameGateway
.venv/bin/python benchmarks/replay_latency.py --frames 120 --queries 20 --frame-bytes 4096 --select-k 3 --policy quality
```

Expected: command prints human-readable lines and final JSON. Save the human-readable p50/p95 values for Task 5 README update.

- [ ] **Step 6: Commit benchmark**

Run:

```bash
cd /home/meng/LiveFrameGateway
git add benchmarks/replay_latency.py tests/test_benchmark.py
git commit -m "feat: add replay latency benchmark"
```

Expected: commit succeeds.

## Task 5: Documentation Repositioning

**Files:**
- Modify: `/home/meng/LiveFrameGateway/README.md`
- Modify: `/home/meng/LiveFrameGateway/docs/design.md`

- [ ] **Step 1: Rewrite README top positioning**

Edit the top of `/home/meng/LiveFrameGateway/README.md` so the first section is:

```markdown
# LiveFrameGateway

**Live Visual Context Infrastructure for Embodied Agents.**

LiveFrameGateway is a lightweight, backend-agnostic frame lifecycle layer for real-time VLM and embodied-agent applications.

**Not an encoder cache. Not a model proxy.** It manages live visual context before a model call: capture, normalize, retain, select, prime, evict, and inject frames so the user's question path does less work.
```

- [ ] **Step 2: Add omni/realtime multimodal comparison**

Add this section after `## Why This Exists`:

```markdown
## How It Relates To Omni Or Realtime Multimodal Models

Omni and realtime multimodal models are strong at low-latency conversation and model-side audio/visual understanding. LiveFrameGateway is complementary infrastructure: it manages which live frames are available, ready, selected, traceable, and attached before the model call.

For embodied agents, the useful boundary is not "another chat model." The boundary is a live visual context layer that can preserve pose, motion, quality, and robot-specific observation metadata while staying independent of the model backend.
```

- [ ] **Step 3: Update metadata examples**

In README API field list, replace specialized top-level robot fields:

```markdown
- `behavior_chunk_id`
- `behavior_episode_id`
- `scan_plan_id`
- `scan_phase`
- `coverage_bin`
- `target_pose`
```

with:

```markdown
- `robot_ext`: optional extension object for robot-specific fields such as `scan_phase`, `coverage_bin`, `target_pose`, and `behavior_episode_id`
```

- [ ] **Step 4: Add selection policy docs**

Add after latest-frame docs:

````markdown
## Select Frames By Policy

```bash
curl -s 'http://127.0.0.1:8095/sessions/demo/frames/select?limit=2&policy=quality'
```

Supported policies:

- `latest`: latest K ready frames
- `quality`: prefers low `quality.blur_score` and high `quality.confidence`
- `motion`: prefers frames where `motion_state.speed` or `motion_state.angular_speed` exceeds a threshold
````

When editing, keep the markdown fences balanced as plain markdown.

- [ ] **Step 5: Add benchmark docs**

Add a benchmark section:

````markdown
## Benchmark

Run a synthetic replay benchmark:

```bash
python benchmarks/replay_latency.py --frames 120 --queries 20 --frame-bytes 4096 --select-k 3 --policy quality
```

Example local output from this repository:

```text
LiveFrameGateway synthetic replay benchmark
frames=120 queries=20 select_k=3 policy=quality
inline request prep p50/p95: <INLINE_P50> / <INLINE_P95> ms
gateway request prep p50/p95: <GATEWAY_P50> / <GATEWAY_P95> ms
gateway fetch p50/p95: <FETCH_P50> / <FETCH_P95> ms
```

This is a synthetic request-preparation benchmark, not a model latency benchmark. Its purpose is to measure how much work can be moved out of the user question path before a VLM call.
````

Replace `<INLINE_P50>`, `<INLINE_P95>`, `<GATEWAY_P50>`, `<GATEWAY_P95>`, `<FETCH_P50>`, and `<FETCH_P95>` with values from Task 4 Step 5.

- [ ] **Step 6: Add mock primer docs**

Add:

````markdown
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
````

When editing, keep the markdown fences balanced as plain markdown.

- [ ] **Step 7: Update design doc**

Edit `/home/meng/LiveFrameGateway/docs/design.md`:

- Move the `Originality Positioning` section immediately after `Purpose`.
- Add a `Selection Policies` subsection under `Architecture` with the latest/quality/motion behavior from the spec.
- Add a `Benchmark Scope` subsection explaining that the benchmark is synthetic request-preparation latency, not model latency.
- Update schema references so specialized robot fields are described as `robot_ext`.

- [ ] **Step 8: Verify markdown content**

Run:

```bash
cd /home/meng/LiveFrameGateway
rg -n "Not an encoder cache|frames/select|Benchmark|robot_ext|Omni" README.md docs/design.md
```

Expected: matches appear in both README and design docs.

- [ ] **Step 9: Commit documentation**

Run:

```bash
cd /home/meng/LiveFrameGateway
git add README.md docs/design.md
git commit -m "docs: reposition alpha2 proof release"
```

Expected: commit succeeds.

## Task 6: Full Verification

**Files:**
- No new source files expected.

- [ ] **Step 1: Run full test suite**

Run:

```bash
cd /home/meng/LiveFrameGateway
.venv/bin/pytest -q
```

Expected: all tests pass.

- [ ] **Step 2: Run CLI help checks**

Run:

```bash
cd /home/meng/LiveFrameGateway
.venv/bin/liveframegateway --help
.venv/bin/python -m liveframegateway --help
```

Expected: both commands print help and exit with status 0.

- [ ] **Step 3: Run benchmark smoke manually**

Run:

```bash
cd /home/meng/LiveFrameGateway
.venv/bin/python benchmarks/replay_latency.py --frames 8 --queries 3 --frame-bytes 128 --select-k 2 --policy quality
```

Expected: output ends with JSON containing `"frames": 8`, `"queries": 3`, and `"policy": "quality"`.

- [ ] **Step 4: Smoke-test service selection route**

Start service:

```bash
cd /home/meng/LiveFrameGateway
.venv/bin/liveframegateway serve --host 127.0.0.1 --port 19095 --ring-size 3
```

In another terminal:

```bash
curl -s http://127.0.0.1:19095/sessions/demo/frames \
  -H 'content-type: application/json' \
  -d '{"frame_uuid":"f1","quality":{"blur_score":0.8}}'
curl -s http://127.0.0.1:19095/sessions/demo/frames \
  -H 'content-type: application/json' \
  -d '{"frame_uuid":"f2","quality":{"blur_score":0.1}}'
curl -s 'http://127.0.0.1:19095/sessions/demo/frames/select?limit=1&policy=quality'
```

Expected: selection response contains one frame with `"frame_uuid": "f2"`.

- [ ] **Step 5: Stop smoke-test service**

Stop the process started in Step 4 with `Ctrl-C` or `kill <pid>`.

Expected: port `19095` is no longer listening.

- [ ] **Step 6: Verify git status**

Run:

```bash
cd /home/meng/LiveFrameGateway
git status --short
git log --oneline --decorate -8
```

Expected: working tree is clean and recent commits include schema, selection, mock primer, benchmark, and docs.

## Self-Review

- Spec coverage: Tasks cover benchmark, latest/quality/motion selection, mock primer lifecycle, `robot_ext` schema cleanup, README/design repositioning, and final verification.
- Compatibility: Existing `/frames/latest` and ingest routes remain in place; legacy specialized robot fields are accepted and normalized into `robot_ext`.
- Test coverage: New behavior has tests for models, store, selection, service, client, mock primer helpers, and benchmark smoke.
- Scope control: Real encoder caches, model proxying, WebRTC, persistent stores, and auth remain deferred.
