---
title: EP因子 — 盈利收益率
created: 2026-08-21
updated: 2026-08-25
type: concept
tags: [factor, value, ep]
sources: [multi_factor_value.py]
confidence: 60
contested: true
---

# EP因子 — 盈利收益率 (Earnings-to-Price)

## 定义
EP = 1 / 市盈率-动态，即每股收益占股价的比例。EP 越高，股票越"便宜"。

## 计算公式
```python
EP = df['EPS_TTM'] / df['最新价']   # TTM 口径（2026-08-22 修复，口径审计 M6）
```
- 数据来源：akshare `stock_yjbb_em`（EPS_TTM，4 季滚动）+ `stock_zh_a_spot_em`（最新价）
- 原 `1.0 / 市盈率-动态`（动态 PE = 现价/年化当期 EPS，单季×4）已降为参考列 EP_DYN、不计入合成（2026-08-22，data_caliber_audit.md）
- 入池条件：PE > 0（剔除亏损股）

## 当前配置
| 项目 | 值 |
|------|-----|
| 权重 | 0.20 (20%) |
| 方向 | +1（越高越好） |
| 处理 | 全市场 winsorize ±3σ → z-score |
| 中性化 | 否（全市场统一标化） |

## 经济逻辑
- 格雷厄姆价值投资的核心指标
- 高 EP 意味着每块钱投入获得的盈利更多
- 在 A 股，EP 因子长期有效，但在创业板/成长股中效果较弱

## 已知问题
- 亏损股已剔除（PE ≤ 0 入池时过滤），但周期股在盈利高点 EP 虚高
- 2024 年后有研究指出 EP 因子在创业板失效的迹象（待验证）
- 与 [[bp-factor]] 存在天然正相关（都反映估值便宜）

## 待决事项（contested）

- "2024 年后 EP 因子在创业板失效的迹象"为**未验证的外部论断**——项目 10 因子统计检验列全空（复盘 S1），EP 的 A 股 2017+ signed IC 与 v3 全流程检验未执行，无法证实/证伪。
- **✅ 2026-08-22 试点符号验证（初步）**：yjbb TTM 快照试点（16 月，2025-04~2026-07）signed IC 方向与登记 + 一致但未达显著线（NW-t=+0.36，ICIR=0.069）；FM 增量（控制 ln_mcap+行业）t=+1.94 未达 2.0 线 → 维持 0.20 权重但标记**观察**，数据未就绪前不裁决淘汰（registry #15；报告 [[test_value_vs_momentum_20260822]]）。
- **口径**：EP 已改 TTM 口径（EPS_TTM/最新价，2026-08-22，见 docs/factor_docs/data_caliber_audit.md）；EP_DYN（动态 PE）已弃用为参考列。
- **指向任务**：复盘 S1（因子零检验，含 EP 补检与符号验证）→ M5（价值×动量 FM 增量裁决，EP 为回归变量之一）。全 A 2017+ 财务数据就绪后走 v3 全流程。
- 相关任务包：W2_Wiki错误声明.md 条目 4 巡检项。

## 相关页面
- [[bp-factor]] — 同属价值因子，常一起使用
- [[weighted-scoring]] — EP 在加权评分中的角色
- [[factor-direction-map]] — 权重与方向一览
- [[multi-factor-v2]] — 当前策略版本
- [[factor-decay]] — 因子衰减风险

## 变更历史
| 日期 | 变更 | 原因 |
|------|------|------|
| 2026-08-21 | 初始化，权重0.20 | v2策略MImo审查后定稿 |
| 2026-08-22 | 试点符号验证回填：方向与登记一致但未达显著线，FM 增量未达 2.0 → 观察 | 复盘 M5 执行（docs/factor_docs/test_value_vs_momentum_20260822.md） |
