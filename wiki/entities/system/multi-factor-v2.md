---
title: 价值投资决策系统 v3（设计定稿 2026-08-25）
created: 2026-08-21
updated: 2026-08-25
type: entity
tags: [system, pipeline]
sources: [multi_factor_value.py, backtest.py, sell_signals.py, docs/factor_docs/value_investing_transition_v2.1.md]
confidence: 60
---

# 价值投资决策系统 v3

## 概述

v2.1 设计定稿（2026-08-25，`docs/factor_docs/value_investing_transition_v2.1.md` 终审通过，P0-A/P1-A/P1-B/P1-C 必改项清零）：从"多因子打分排序器"（v2）转型为**价值投资决策系统**（v3）。因子有效性状态见 docs/factor_docs/factor_registry.md——"设计已审"不等于"因子有效"（M1 口径）。

**四层管线**（替代单一 SCORE 排序）：

1. ① 可交易性过滤（约束层）：停牌/退市/ST 排除；市值 ≥30 亿；日换手率 0.1%~20%；上市 ≥5 年
2. ② 质量门槛（排除层，一票否决）：非金融 ROE_TTM ≥8%（周期 8 行业豁免 ≥4% 且 EPS>0）；GPM>0；CFO_NI_TTM>0；LEV<70%；EPS_TTM>0
3. ③ 估值打分（核心层）：**安全边际分 = 0.30×PE_PCTL + 0.30×PB_PCTL + 0.15×EP_z + 0.15×BP_z + 0.05×DY_z + 0.05×FCF_YIELD_z**（主观先验权重，W-编号草案挂起，组合层检验后由证据定稿）；行业内 z-score 统一申万一级
4. ④ 组合构建：top 10-15（**默认 12，等权**），**季度调仓**（原月度/top30）；行业上限 ≤30%；个股上限 ≤10%；容量 ≤5% ADV

**新增 4 因子**（registry ⓪ 步已登记 2026-08-25，**均待检验**）：

| 因子 | 预期符号 | 数据源 | 状态 |
|------|---------|--------|------|
| PE_PCTL | − | RPT_VALUEANALYSIS_DET（2018-01+ 滚动窗口分位） | ⏳ 待检验 |
| PB_PCTL | − | 同 PE_PCTL | ⏳ 待检验 |
| DY | + | fhps_detail_em（PIT 除权除息日对齐） | ⏳ 待检验 |
| FCF_YIELD | + | RPT_DMSK_FN_CASHFLOW（首次公告快照固化；金融股剔除出打分） | ⏳ 待检验 |

**MOM_60D 处置**：原方向（+）已淘汰出打分体系（registry #13 试点反向显著 + #17 FM 无增量）；反转方向 #12 MOM_60D_R1 保持待检（P4 并入检验）。

## 代码位置

- `G:/股市探究/quant-investing/code/value_investing.py` — v3 主策略模块（**计划**，P2 实施：门槛层+打分层+组合层）
- `G:/股市探究/quant-investing/code/multi_factor_value.py` — 旧系统 v2，**保留作对照**（MOM_60D 归零后 8 因子重归一化：EP 0.235/BP 0.235/ROE_TTM 0.141/GPM 0.071/CFO_NI_TTM 0.059/LEV 0.024/TURNOVER 0.176/LOG_MCAP 0.059）

## 实施状态

| 阶段 | 内容 | 状态 |
|------|------|------|
| P0 | 设计终审 | ✅ 2026-08-25 定稿 |
| P1 | data_fetcher 4 新接口 + 口径验证（NOTICE_DATE 交叉校验/东财→申万映射 ≥95%/5 年财务历史） | ⏳ 待实施 |
| P2 | value_investing.py 重构 + MOM 归零重归一化 + 卖出信号合成测试 | ⏳ 待实施 |
| P2.5 | 生产开关 fail-closed（默认拒绝实验性权重；显式 `--experimental` 允许但强制标注、禁止实盘信号输出） | ⏳ 待实施 |
| P3 | registry 前置登记 4 新因子 + 文档同步（本页所属） | ✅ 2026-08-25 |
| P4 | v3 统计检验（4 新因子，分段报告 2018-2022 / 2023+） | ⏳ 待检验 |
| P5 | 真实数据回测（新旧净超额对照，对照期 ≥1 完整年度） | ⏳ 待实施 |

## 旧系统 v2（对照）模块分工

- `sell_signals.py` — 卖出信号（时间止盈/衰减/止损）→ 目标权重矩阵；⚠️ v3 语义变更：信号行 = **完整持仓快照**（未动持仓保留原权重，禁止只列卖出股）
- `backtest.py` — 真实成本回测引擎（金样本 103/103）；v3 不改引擎（季度调仓 = 传季度信号日期，top_n=12 参数化）
- `ic_monitor.py` / `rolling_stats.py` / `regime_weights.py` — 检验与风控工具
- `data_fetcher.py` — 统一数据层（缓存+重试+多源降级链+退市股）
- `e2e_pipeline.py` — 端到端回测管线；`factor_test_suite.py` — v3 因子检验流水线

## 相关页面

- [[ep-factor]] / [[bp-factor]] — 价值因子（层③绝对估值）
- [[pe-pctl]] / [[pb-pctl]] / [[dy-factor]] / [[fcf-yield]] — v2.1 新增 4 因子（待检验）
- [[momentum-60d]] — 原方向已淘汰（#13），反转方向待检（#12）
- [[backtest-engine]] — 回测执行；[[sell-signals]] — 卖出信号
- [[sop-v1.1]] — 工作规范（§3.4 价值投资决策流程，v1.6）
