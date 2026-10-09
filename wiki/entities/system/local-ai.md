---
title: 本地AI配置 — Ollama + Qwen2.5
created: 2026-08-21
updated: 2026-09-22
type: entity
tags: [system, tool]
sources: [local_ai.py, wiki_ingest.py]
confidence: 85
---

# 本地AI配置 — Ollama + Qwen2.5

## 概述
本地部署的 AI 推理引擎，用于知识库资料整理、因子研究辅助、Wiki 页面生成。

## 配置

| 项目 | 值 |
|------|-----|
| 引擎 | Ollama **0.34.2**（2026-09-22 核实；原记 0.32.15 已过时） |
| 模型（当前已装） | **`qwen2.5:7b`**（文本 4.7GB）、**`qwen2.5vl:7b`**（视觉 6.0GB）——见下方选型结论 |
| 已删除 | `qwen3:30b-a3b`（2026-09-22 按用户要求删除，**释放 17.29 GB**）及其 CPU 变体 `qwen3-30b-a3b-cpu`（同日稍早删除）。删除依据见「选型结论」节 |
| 模型库占用 | **9.92 GB**（回到 2026-09-21 升级前的水平） |
| 模型存储 | `G:\股市探究\quant-investing\ai\models\`（经 `OLLAMA_MODELS`；**改动后必须重启 Ollama 服务**才生效） |
| API 端点 | `http://localhost:11434`（OpenAI 兼容端点 `/v1` 亦可） |
| GPU | RTX 5060 Laptop，**8151 MiB**（`nvidia-smi` 实测；Win32 报的 4GB 是脏数据） |
| **NPU** | **有**（`Intel(R) AI Boost`，PnP `Class=ComputeAccelerator`，驱动 32.0.100.3717）——**2026-09-22 起已投入实际使用**：Jev 决策端点常驻服务就跑在 NPU 上（见「Jev 决策端点服务化 + DSH 集成」节）。**就地更正**：原记「但**当前不可用**」，那是「**不能加速 Ollama/LLM**」的语境（Ollama 至今无 NPU 后端），**不等于 NPU 本身不可用** |
| RAM 占用 | 7B 约 1.1 GB；30B 约 **19 GB** |

## NPU 能否用于推理加速（2026-09-22 核查）

**有硬件，但走不通当前路线。**

- **硬件存在**：`Intel(R) AI Boost`（`PCI\VEN_8086&DEV_AD1D`）状态 OK、驱动已装。（先前「HX 系列无 NPU」的推测**错误**，已纠正。）
- **Ollama 不支持**：本机 Ollama 0.34.2 的 `lib\` 只有 `ggml-cpu-*` / `ggml-cuda.dll` / `ggml-vulkan.dll`，**无 openvino / npu 后端**；官方请求仍开放（[ollama#5747](https://github.com/ollama/ollama/issues/5747)）。故 DSH 的 `ollama` 路由**不可能**走 NPU。
- **理论路径**：llama.cpp 有 [OpenVINO 后端](https://github.com/ggml-org/llama.cpp/blob/master/docs/backend/OPENVINO.md)可指定 `GGML_OPENVINO_DEVICE=NPU`（需 UD32+ 驱动，已满足），但限制硬：NPU 主要支持 **`Q4_0`**（本机三模型均为 **`Q4_K_M`**）、建议**上下文 512**、**不支持模型缓存**、**不支持 `llama-server -np > 1`**（无并行序列）。
- **不划算**：独显已实测 **61.1 tok/s**；NPU 为低功耗定位，吞吐低于独显，且需绕开 Ollama + 换量化 + 砍上下文/并行。**显存被游戏占用时，更简单的答案是 CPU 固化变体或 7B `num_gpu 0`。**
- 详见 `G:\deeeseek\dsh-portable-rc2-inspect\docs\NPU推理加速可行性核查.md`

## 选型结论（2026-09-22 实测，纯 GPU）

| 模型 | 当前状态 | 运行位置 | 速度 | 质量(6题) |
|------|---------|---------|------|-----------|
| **`qwen2.5:7b`** | ✅ **在用** | **GPU 全进显存**(4.99GB) | **61.1 tok/s** | **5/6** |
| **`qwen2.5vl:7b`** | ✅ **在用** | **GPU 全进显存**(5.73GB) | **62.3 tok/s** | **5/6** |
| `qwen3-30b-a3b-cpu` | ❌ 已删除（09-22） | CPU（`num_gpu 0` 固化） | 17.7 tok/s | **4/6** |
| `qwen3:30b-a3b` | ❌ 已删除（09-22） | 只能 CPU（18GB 装不进 8GB 显存） | 17.7 tok/s | **4/6** |

**为什么删 30B**：质量 4/6 **低于** 7B 的 5/6；且有「**思考泄漏**」——`think=false` 对它无效，思考混进正文，破坏 JSON/长度约束类任务（约束题输出 887 汉字，要求 ≤20）；开启思考则正文为空、token 全被思考吃光。另需 19 GB 内存、32 秒冷启动。**「参数更大=更好」在本机被实测否定**（原因是思考型模型与该 OpenAI 兼容端点配合不良，非模型本身弱）。

**纯 GPU 对 7B 是 6.4 倍提升**（9.5 → 61.1 tok/s）。

**「参数更大=更好」在本机被否定**：30B 输在**思考泄漏**——`think=false` 对它是无效的，思考混进正文，破坏 JSON/长度约束类任务（实测约束题输出 887 汉字，要求≤20）；而 `think=true` 时正文为空、token 全被思考吃光（在 DSH 里表现为「没有回复」）。7B 两只是非思考型，**格式必守**。

**共同短板**：三只的**多步算术都不可靠**（7B 答 221/280，正确 226）——此类任务走云端强模型。

**GPU 优势的前提是显存空闲**：玩游戏时显存被占，7B 装不进去会被打回 CPU（掉到 9.5 tok/s）。

## 使用场景

| 场景 | 说明 |
|------|------|
| 研报摘要 | 从研报中提取关键要点 |
| 因子页面生成 | 根据研究资料生成 Wiki 概念页 |
| 资料结构化 | 将非结构化文本转为 Markdown |
| 回测分析 | 辅助分析回测结果 |

## 调用脚本

### local_ai.py — 基础调用
```python
from local_ai import chat, check_model
result = chat("解释什么是EP因子", system="你是量化投资专家")
```

### wiki_ingest.py — 资料摄入
```bash
D:/pyh/python.exe -E G:/股市探究/quant-investing/code/wiki_ingest.py research.txt "价值投资因子"
```

## 工作流

```
原始资料（研报/论文/文章）
    ↓ wiki_ingest.py
本地 AI 提取关键要点
    ↓
AI 生成 Wiki Markdown 页面
    ↓
写入 Wiki（raw/articles/）
    ↓
人工审核 + 交叉引用
```

## 与云端 AI 的分工

| 任务 | 本地 AI (`qwen2.5:7b` GPU) | 云端 AI |
|------|-------------------|-----------------|
| 简单摘要 | ✅ 快速、免费、61 tok/s | 可以但浪费 |
| 分类 / JSON 抽取 / 格式约束 | ✅ 实测 6 题中这四类全过 | ✅ |
| 因子页面生成 | ✅ 可用 | ✅ 更好 |
| 复杂分析 / **多步算术** | ❌ 实测三只本地模型算术均错 | ✅ 更强 |
| 因子审查 | ❌ 不适合 | ✅ MImo 审查 |
| Wiki 维护 | ❌ 不适合 | ✅ API 操作 |
| 看图 / OCR 辅助 | ✅ 仅 `qwen2.5vl:7b` 能做 | ✅ 更准（本地模型会编造图-文映射） |

## 硬件影响

| 状态 | GPU | RAM | CPU |
|------|-----|-----|-----|
| 空闲 | 0% | 0 | 0% |
| 7B 推理中（GPU） | 权重约 5–5.7GB 常驻 | 约 1.1GB | 低 |
| 30B 推理中（CPU） | 不用显存 | **+19GB** | 高（纯 CPU 推理） |
| 与游戏同时运行 | 游戏占显存后 7B 无法进 GPU，**回落到 9.5 tok/s** | — | — |
| 与选股脚本同时运行 | 不冲突 | 7B 宽裕；**30B 会紧张**（19GB） | 30B 会争 CPU |

## 变更历史
| 日期 | 变更 | 原因 |
|------|------|------|
| 2026-08-21 | 初始化 | 搭建本地 AI + Wiki 集成 |
| 2026-09-22 | 更正+扩充 | ① Ollama 版本 0.32.15→0.34.2；② 补入 `qwen2.5vl:7b` 与 `qwen3-30b-a3b`/CPU 变体；③ 新增「选型结论」节（纯 GPU 实测 61 tok/s、6 题质量对比、30B 思考泄漏导致 4/6）；④ 更正显存为实测 8151 MiB；⑤ 更正模型存储说明（`OLLAMA_MODELS` 需重启服务才生效）；⑥ 分工表补入分类/JSON/算术/看图四行 |
| 2026-09-22 | 补充 | 新增「NPU 能否用于推理加速」节（有硬件 Intel AI Boost、但 Ollama 无 NPU 后端走不通） |
| 2026-09-22 | 更新 | **卸载 `qwen3-30b-a3b-cpu`**（按用户要求）：质量 4/6 低于 7B + 思考泄漏 + 19GB 内存 + 32s 冷启动，不值得留。DSH 的 `ollama` 路由随之缩回 2 个模型（`qwen2.5:7b` / `qwen2.5vl:7b`）。**注：卸载未释放磁盘**——该变体复用基础模型的 blob，删它只去 manifest 与极小参数层；基础模型 `qwen3:30b-a3b`（18GB）保留未删 |
| 2026-09-22 | 更新 | **删除基础模型 `qwen3:30b-a3b`**（按用户要求），**实际释放 17.29 GB**（G 盘可用 62.85→80.14 GB；模型库 27.20→9.92 GB，回到升级前水平）。剩余两只实测推理正常。本机本地模型自此收敛为 `qwen2.5:7b` + `qwen2.5vl:7b` |
| 2026-09-22 | 新增+更正 | **Jev 决策端点服务化 + DSH 集成**：混合管线（NPU 编码器 + CPU head）做成常驻 HTTP 服务并接入 DSH 可选 provider，新增「Jev 决策端点服务化 + DSH 集成」节（任务目录 `G:\deeeseek\jev-endpoint\`）。同时**就地更正三处冲突**：① 配置表 NPU 行「当前不可用」→ 已实际投用（澄清是「不能加速 Ollama/LLM」而非 NPU 不可用）；② 「NPU 能力边界」节定位行的「38.4ms 快 CPU 1.58×」是第 5 轮**编码器单独**数据，已补注被本轮 192.7 ms 服务端端到端取代；③ 「Jev 决策模型在 NPU 上的实测」节「**未实施但可行的架构**」→ 混合执行**已实施且已服务化**，仅「手写精简 OpenVINO 图」仍未做。既有内容一律保留未删 |

## NPU 能力边界（实测，2026-09-22）

详报：`G:\deeeseek\npu-capability-explore\docs\NPU能力边界探索报告.md`

| 维度 | 实测结论 |
|------|---------|
| 实测算力 | 声明 13,107 GOPS(INT8)，实测有效 **158→761 GOPS**（512³→2048³），仅达理论 **1.2%–5.8%**；随规模强增长 |
| 形状交叉点 | 固定开销约 **0.9 ms**；**L<~450 CPU 更快，L>~500 NPU 更快** |
| 算子覆盖 | relu/softmax/gelu/transpose/add/reduce_mean/**sqrt/sin/pow**/gather/**conv2d** = **11/11 通过** |
| **动态形状** | ❌ **原生崩溃 `STATUS_STACK_BUFFER_OVERRUN`**（不是报错！必须 `reshape` 固定形状） |
| INT8 matmul（图内直建） | ❌ 被拒 |
| batch 1/2/4/8 | ✅ 全通过 |
| 编译成本 | 小模型 0.2s（24 层）；**7B LLM >10 分钟未完成** |
| 并发 | `THROUGHPUT` 提示**无效**（NPU −25%、CPU −40%） |
| **游戏帧率** | ❌ **不可能直接提升**：NPU 设备类为 `ComputeAccelerator`，**无显示/渲染能力**（显示适配器注册表只有 iGPU/独显/虚拟显示） |
| **游戏时并行** | ✅ **成立且可观**：NPU 满载时 GPU 利用率仅 **+0.1 个百分点**、显存 −16MiB、CPU **2.3% 单核** |
| **数学模型计算** | ❌ **不可用**：比 CPU 慢 **1–24×**（蒙特卡洛 23.6×、Black-Scholes 7.6×），且 **FP16 精度差约 1000×**（误差 1e-1 vs CPU 1e-5） |

**定位**：NPU 不是"更快的 CPU/GPU"，而是**低功耗、独立、擅长小模型定长前向的推理协处理器**。价值在于**以零 GPU/CPU 代价并行跑小型决策模型**（如 Jev 形态，实测 38.4ms 快 CPU 1.58×），而非加速 LLM 或数值计算。

> **2026-09-22 就地更正（增量，不改原文）**：上句引用的「38.4ms 快 CPU 1.58×」是**第 5 轮的编码器单独**数据，已被后续实测取代——混合管线服务化后**服务端端到端中位 192.7 ms、HTTP 往返中位 209.8 ms**，vs CPU 全量 568.4 ms **提速 2.71×（HTTP 往返口径）**。见「Jev 决策端点服务化 + DSH 集成」。**定位结论本身不变**：NPU 是低功耗独立协处理器，**不加速 LLM 生成、不加速数值计算**。

## Jev 决策模型在 NPU 上的实测（2026-09-22）

详报：`G:\deeeseek\npu-capability-explore\docs\Jev决策模型NPU端到端报告.md`

**全链路已打通**：Open Jev（ModernBERT-base 150M）→ 数据集（1.9MB/1200 样本）→ **RTX 5060 训练** → ONNX 导出（误差 6.32e-06）→ OpenVINO → **NPU 编译成功**。

| 结论 | 数据 |
|------|------|
| 完整 Jev 在 NPU | **1625 ms vs CPU 568 ms（慢 2.9×）** —— 不划算 |
| **编码器单独在 NPU** | **全面胜出**：L=768 时 253 ms vs CPU 383 / iGPU 283（比值稳定 0.55–0.66） |
| 根因 | **导出图的动态形状脚手架**（Slice/ShapeOf/Squeeze/Range 约 2000 算子），非 NPU 算力不足 |
| NPU 精度 | logit 最大误差 **0.812**（FP16）；CPU vs ONNX Runtime 仅 2.82e-06 |

**修正第 5 轮的乐观推断**：曾据「编码器 38.4ms 快 CPU 1.58×」推断「Jev 是 NPU 的合适负载」，
**完整模型跑通后该推断被否定** —— 编码器适合 NPU，完整 Jev 图不适合。

**两个可复用的坑（已解决）**：
1. **PyTorch 缺 Blackwell 内核**：`cu126` 只到 `sm_90`，而 RTX 5060 是 `sm_120` →
   `CUDA error: no kernel image is available`。解法：装 `cu128` 索引（得 torch 2.11.0+cu128，含 sm_100/sm_120）。
2. **NPU 不支持 `IsNaN` 算子**（模型有 22 个，ModernBERT 处理 padding mask 用）→
   等价改写 `IsNaN(x)` → `Not(Equal(x,x))`，22 个替换后 **NPU 编译成功**。
   → 可复用手法：遇 NPU `NOT IMPLEMENTED` 先试等价算子替换。

**另一个方法论纠正（重要）**：初测用「串行配置扫描」报告 `NPU_TURBO=YES` 提速 **+75.6%**，
经 **A/B 交错复核**证明是**测量假象**（第一个配置承受冷启动编译，其余吃缓存）。
真实增益仅 **0.7%–4%**。凡涉及编译缓存的性能对比，必须 A/B 交错。

**未实施但可行的架构**：编码器在 NPU + logits 头在 CPU 的混合执行；或手写精简 OpenVINO 图绕开 torch.export 脚手架。

> **2026-09-22 就地更正**：本句前半（**编码器在 NPU + head 在 CPU 的混合执行**）**已实施并已服务化**——见下一节实测（189.18 ms / 100% 一致率）及「Jev 决策端点服务化 + DSH 集成」（常驻 HTTP 服务）。仍未实施的只有后半句（**手写精简 OpenVINO 图绕开 torch.export 脚手架**）。

### 突破：混合执行让 Jev 在 NPU 上提速 3.15×（2026-09-22）

**关键发现**：同架构同长度（L=768）下，**`IsNaN` 的有无造成 8.9 倍差距**。

| 导出方式 | IsNaN | NPU p50 |
|---------|-------|---------|
| dynamo + **SDPA**（默认） | **22** | 1613.59 ms |
| **dynamo + `attn_implementation="eager"`** | **0** | **180.3 ms** ⚡ |
| （参照）HF 官方 q4 | 0 | 255.0 ms |

SDPA 的 `-inf` 掩码导出时产生 NaN，需 IsNaN 参与处理 → 图对 NPU 极不友好；
**eager 用加性掩码，不产生 NaN**，导出图干净。

**混合架构实测**（编码器 NPU + head CPU；head 仅 `Linear(768→1)`，768 参数）：

| 方案 | 端到端 | 误差 |
|------|--------|------|
| **NPU 编码器 + CPU head** | **180.29 ms** | 1.79e-02 |
| CPU 编码器 + CPU head | 436.44 ms | 1.91e-06 |
| iGPU 编码器 + CPU head | 219.44 ms | 1.85e-02 |

→ **vs CPU 全量 568.4 ms 提速 3.15×**；**vs NPU 全量 1624.8 ms 提速 9.01×**；head 仅占 0.10%。

**可复用的 NPU 适配配方**：
1. 导出用 `attn_implementation="eager"`（避开 IsNaN）
2. 只把**编码器**放 NPU，head 留 CPU（完整图会慢 9 倍）
3. 固定输入形状（`reshape`），否则 NPU 原生崩溃
4. **不要盲目量化**——INT8 动态量化在 NPU 上反而更慢（1613→3375 ms）
5. 退路：`IsNaN(x) → Not(Equal(x,x))` 等价替换（能跑但慢且精度差：误差 0.812）
### ⚠️ 最值钱的一课：导出 dummy 输入必须复现真实输入特征（2026-09-22 自我纠错）

**问题**：Jev 混合管线初测显示 180 ms、3.15× 提速，但**决策一致率只有 78%**（22% 决策翻转）、
logit 相对误差 **51%**。追查后发现**根因在 ONNX 导出，不在 NPU**。

**诊断链**：

| 对照 | 结果 | 含义 |
|------|------|------|
| 我的 head 实现 vs PyTorch | 2.38e-07 | head 正确 |
| PyTorch `sdpa` vs `eager` | **0.0000** | 两实现等价（且 ModernBERT 不支持动态切换，设置无效） |
| **ONNX 导出 vs PyTorch** | **max 30.37** | **导出不忠实** |
| CPU 编码器路径误差 | 6.42e-01（NPU 6.46e-01） | **不是 NPU 精度问题** |

**根因**：导出 dummy 用了**全 1 的 `attention_mask`** → 模型走"无掩码"分支并被固化；
真实输入含 padding(0) 时行为不同 → 结果全错。

**验证与修正**：

| dummy mask | vs PyTorch |
|-----------|-----------|
| 全 1 mask | max **30.37** ❌ |
| **带 padding 的真实 mask** | **max 0.0000** ✅ |

**修正后的最终数字**（`enc_realmask.onnx`）：

| 方案 | 端到端 | 绝对误差 | 相对误差 | 决策一致率 |
|------|--------|---------|---------|-----------|
| **NPU 编码器 + CPU head** | **189.18 ms** | 0.027 | **0.984%** | **100/100 = 100%** ✅ |
| CPU 编码器 + CPU head | 420.53 ms | 3.10e-06 | — | 参照 |

**vs CPU 全量 568.4 ms → 提速 3.00×**（先前 3.15× 建立在错误管线上，**作废**）

→ **教训**：用全 1 mask 导出的模型**照样能跑、速度也快**，只有**对账**才能发现它算的是错东西。
若不查决策一致率，这个 bug 会一路带到生产。**导出 dummy 必须复现真实输入的分布特征。**
### Jev 训练完成：官方测试集成绩（2026-09-22）

训练 12/12 epoch，最佳 val acc **0.6739**（超过仓库自报微调 0.6240 与 frozen probe 0.6705）。
官方 400 例 / 2000 决策测试集：

| 配置 | **准确率** | **ECE（校准）** |
|------|-----------|----------------|
| 模型单独 | 0.6470 | 0.0739 |
| frozen probe 单独 | 0.6695 | 0.0384 |
| **ensemble(w=0.50)+锐化** | **0.7005** | **0.0288** |
| （仓库自报 ensemble） | 0.6965 | 0.0565 |
| **TypeSafe Jev 1.13.0** | **0.7270** | 0.1440 |

- 准确率距官方 Jev 仅差 **0.0265**，**超过仓库自报的 0.6965**
- **校准 ECE 0.0288 比 Jev 的 0.1440 好约 5 倍**（最突出优势）
- 本地 **33.9 ms/case**（CUDA）vs Jev 云 239 ms/call
- **置信度可路由**：阈值 0.90 → 覆盖 18.5%、准确率 **0.9541**
- 分类型：noul 0.8183 / choice 0.6650 / score 0.6388
- 注：训练用 `max_len=768`（仓库默认 1024），可能仍有上升空间

---

## Jev 决策端点服务化 + DSH 集成（2026-09-22）

**一句话**：把上一轮跑通的「NPU 编码器 + CPU head」混合管线，从一次性脚本做成**常驻本地 HTTP 服务**，并作为**可选 provider** 接进 DSH。

| 项 | 值 |
|------|-----|
| 任务目录 | `G:\deeeseek\jev-endpoint\`（`code\` 服务与 6 个验证脚本、`data\` 原始实测数据、`docs\使用与集成说明.md`） |
| 服务本体 | `code\jev_server.py`（FastAPI + **OpenVINO 原生 API**，非 openvino-genai 封装） |
| 通道 | 原生 `POST /decide`（`{state, questions｜schema_name, calibrated}`）；OpenAI 薄适配 `POST /v1/chat/completions`；另有 `GET /health`、`GET /v1/models` |
| 运行设备 | **Intel NPU**（`GET /health` 实测 `device=NPU`、`graph.devices=CPU,GPU.0,GPU.1,NPU`） |
| 编码器 | **`G:\npu-experiment\enc_realmask.onnx`**（带真实 mask 的导出；**不是** `enc_dynamo_eager.onnx`） |
| 详报 | `G:\deeeseek\jev-endpoint\docs\使用与集成说明.md`；上游依据 `G:\deeeseek\npu-capability-explore\docs\Jev决策模型NPU端到端报告.md` |

### 实测数据（一手；原始 JSON 在 `data\parity.json` / `data\latency.json`）

| 指标 | 实测 | 验收线 |
|------|------|--------|
| **决策一致率**（NPU 混合 vs CPU 全量 PyTorch） | **100/100 = 100%** | ≥95% ✅ |
| logit 相对误差 中位 / 最大 | **0.984%** / **1.927%** | <2%（**余量仅 0.073 个百分点**） |
| logit 绝对误差 中位 | 0.0270 | — |
| 服务端端到端 中位 / p95（原生 `/decide`） | **192.7 ms** / 196.0 ms | — |
| 服务端端到端 中位 / p95（OpenAI 通道） | **192.6 ms** / 195.9 ms | — |
| HTTP 往返 中位 | **209.8 ms** | — |
| **首次调用（冷）** | **380.0 ms = 稳态 1.8×** | — |
| vs CPU 全量 568.4 ms | **提速 2.71×**（口径见下） | — |
| 启动：NPU 编译**缓存命中** / **未命中** | **0.5 s** / 28.3 s | — |
| 图 | 1872 算子 / **IsNaN = 0** | — |

口径：20 条真实测试样本（`LocalLLaMA/typed-decisions` test split，`agent_trace_observability` 工作流）→ **100 个决策**；延迟为 **60 轮交错测量 + 40 次预热**（交错是硬要求，见下文配方第 5 条）。

**两个必须记住的口径**：

1. **2.71× 是 HTTP 往返口径**（568.4 / 209.8），**不是服务端计时口径**。用服务端 e2e 192.7 ms 算则是 **2.95×**。对外承诺用 HTTP 往返，与服务端计时**分开报、不混用**。
2. **两条通道无可测差异**（服务端 e2e 192.7 vs 192.6 ms，HTTP 往返 209.8 vs 209.3 ms）——OpenAI 那层只是协议翻译，开销可忽略。**服务端 e2e 192.7 ms 与上一轮同进程实测 189.18 ms 吻合**，说明 HTTP 服务化只增加约 17 ms（网络+序列化），**没有引入回归**。

> 关于启动耗时：编译时间有**三档记录并存**，按条件不同——缓存命中 **0.5 s**（本轮，已由运行中服务 `GET /health` 的 `compile_s=0.51` 复核）、自检捕获的一次 **18.1 s**、上一轮未命中 **28.3 s**。报数时必须带条件。

### DSH 集成

在 `C:\Users\asus\.dsh\settings.yaml` 的 `llm-pi-ai.providers` 下新增 `jev`：`api: openai-completions`、`baseURL: http://127.0.0.1:8123/v1`、`apiKeyEnv: JEV_API_KEY`（服务不校验，给非空值即可）、模型 `jev-decision`。

- **验证方式不是猜**：直接调用 **DSH 编译产物里的同一个函数** `resolveProfiles(providers, 'strict')`（`G:\deepseek-harness\packages\llm\llm-pi-ai\lib\types\config.js`）做严格校验 → `jev` 路由解析为**可用**（`piProvider` 已构造、无 `catalogError`、无 `modelErrors`）。脚手架：`code\verify_dsh_config.mjs` + `code\dump_providers.py`（providers 段由 Python 侧导出 JSON，**不让验证脚手架自己解析 YAML**，避免脚手架成为不可信环节）。YAML 能被解析 ≠ DSH 会接受这个 provider。
- **这是可选 provider，默认路由未改动**：仍是 `deepseek-official` / `deepseek-flash`（`reasoningEffort: max`）。
- `settings.yaml` 同时修掉一条过期注释（原文「基础模型 `qwen3:30b-a3b` 保留未删」，实际已于同日删除并回收 **17.29 GB**）。
- **依赖外部进程**：DSH **不会**替你拉起这个服务，也不做健康检查；服务没起时调用直接连接失败。

### ⚠️ 关键限制：它接受 `tools`，但**永远不会调用工具**

| 形态（原始输出 `data\tools-probe.txt`） | 结果 |
|------|------|
| 带 `tools` + `tool_choice: "auto"` | HTTP 200、378 ms、`finish_reason=stop`，**返回纯文本，`tool_calls` 不出现** |
| messages 含 `assistant(tool_calls)` + `tool` 结果的多轮回放 | HTTP 200、209 ms，**接受** |
| `stream: true` | HTTP 200、`text/event-stream; charset=utf-8`，**3 个 SSE 事件 + `data: [DONE]`** |

**结论：这条路由在 DSH 里只能当「纯文本决策模型」用，无法驱动 agent 的工具循环。** 这不是坏了——**分类模型没有解码器，本来就没有工具调用能力**。选它之前必须清楚这一点。

### 两条不可违反的正确性约束（血泪教训）

1. **编码器必须用 `enc_realmask.onnx`**（导出 dummy mask **含 padding**），**不是** `enc_dynamo_eager.onnx`（全 1 mask）。后者会**静默固化错误的掩码逻辑**：管线照样跑、速度也快，但**决策一致率掉到 78%**——**只有对账才发现它算的是错东西**。运行中的服务已由 `GET /health` 核实用的是 `enc_realmask.onnx`。
2. **输入必须 reshape 成静态 `[1,768]`**——NPU 遇动态形状是**原生崩溃**（`STATUS_STACK_BUFFER_OVERRUN`），`try/except` 抓不到。超长输入在**状态侧**截断（问题侧永不截断），再由端点补 PAD 到 768。

### 本轮踩到并修掉的两个真实 bug（都可复用）

| # | 现象 | 根因 | 修法 |
|---|------|------|------|
| **a** | 每个 POST 都回 `422 {"loc":["query","r"],"Field required"}` | `from __future__ import annotations`（注解全变字符串）**＋ 请求模型定义在 `build_app()` 函数内部** → FastAPI 只能用**模块全局命名空间**解析前向引用，嵌套在函数里解析不到，于是**静默降级**把请求体当成查询参数。**import 成功、`GET /health` 也正常，只有真发一次 POST 才暴露** | 请求模型定义在**模块级**；并加启动自检 `_assert_body_params()`——启动即断言两个 POST 路由确实有**请求体字段**，不满足直接 `SystemExit`（打印 `[jev] 自检 /decide 请求体 OK: ['r']`） |
| **b** | 服务被 `UnicodeEncodeError` **直接打死**（不是报错，是进程没了） | Windows 控制台默认 **GBK**：`print` 里带 `✓` / `✅` 这类**排版符号**即抛异常。**中文本身没问题**，危险的是符号 | 启动时 `sys.stdout.reconfigure(encoding="utf-8")`。同一个坑本轮在**两个不同脚本**里各踩了一次 |

**可复用两条**：凡 FastAPI ＋ `from __future__ import annotations`，请求模型一律放**模块级**，并加一条「POST 路由确有 body 字段」的**启动自检**；凡 Windows 控制台脚本，**启动即把 stdout 改成 UTF-8**。

### 可复用配方（NPU 混合推理 → 常驻服务）

1. 导出用 `attn_implementation="eager"`（避开 `IsNaN`；成品图 1872 算子 / IsNaN=0）
2. 只把**编码器**放 NPU；head（`Linear(768→1)`，768 参数，占 **0.10%**）留 CPU
3. 固定输入形状 `[1,768]`，超长在**状态侧**截断
4. **不要盲目量化**——INT8 动态量化在 NPU 上反而更慢
5. 性能对比**必须 A/B 交错**（否则第一个配置吃冷启动编译，造出「+75.6%」这类假象）
6. 导出 dummy **必须复现真实输入特征**（含 padding 的 mask）

### 遗留

| 项 | 状态 |
|------|------|
| **未做自启** | DSH 不会拉起服务；要长期可用需计划任务/启动目录，当前需手动起 |
| 服务**无鉴权** | 默认绑 `127.0.0.1`；`--host` 改非回环地址会打印警告 |
| 序列固定 768 | 更长输入需重新导出 + 重编译（NPU 静态形状） |
| `max_len=768` 只覆盖 93% 训练分布 | p50=607 / p90=727；用 1024 续训可能提升，未做 |
| 校准温度 T=1.0 | `calibrated` 开关当前是**恒等变换**，无实际差异 |
| 置信度路由**未接** | 阈值 0.90 → 覆盖 18.5%、准确率 0.9541 的策略层**未实现**（服务只输出概率） |
| 最大相对误差余量薄 | 1.927% vs 验收线 2%，只剩 0.073 个百分点；**换样本批必须重跑对账**，不能假定仍过关 |