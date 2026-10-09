---
title: DSH 工具呈现模式与 PTC 决策
created: 2026-09-19
updated: 2026-09-19
type: entity
tags: [system, tool, decision]
sources: [G:/deeeseek/ptc-vs-native-bench/REVIEW.md, G:/deeeseek/ptc-vs-native-bench/data/summary-sizes3.json, G:/deeeseek/ptc-vs-native-bench/docs/decision-card.md, G:/deepseek-harness/packages/core/tools/README.zh.md]
confidence: 85
---

# DSH 工具呈现模式与 PTC 决策

DSH 的"工具怎么交给模型"是一个**呈现模式（presentation mode）**选择：`native`（每个工具一份 JSON Schema）、`ptc`（只给 `run_code` + 生成的 TypeScript SDK）、`both`（两套都发）。本页记录 2026-09-19 三轮实测的定量结论与决策判据；机制类坑见 [[dsh-plugin-internals]]，环境类坑见 [[ai-toolchain-notes]]。

**一页决策卡：`G:\deeeseek\ptc-vs-native-bench\docs\decision-card.md`（本页是其知识库版本）。**

## 1. 结论（可直接用）

**PTC 的价值 = 让"大输入 → 小结论"的处理不再把大输入带进上下文。**

| 单文件体量 | native 新输入 token | ptc 新输入 token | native 成本 | ptc 成本 | PTC 优势 |
| --- | --- | --- | --- | --- | --- |
| 2.8 KB | 9,860 | 3,599 | ¥0.0305 | ¥0.0220 | 1.39× |
| 24.8 KB | 20,529 | 3,458 | ¥0.0547 | ¥0.0155 | **3.53×** |
| 143.4 KB | 9,059 | 3,571 | ¥0.0259 | ¥0.0155 | 1.67× |
| 581 KB | 21,398 | 3,815 | ¥0.0562 | ¥0.0198 | 2.84× |

- **PTC 的累计新输入 token 是恒定的（≈3,500–3,800/任务）**，与文件多大无关；native 是 9,000–21,000+，且随"模型这一轮选择读文件还是写 shell 脚本"漂移。
- **固定开销**：PTC 首请求系统提示词比 native **多 ≈1,400 token（+15%）**；`both` 多 **≈7,400（+78%）**。所以小任务上省得最少（1.39×），中等文件收益最大。
- **往返**：把"用一个程序做完"写进任务后，PTC 请求数 6 → 2.7（native 3.5–6.5）；不写就会被模型拆成多次 `run_code`，反而比 native 多。
- 16/16 全部答对；成本口径 cacheRead ¥0.2/M、未命中输入 ¥2/M、输出 ¥3/M（deepseek 定价），数据源为 provider 返回的逐次 `usage`。

## 2. 判据

1. 能用**一段程序**说清（批量读/过滤/聚合/并发）→ 考虑 PTC；需要逐步人工审阅 → native。
2. 输入 ≥24 KB 而结论很小 → PTC 回本最确定；几 KB → 两者都行，PTC 略省。
3. 500 KB 以上要留意模型上下文窗口；PTC 的意义正是"大输入不进上下文"。
4. `both` 只在任务类型混合且愿意付 +78% 提示词时用。

## 3. 任务措辞（实测影响最大的一条）

普通 PTC 会话里，模型会把每次工具调用各包一层 `run_code`，往返反而比 native 多（实测 6 vs 5）。加一句：

```text
要求：必须用一段 run_code 程序完成全部步骤（程序内用 tools.read / tools.glob，
不要直接调用其它工具，不要分多次程序），只输出最终一行：<格式>
```

## 4. 反模式

- 单步任务用 PTC（多付 Node 进程启动 + 沙箱准备）；
- 小任务上"既逼它写程序又让它反复验证"（实测因此比 native 贵 1.5×，是措辞问题不是体量规律）；
- 程序内做长等待/人工审批（`run_code` 默认 120 s 经过时间预算，含等工具与等人，上限 600 s）；
- 指望失败自动重放（程序可能已写盘/发请求）；
- 把 PTC 当安全边界（程序内可直接用 Node `fs`/`child_process`，受与 bash 相同的 OS 策略约束）。

## 5. 测量方法（可复用）

- 三种模式切换：`DSH_TOOLS_MODE=native|ptc|both`（web-app bundle 的 env seam，官方注释写明是 per-session 选择落地前的临时通道）；
- 驱动：`node apps/cli/lib/bin.js --profile headless headless --json "<task>"`（headless profile 走 `dsh-base`，自带 `ptc-runtime`）；
- 逐次 token：解析 `--json` 事件流里的 `status.step_end.usage`（`inputTokens` 是**未命中缓存**的新输入，提示词总量 = `inputTokens + cacheReadTokens`）；
- **必须先隔离 fixture**：每个样本独立目录 + 任务里写绝对路径。否则模型在找不到文件时会 `glob("**/app.log")` 读到别轮的 fixture，返回别轮的答案（本轮实测因此作废 4 个样本）。

## 6. 关联

- [[dsh-plugin-internals]] — DSH 插件机制、会话日志格式、子代理唤醒
- [[ai-toolchain-notes]] — 环境类坑（pwsh 编码、行尾、Ollama 端点）
- [[sop-v1.1]] — 流程规则本体
