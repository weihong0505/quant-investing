---
title: 本地 QLoRA 微调 7B 实践方法论
created: 2026-09-23
updated: 2026-09-23
type: entity
tags: [system, tool]
sources: []
confidence: 65
---

# 本地 QLoRA 微调 7B 实践方法论

> 来源：一个本地情感陪伴模型微调项目（2026-09 已归档；语料与个人数据不入库，本文只沉淀**技术与流程**经验）。
> 环境：Windows 笔记本 · RTX 5060 Laptop（sm_120）· 8GB 显存 · Qwen2.5-7B-Instruct。

## 概述 / 是什么

在消费级笔记本上做 QLoRA SFT 的一手经验合集：环境选型、数据管线、**四个必踩训练卡点**、以及一套 **GPU 疑难杂症排查方法论**（本次实际用到的全流程，含未解案）。

## 关键事实与经验

### 1. 环境选型（Windows + 8GB 显存）

- torch **必须 cu128+ 轮子**才有 Blackwell sm_120 内核；驱动 UMD 与 torch CUDA 运行时错配是张量核异常的嫌疑源之一（未证实）。
- transformers 5.x 有破坏性变更：`warmup_ratio`、`group_by_length` 已移除（用 `warmup_steps`、删参）。
- QLoRA 配置（8GB 稳妥档）：NF4 + 双量化、r=16/α=32、batch=1 × accum=16、max_len=1536、bf16、gradient checkpointing、lr=1e-4 cosine。
- 合并 LoRA 必须在 bf16 基座上做（CPU 合并，8GB 显存放不下 7B bf16）。

### 2. 四个训练卡点（都已实证并修复）

| 卡点 | 处置 |
|---|---|
| 脚本读路径与磁盘不符（生成器与训练脚本目录不同） | 启动训练前核对真实路径 |
| transformers 5.17 移除 `warmup_ratio`/`group_by_length` | 换 `warmup_steps`、删参 |
| **paged_adamw_8bit 的 optimizer 序列化在 checkpoint 保存处挂起**（CPU 满转、0 字节文件、永不返回） | `save_only_model=True`；final 保存直走 `PeftModel.save_pretrained` 绕开 Trainer |
| 长时间训练的中断损失 | checkpoint 每 50 步落盘；续训 `resume_from_checkpoint` + **过滤小步号 checkpoint**（避免误续 smoke 残留） |

### 3. 下载与校验

- huggingface_hub（httpx）在本机可**静默卡死**（满核空转、0 字节落盘）→ 用 curl 断点续传分片（`-C -` + HEAD 取期望大小 + 自动重试），4 路并行可达 ~10MB/s。
- 完整性校验：解析各分片 safetensors 头部，张量数据字节总和 == `model.safetensors.index.json` 的 `total_size`（文件总大小会多出头部开销，勿直接比对）。

### 4. GPU 疑难杂症排查方法论（本次实战七步）

1. **先记基线**：正常态步速/算力，异常判定靠前后对比（本例基线 38s/步 → 异常 100-130s/步）。
2. **分项体检**：bf16 GEMM（张量核）vs fp32 GEMM（CUDA 核）vs 显存带宽 vs 显存完整性回读。本例 bf16=36 TFLOPS（应 100+）、fp32=11（正常）→ 精准锁定张量核路径。
3. **wall vs GPU 时间**（CUDA event）：ratio≈1 说明 GPU 真在慢算，排除启动/搬运开销。
4. **时钟/功耗/温度**：注意 NVML 读数会自相矛盾（本例报满频 2857MHz/100% 但仅 33W）；**以墙钟实测为准**。功耗异常低 + 满频 = 张量核没吃上活。
5. **PCIe 链路代宽**：链路卡低代（本例 Gen2×8，应 Gen5×16）会拖垮显存带宽敏感负载；游戏无感是因为纹理常驻显存。
6. **系统事件日志**：`Event 1019`（nvlddmkm bugcheck 蓝屏）、`Event 153`（GPU 故障）是定位时间线的铁证；蓝屏后 GPU 可能进入降级态。
7. **逐项排除环境因素**：电源计划/ASPM、Defender 实时扫描、壁纸引擎等后台 GPU 占用。

**未解案**：本例蓝屏后张量核慢 3× 跨重启/冷启动持续，最终项目终止；剩余假设按性价比：换新版驱动 → 换 torch CUDA 运行时 → 硬件缺陷（售后）。

### 5. 坑与教训（通用）

- **强杀活跃 CUDA 进程（-Force）可触发 nvlddmkm 蓝屏**——先不带 -Force 停。
- 杀 CUDA 进程后紧邻启动的新进程会瞬时 OOM（显存 teardown 未完成），等几秒即可。
- 后台 shell 若为 PowerShell 5.1：ps1 必须 UTF-8 带 BOM（否则中文路径乱码）、无三元运算符。
- **游戏正常 ≠ CUDA 正常**：游戏与训练的负载模式（张量核使用、PCIe 依赖）差异很大，不能互证。
- 训练前先跑冒烟（个位数 step）验证管线，再上全量；冒烟与全量用同一份数据前 N 行以便对比。

## 与其他页面

- [[ai-toolchain-notes]] — 本机 AI 工具链层面的其他坑（pwsh 编码、Ollama 端点等）
- [[local-ai]] — 本地 AI 配置与 NPU/推理实测（本项目属其「本地训练」一脉）

## 复用指引

重启类似项目时的顺序：GPU 体检（bf16 GEMM >100 TFLOPS 为健康线）→ 2 步基准 → 全量（checkpoint 50 步一档）→ merge → GGUF → 注册推理端 → 固定探针验收。
