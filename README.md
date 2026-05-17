# 🚀 LiveFrameGateway

[🇨🇳 简体中文](README.zh-CN.md) | [🇺🇸 English](README.md)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

**The "Visual Context Layer" for VLMs and Embodied Agents.**

LiveFrameGateway is a lightweight, backend-agnostic infrastructure that manages the lifecycle of live camera frames. It bridges the gap between raw video streams and multimodal LLMs by maintaining a high-performance "ready-frame" buffer.

### ⚡ Why LiveFrameGateway?

In traditional VLM interactions, the visual path starts *only after* the user asks a question, leading to high latency:
> `Question` ➔ `Capture` ➔ `Upload` ➔ `Encode` ➔ `VLM Inference` ➔ `Answer` (🐢 Slow)

LiveFrameGateway moves the heavy lifting **ahead of the question**:
> `Stream` ➔ `Continuous Prep (Normalize/Prime)` ➔ `Ring Buffer`
>
> `Question` ➔ `Instant Fetch` ➔ `VLM Inference` ➔ `Answer` (🚀 Fast)

---

## 🤖 vs. Realtime Audio/Video Models & Voice Agents

Is this a competitor to modern realtime multimodal systems such as **Gemini Live API**, **OpenAI Realtime API** (`gpt-realtime`), **MiniCPM-o 4.5**, or **Qwen2.5-Omni**? **No, it is infrastructure.**

Those systems are model/API layers for low-latency interaction: depending on the provider, they handle speech-to-speech, audio/video streams, image inputs, text, and streamed responses. LiveFrameGateway is the **visual context lifecycle layer** around them: it keeps robot camera frames ready, traceable, selectable, and injectable before the model call.

| Feature | Realtime Audio/Video Models & APIs | LiveFrameGateway Approach |
| :--- | :--- | :--- |
| **Role** | End-to-end interactive model/runtime | Backend-agnostic visual context infrastructure |
| **Realtime focus** | Streaming audio/video/text I/O and spoken responses | Pre-question frame readiness, selection, and injection |
| **Visual input** | Provider/model-defined live stream or sampled frames | Explicit ready-frame ring with stable `frame_uuid` |
| **Metadata** | Usually model input payload only | Pixels + **Robot State** (pose, motion, quality, scan metadata) |
| **Control** | Optimized for conversational immediacy | Optimized for robotics traceability, cache priming, and frame lifecycle |
| **Compatibility** | Provider/model-specific | Works beside vLLM, SGLang, hosted VLMs, and realtime APIs |

---

## ✨ Key Features

- 🔄 **Smart Ring Buffers**: Per-session bounded buffers for live frames with automatic eviction.
- 🎯 **Intelligent Selection**: Retrieve the "best" frames using policies like `latest`, `quality`, or `motion`.
- 🧩 **Seamless Injection**: One-line integration to format frames for OpenAI-compatible multimodal APIs.
- 🤖 **Robot-First**: Built-in support for pose, motion, and scan metadata, essential for embodied intelligence.
- 🔌 **Primer Hooks**: Call external services (e.g., ViT encoders) as frames arrive to pre-warm the cache.
- 📏 **Latency Benchmarks**: Tools to measure and prove your latency savings.

---

## 🏗️ Architecture

```text
  [ Frame Producer ]            [ LiveFrameGateway ]             [ Agent / VLM ]
 (Robot/Camera/App)            (Sidecar / Service)             (Consumer App)
         |                             |                              |
         | --- POST /frames ---------> |                              |
         |                             | --- (Optional) Primer ---->  |
         |                             |                              |
         |                             | <--- GET /select /latest --- |
         |                             |                              |
         |                             | --- OpenAI Multimodal Msg -> |
```

---

## 🚀 Quick Start

### 1. Install
```bash
pip install "liveframegateway[dev] @ git+https://github.com/Animan-AI/LiveFrameGateway.git"
```

### 2. Start the Gateway
```bash
liveframegateway serve --port 8095 --ring-size 20
```

### 3. Push a Frame
```bash
curl -X POST http://127.0.0.1:8095/sessions/demo/frames \
  -H 'Content-Type: application/json' \
  -d '{
    "frame_uuid": "f1",
    "image_base64": "...",
    "quality": {"blur_score": 0.05, "confidence": 0.98}
  }'
```

### 4. Use in Python
```python
from liveframegateway.injection import inject_openai_messages
import requests

# Fetch selected frames from the gateway
frames = requests.get(
    "http://127.0.0.1:8095/sessions/demo/frames/select?policy=quality"
).json()["frames"]

# Inject into OpenAI-compatible messages
messages = inject_openai_messages(
    messages=[{"role": "system", "content": "You are a robot assistant."}],
    frames=frames,
    user_text="What do you see?"
)
```

---

## 🔍 Selection Policies

- **`latest`**: Default. Gets the most recent N frames.
- **`quality`**: Selects frames with the highest quality scores (confidence - blur).
- **`motion`**: Selects frames where the robot was moving (based on speed thresholds).

---

## 📊 Measuring Impact

Use the built-in probes to measure your own stack:

```bash
# 🧪 Request preparation overhead
python benchmarks/replay_latency.py --frames 120 --select-k 3

# ⚡ Server-side question path against an OpenAI-compatible VLM
python benchmarks/question_path_latency_probe.py \
  --gateway-base-url http://127.0.0.1:8095 \
  --consumer-base-url http://127.0.0.1:8201/v1 \
  --model your-model-name \
  --session-id your-session-id
```

### 🧪 Live Setup

One live robotics deployment run on `2026-05-17`:

| Item | Value |
| :--- | :--- |
| 📷 Device stream | Orange Pi camera frames |
| 🔄 Gateway mode | ready-frame ring + external encoder primer |
| 🧠 VLM backend | local vLLM OpenAI-compatible server |
| 🏷️ Model | `qwen36-35b-a3b-awq` |
| 🔁 Iterations | `10` |

### ⚡ Measured Result

| Metric | Traditional direct image | Ready-frame path | Delta |
| :--- | ---: | ---: | ---: |
| Server-side TTFT p50 | `283.0 ms` | `228.8 ms` | `-54.9 ms` |
| Server-side TTFT p95 | `341.3 ms` | `243.1 ms` | `-98.2 ms` |
| Total VLM request p50 | `301.5 ms` | `248.4 ms` | `-53.1 ms` |
| Latest-frame fetch p50 | N/A | `~2.3 ms` | N/A |

### 🔧 Preparation Cost

| Preparation stage | p50 | p95 | Source |
| :--- | ---: | ---: | :--- |
| Device frame timestamp -> server ingest | `57 ms` | `72 ms` | last 120 private deployment ingest logs |
| Device frame timestamp -> external encoder-cache file ready | `134 ms` | `157 ms` | recent encoder-cache artifacts |

### 🧮 Estimated Perceived TTFT

LiveFrameGateway does not need a second "should we take a photo?" decision. Visual context is already maintained, so the ready-frame path can select and inject frames directly.

```text
🐢 Photo-on-demand
   ~= photo/vision intent routing + capture/upload + direct VLM TTFT
   ~= R_photo_route + 57 ms + 283 ms
   ~= R_photo_route + 340 ms

🚀 Ready-frame
   ~= latest-frame fetch + ready-frame VLM TTFT
   ~= 2 ms + 229 ms
   ~= 231 ms

✅ Estimated p50 saving ~= R_photo_route + 109 ms
```

If a deployment would otherwise wait for an external encoder-primer/cache step after the question, the avoided preparation window is closer to `134 ms`, making the estimated p50 saving about:

```text
✅ R_photo_route + 186 ms
```

### ⚠️ Scope

- A shared dialogue router before every model call is outside this visual-path comparison.
- The numbers above are deployment-specific examples, not universal claims.
- They do **not** include ASR, LLM text planning, TTS synthesis, audio download, or device playback.
- They measure the visual question path up to VLM first token.

---

## 🗺️ Roadmap

- [ ] Async primer mode for heavy ViT encoding.
- [ ] Scene-change-aware selection policies.
- [ ] Debugging dashboard for visual frame traces.
- [ ] Native adapters for vLLM and SGLang.

## 📄 License
MIT License. See [LICENSE](LICENSE) for details.
