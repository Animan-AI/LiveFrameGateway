# 🚀 LiveFrameGateway

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

## 🤖 对比：LiveFrameGateway vs. 豆包 / MiniCPM-V 4.6 等原生模型

这是否是 **豆包 (Doubao)** 或 **MiniCPM-V 4.6** 等实时多模态模型的竞争对手？**不，它是它们的基础设施。**

虽然豆包等云端模型提供了极佳的对话体验，MiniCPM-V 4.6 展现了强大的多模态能力，但 LiveFrameGateway 解决的是**视觉数据如何高效流向这些“大脑”**的工程问题：

| 特性 | 豆包 / MiniCPM-V 4.6 原生交互 | LiveFrameGateway 方案 |
| :--- | :--- | :--- |
| **设计哲学** | 端到端推理与流式输出 | 通过异步预处理“屏蔽”传输与准备延迟 |
| **元数据** | 纯像素输入 | 像素 + **机器人状态** (姿态/运动/扫描进度) |
| **带宽压力** | 往往需要持续的高带宽流 | **选择性推送**，仅在关键帧或按需预加载 |
| **端侧适配** | 依赖模型本身的轻量化 | **后端无关**，让轻量化模型也能访问历史高质量帧 |
| **场景定位** | 开放域人机对话 | 具身智能体感知、低延迟视觉问答与回溯 |

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
pip install "liveframegateway[dev] @ git+https://github.com/your-username/LiveFrameGateway.git"
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
frames = requests.get("http://127.0.0.1:8095/sessions/demo/frames/select?policy=quality").json()

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

使用内置的基准测试套件验证延迟收益：

```bash
# 衡量请求准备阶段的开销
python benchmarks/replay_latency.py --frames 120 --select-k 3

# 测试端到端提问路径延迟
python benchmarks/question_path_latency_probe.py --gateway-base-url http://127.0.0.1:8095
```

---

## 🗺️ 路线图

- [ ] 针对重型 ViT 编码的异步预热模式。
- [ ] 场景变化感知（Scene-change-aware）的选择策略。
- [ ] 用于视觉帧追踪调试的可视化看板。
- [ ] 针对 vLLM 和 SGLang 的原生适配器。

## 📄 开源协议
MIT License. 详见 [LICENSE](LICENSE) 文件。
