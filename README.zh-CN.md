# 🚀 LiveFrameGateway

[🇨🇳 简体中文](README.zh-CN.md) | [🇺🇸 English](README.md)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

**面向 VLM 和具身智能体的“视觉上下文层”基础设施。**

LiveFrameGateway 是一个轻量级、后端无关的基础设施，用于管理实时相机帧的生命周期。它通过维护高性能的“就绪帧（Ready-frame）”环形缓冲区，填补了原始视频流与多模态大模型（VLM）之间的空白。

### ⚡ 为什么需要 LiveFrameGateway？

在传统的 VLM 交互中，视觉链路往往在用户提问**之后**才开始，导致极高的延迟：
> `提问` ➔ `拍图` ➔ `上传` ➔ `编码` ➔ `VLM 推理` ➔ `回答` (🐢 缓慢)

LiveFrameGateway 将沉重的处理工作**提前到提问之前**：
> `视频流` ➔ `持续准备 (规范化/预热)` ➔ `环形缓存`
>
> `提问` ➔ `瞬间获取` ➔ `VLM 推理` ➔ `回答` (🚀 极速)

---

## 🤖 对比：实时音视频模型/API 与语音 Agent

这是否是 **豆包视频通话/实时音视频能力**、**Gemini Live API**、**MiniCPM-o 4.5**、**Qwen2.5-Omni** 或 **OpenAI Realtime API (`gpt-realtime`)** 的竞争对手？**不是，它是它们的基础设施。**

这些系统是模型/API 层，侧重低延迟交互。根据不同提供方，它们可能处理语音到语音、音视频流、图像输入、文本和流式输出。LiveFrameGateway 解决的是它们周围的**视觉上下文生命周期**：让机器人相机帧在模型调用前就已经 ready、可追踪、可选择、可注入。

| 特性 | 实时音视频模型/API | LiveFrameGateway 方案 |
| :--- | :--- | :--- |
| **角色** | 端到端交互模型或运行时 | 后端无关的视觉上下文基础设施 |
| **实时重点** | 流式音频/视频/文本 I/O 和语音响应 | 提问前的帧就绪、选择与注入 |
| **视觉输入** | 由模型/提供方定义的实时流或抽样帧 | 显式 ready-frame ring + 稳定 `frame_uuid` |
| **元数据** | 通常只是模型输入 payload | 像素 + **机器人状态** (姿态/运动/质量/扫描元数据) |
| **控制性** | 优化对话即时性 | 优化机器人可追踪性、缓存预热和帧生命周期 |
| **兼容性** | 依赖具体提供方或模型 | 可配合 vLLM、SGLang、托管 VLM 和 realtime API 使用 |

---

## ✨ 核心特性

- 🔄 **智能环形缓存**：按会话（Session）隔离的有界缓冲区，支持自动淘汰。
- 🎯 **智能帧选择**：支持 `latest`（最新）、`quality`（质量优先）、`motion`（运动优先）等策略，选出“最合适”的帧。
- 🧩 **无缝消息注入**：只需一行代码，即可将缓存帧格式化为兼容 OpenAI 的多模态 API 消息。
- 🤖 **具身智能优先**：原生支持姿态（Pose）、运动（Motion）和扫描元数据，这对于具身智能体至关重要。
- 🔌 **预热钩子 (Primer Hooks)**：在帧到达时自动调用外部服务（如 ViT 编码器），提前预热缓存。
- 📏 **延迟基准测试**：内置测试工具，直观量化延迟优化的效果。

---

## 🏗️ 系统架构

```text
  [ 帧产生者 ]                 [ LiveFrameGateway ]             [ 智能体 / VLM ]
 (机器人/相机/App)               (Sidecar / 服务)                (消费者应用)
         |                             |                              |
         | --- POST /frames ---------> |                              |
         |                             | --- (可选) Primer 预热 ---->  |
         |                             |                              |
         |                             | <--- GET /select /latest --- |
         |                             |                              |
         |                             | --- OpenAI 多模态消息 ------> |
```

---

## 🚀 快速开始

### 1. 安装
```bash
pip install "liveframegateway[dev] @ git+https://github.com/Animan-AI/LiveFrameGateway.git"
```

### 2. 启动 Gateway 服务
```bash
liveframegateway serve --port 8095 --ring-size 20
```

### 3. 推送一帧数据
```bash
curl -X POST http://127.0.0.1:8095/sessions/demo/frames \
  -H 'Content-Type: application/json' \
  -d '{
    "frame_uuid": "f1",
    "image_base64": "...",
    "quality": {"blur_score": 0.05, "confidence": 0.98}
  }'
```

### 4. 在 Python 中使用
```python
from liveframegateway.injection import inject_openai_messages
import requests

# 从 gateway 获取选定的帧
frames = requests.get(
    "http://127.0.0.1:8095/sessions/demo/frames/select?policy=quality"
).json()["frames"]

# 注入到 OpenAI 兼容的消息列表中
messages = inject_openai_messages(
    messages=[{"role": "system", "content": "你是一个机器人助手。"}],
    frames=frames,
    user_text="你看到了什么？"
)
```

---

## 🔍 帧选择策略

- **`latest`**：默认策略。获取最近的 N 帧。
- **`quality`**：根据质量评分（置信度 - 模糊度）筛选最佳帧。
- **`motion`**：根据运动阈值筛选机器人移动过程中的帧。

---

## 📊 性能评估

使用内置 probe 在你自己的系统上验证延迟收益：

```bash
# 🧪 衡量请求准备阶段开销
python benchmarks/replay_latency.py --frames 120 --select-k 3

# ⚡ 针对 OpenAI-compatible VLM 测试 server-side 提问路径
python benchmarks/question_path_latency_probe.py \
  --gateway-base-url http://127.0.0.1:8095 \
  --consumer-base-url http://127.0.0.1:8201/v1 \
  --model your-model-name \
  --session-id your-session-id
```

### 🧪 实机测试环境

一次 `2026-05-17` 的真实机器人部署测试：

| 项目 | 取值 |
| :--- | :--- |
| 📷 设备流 | Orange Pi 相机帧 |
| 🔄 Gateway 模式 | ready-frame ring + 外部 encoder primer |
| 🧠 VLM 后端 | 本地 vLLM OpenAI-compatible 服务 |
| 🏷️ 模型 | `qwen36-35b-a3b-awq` |
| 🔁 迭代次数 | `10` |

### ⚡ 实测结果

| 指标 | 传统 direct image | Ready-frame path | 差值 |
| :--- | ---: | ---: | ---: |
| Server-side TTFT p50 | `283.0 ms` | `228.8 ms` | `-54.9 ms` |
| Server-side TTFT p95 | `341.3 ms` | `243.1 ms` | `-98.2 ms` |
| VLM 请求总耗时 p50 | `301.5 ms` | `248.4 ms` | `-53.1 ms` |
| latest-frame fetch p50 | N/A | `~2.3 ms` | N/A |

### 🔧 帧准备成本

| 准备阶段 | p50 | p95 | 来源 |
| :--- | ---: | ---: | :--- |
| 设备帧时间戳 -> server ingest | `57 ms` | `72 ms` | 最近 120 条私有部署 ingest 日志 |
| 设备帧时间戳 -> 外部 encoder-cache 文件 ready | `134 ms` | `157 ms` | 最近 encoder-cache artifacts |

### 🧮 估算体感 TTFT

LiveFrameGateway 不需要再做一次“是否拍照”的判定。视觉上下文已经持续维护，构建 VLM 请求时可以直接选择并注入 ready frames。

```text
🐢 按需拍照
   ~= 拍照/视觉意图路由 + 拍图/上传 + direct VLM TTFT
   ~= R_photo_route + 57 ms + 283 ms
   ~= R_photo_route + 340 ms

🚀 Ready-frame
   ~= latest-frame fetch + ready-frame VLM TTFT
   ~= 2 ms + 229 ms
   ~= 231 ms

✅ 估算 p50 节省 ~= R_photo_route + 109 ms
```

如果某个部署在用户提问后还需要等待外部 encoder-primer/cache 步骤，那么被提前隐藏的准备窗口更接近 `134 ms`，估算 p50 节省约为：

```text
✅ R_photo_route + 186 ms
```

### ⚠️ 适用边界

- 如果应用层在所有模型调用前都有一个通用对话 router，这个共享 router 不应计入视觉路径对比。
- 上述数字是具体部署下的示例，不是通用结论。
- 这些数字**不包含** ASR、文本规划、TTS 合成、音频下发或端侧播放。
- 它们只衡量视觉提问路径到 VLM first token 的部分。

---

## 🗺️ 路线图

- [ ] 针对重型 ViT 编码的异步预热模式。
- [ ] 场景变化感知（Scene-change-aware）的选择策略。
- [ ] 用于视觉帧追踪调试的可视化看板。
- [ ] 针对 vLLM 和 SGLang 的原生适配器。

## 📄 开源协议
MIT License. 详见 [LICENSE](LICENSE) 文件。
