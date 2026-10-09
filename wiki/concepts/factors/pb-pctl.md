---
title: PB_PCTL因子 — 市净率历史分位
created: 2026-08-25
updated: 2026-08-25
type: concept
tags: [factor, value]
sources: [docs/factor_docs/value_investing_transition_v2.1.md]
confidence: 35
contested: false
status: 待检验
---

# PB_PCTL因子 — 市净率历史分位 (Percentile)

## 定义
PB_PCTL = PB(MRQ) 的**实际历史滚动窗口分位**：数据源 2018-01-02 起累积，窗口随日历增长（最短 ≥250 交易日才产出分位，更短→缺失并声明占比）；5 年固定窗口降为敏感性。月末最后交易日快照。净资产为负 PB 剔除出分位序列。分位越低 → 安全边际越大。

## 数据源
- 东财 datacenter RPT_VALUEANALYSIS_DET（2018-01-02 起，≈8.6 年，日频；**退市股不可得**）
- registry 登记样本期：2018-01+

## 预期符号（registry 锁定 2026-08-25）
−（分位越低得分越高；登记后防改口，符号锁定）

## 检验状态
⏳ **待检验**（设计已审，v2.1 定稿 2026-08-25；registry #19；W-编号草案 W-PB_PCTL-DESIGN-20260825-01 挂起）。P4 阶段 v3 全流程检验（**分段报告 2018-2022 / 2023+**）。未检验前权重为实验性（生产开关 fail-closed 拒绝实盘）。

## 风险
- 退市股在估值历史接口完全缺失 → 幸存者偏差（高估方向），回测期量化声明
- 与 EP/BP、PE_PCTL 相关性高 → 共线性闸门 |corr|>0.7 强制检查（价值组）
- 周期股净资产口径波动（减值/增发）可能扭曲分位

## 相关页面
- [[multi-factor-v2]] — 价值投资决策系统 v3（安全边际分 0.30 权重）
- [[ep-factor]] / [[bp-factor]] — 同属价值维度（绝对估值）
- [[pe-pctl]] — 姊妹因子（PE 分位）
