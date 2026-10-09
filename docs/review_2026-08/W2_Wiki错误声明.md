# W2 — Wiki 声明与代码不符：错误知识在库里传播

> 来源：项目复盘 2026-08-22 第 W2 项（Wiki 全文：G:\quant-investing\wiki\comparisons\project-review-2026-08.md）
> ✅ 已验收 2026-08-22 AI批处理：backtest-engine/multi-factor-v2/momentum-60d修正，5个因子页加contested标记
> ✅ 已验收 2026-08-22 AI批处理（第二批）：9 因子页巡检收尾（gpm/cfo-ni-ttm/lev/log-mcap 补 contested:true + 口径审计指向；turnover 权重 0.10→0.15 同步）；ep 公式改 TTM 口径；vol-ratio 弃用状态同步；backtest-engine 当前状态行更新为 CSI300 试点已跑通；grep '25/25' 与 '已实现' 逐条核对通过
> 严重度：🟠 重大　|　任务性质：Wiki 修订　|　涉及文件：wiki/entities/system/backtest-engine.md、wiki/entities/system/multi-factor-v2.md、wiki/concepts/factors/momentum-60d.md
> 依赖：部分条目依赖对应代码任务定案（见下）　|　建议优先级：随时可做（与代码任务联动）

## 1. 问题现状

Wiki 中至少 3 处页面声明与代码事实不符，其中 2 处是"把未实现的能力标成已实现"。LLM Wiki 的核心资产是可信度——错误声明比没有声明更糟。

## 2. 逐条证据与修改要求

### 条目 1：backtest-engine.md 宣称 hfq 收益层已实现（假）

- **证据**：`wiki/entities/system/backtest-engine.md`"双口径铁律"一节："信号/收益层：hfq（总收益口径，含分红再投）"——标注为已实现能力。代码实况：px_hfq 零使用（见 C3 任务证据）。
- **修改要求**：**等 C3 定案后同步**：方案 A（实现 hfq）→ 保留表述；方案 B（改口径）→ 改写为最终口径。当前可先行在页面加醒目标注："⚠️ 本页该条与代码现状不符，见项目复盘 C3，修复中"。

### 条目 2：multi-factor-v2.md 宣称 backtest.py"替代旧 simple_backtest() 玩具版"（假）

- **证据**：`wiki/entities/system/multi-factor-v2.md`"模块分工"一节："backtest.py — 真实成本回测引擎（替代旧 simple_backtest() 玩具版）"。代码实况：simple_backtest 仍在且是管线默认调用的唯一回测（见 C2 任务证据）。
- **修改要求**：**等 C2 定案后同步**（C2 完成后此表述自然成真）。当前先加标注或直接改为"回测引擎已实现金样本验证，尚未接入真实数据"。

### 条目 3：backtest-engine.md "~800 行"（实际 605 行）

- **证据**：页面写"自研月度调仓回测引擎（~800 行）"；实际 `wc -l` = 605。
- **修改要求**：改为准确行数或去掉行数（行数不是知识，建议直接删除该表述）。

### 条目 4：momentum-60d.md 自认"最大因子矛盾"却不触发任何行动

- **证据**：`wiki/concepts/factors/momentum-60d.md`"已知问题"："与价值因子的冲突：EP 说'买银行'，动量说'卖银行'——这是系统中最大的因子矛盾"，confidence 标 medium；因子照常 15% 权重运行，无 contested 标记、无待决事项。
- **修改要求**：① frontmatter 加 `contested: true`；② 加"待决事项"区块指向 M5 任务（FM 增量检验裁决）；③ confidence 由 medium 改为 low（无检验证据，符合 SCHEMA 定义"low：单来源、过时、或与新数据矛盾"）。M5 有结论后回填。
- **注意**：类似"有记录、无行动"的因子页还有可能存在于其他 9 个因子页——修改时顺带巡检：凡"已知问题"里提到未验证矛盾/风险的页面，一律 contested 标记 + 指向对应复盘任务。

## 3. 验收标准

- [ ] 条目 1-3 页面表述与代码事实一致（或带明确的"修复中"标注）
- [ ] momentum 页及巡检发现的其他因子页：contested 标记 + 待决事项 + confidence 降级
- [ ] `grep -r '已实现' wiki/entities/system/` 抽查：所有"已实现"能力在代码中可对应到真实逻辑（逐条过一遍）

## 4. 修改后需同步的文档

- wiki/log.md（update 记录）
