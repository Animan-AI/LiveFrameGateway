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

## 🤖 vs. End-to-End Realtime Models

Is this a competitor to GPT-4o or Gemini 1.5 Pro's native audio-visual streaming? **No, it is infrastructure.**

While end-to-end models focus on token-level streaming, LiveFrameGateway provides the **engineering lifecycle** required for robots and agents to use *any* VLM effectively:

| Feature | End-to-End Realtime Models | LiveFrameGateway Approach |
| :--- | :--- | :--- |
| **Philosophy** | Native multimodal streaming | Latency masking via async prep |
| **Metadata** | Pure pixels | Pixels + **Robot State** (Pose/Motion) |
| **Bandwidth** | Constant high-bitrate stream | Selective, on-demand or pre-loading |
| **Flexibility** | Provider-specific | **Backend-agnostic** (vLLM, Claude, etc.) |
| **Use Case** | Human-AI conversation | Robot vision & low-latency interaction |

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
pip install "liveframegateway[dev] @ git+https://github.com/your-username/LiveFrameGateway.git"
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
frames = requests.get("http://127.0.0.1:8095/sessions/demo/frames/select?policy=quality").json()

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

Prove your latency gains with our built-in benchmarking suite:

```bash
# Measure request preparation overhead
python benchmarks/replay_latency.py --frames 120 --select-k 3

# Test end-to-end question-path latency
python benchmarks/question_path_latency_probe.py --gateway-base-url http://127.0.0.1:8095
```

---

## 🗺️ Roadmap

- [ ] Async primer mode for heavy ViT encoding.
- [ ] Scene-change-aware selection policies.
- [ ] Debugging dashboard for visual frame traces.
- [ ] Native adapters for vLLM and SGLang.

## 📄 License
MIT License. See [LICENSE](LICENSE) for details.
