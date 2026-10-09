---
title: DY因子 — 股息率
created: 2026-08-25
updated: 2026-08-25
type: concept
tags: [factor, value]
sources: [docs/factor_docs/value_investing_transition_v2.1.md]
confidence: 35
contested: false
status: 待检验
---

# DY因子 — 股息率 (Dividend Yield)

## 定义
DY = 最近 12 个月每股股息（含税，分红方案进度 = "实施分配"）/ raw 现价。股息是真实已实施分配的现金流，价值锚角色；金融股 DY 保留（银行股息有现金流含义）。

## 数据源
- 东财 `stock_fhps_detail_em` / `stock_fhps_em`（分红送转明细，**除权除息日 PIT 对齐**；实测 600000：26 条/27 年）
- ⚠️ 勿用 fhps 的"股息率"快照列——须按最近 12 个月实际实施分配自行计算（raw 现价口径）
- registry 登记样本期：2018-01+

## 预期符号（registry 锁定 2026-08-25）
+（股息率越高得分越高；登记后防改口，符号锁定）

## 检验状态
⏳ **待检验**（设计已审，v2.1 定稿 2026-08-25；registry #20；W-编号草案 W-DY-DESIGN-20260825-01 挂起）。P4 阶段 v3 全流程检验。未检验前权重为实验性（生产开关 fail-closed 拒绝实盘）。安全边际分中 0.05 为**低权重占位防污染**——检验后由证据决定。

## 风险
- raw 现价 vs hfq 口径差异；除权除息日对齐错误 → 未来函数或股息错配
- 不分红/少分红股票 DY=0 → 缺失/中性处理需明确（设计：缺失赋中性分）
- 股息政策变化（周期行业）导致的历史不可比

## 相关页面
- [[multi-factor-v2]] — 价值投资决策系统 v3（安全边际分 0.05 权重）
- [[ep-factor]] / [[bp-factor]] — 同属价值维度
- [[fcf-yield]] — 同为现金流回报维度
