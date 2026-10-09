---
title: FCF_YIELD因子 — 自由现金流收益率
created: 2026-08-25
updated: 2026-08-25
type: concept
tags: [factor, value]
sources: [docs/factor_docs/value_investing_transition_v2.1.md]
confidence: 35
contested: false
status: 待检验
---

# FCF_YIELD因子 — 自由现金流收益率 (Free Cash Flow Yield)

## 定义
FCF_YIELD = TTM 自由现金流 / raw 总市值。FCF = NETCASH_OPERATE − CONSTRUCT_LONG_ASSET（TTM 累计口径：最新期 + 去年年报 − 去年同期）。FCF 是内在价值源泉，弥补 CFO_NI_TTM 只有比率、无 FCF 绝对水平的缺口。

## 数据源
- 东财 datacenter RPT_DMSK_FN_CASHFLOW（1998 起，季度；排序必须 REPORT_DATE）
- **PIT 对齐：NOTICE_DATE 实测为修订日非首次公告日 → 必须采用首次公告快照固化口径**（⚠️ yjbb"最新公告日期"是否同款修订日待 P1 实测，P1 出口做 fhps 业绩披露日期交叉校验）
- **金融股（银行/保险/证券/多元金融/信托）：FCF 语义失效（经营现金流≈存贷款流量），剔除出打分（中性化→0）；CFO 门槛同样豁免**
- registry 登记样本期：2018-01+

## 预期符号（registry 锁定 2026-08-25）
+（FCF 收益率越高得分越高；登记后防改口，符号锁定）

## 检验状态
⏳ **待检验**（设计已审，v2.1 定稿 2026-08-25；registry #21；W-编号草案 W-FCF_YIELD-DESIGN-20260825-01 挂起）。P4 阶段 v3 全流程检验。未检验前权重为实验性（生产开关 fail-closed 拒绝实盘）。安全边际分中 0.05 为**低权重占位防污染**——检验后由证据决定。

## 风险
- 资本开支周期导致 FCF 波动大（扩张期 FCF 骤降 → 误判"不便宜"）
- 修订日/首次公告日混用 → 未来函数（回测必须首次公告快照固化）
- 金融股 FCF 无意义 → 必须剔除出打分（中性化→0）

## 相关页面
- [[multi-factor-v2]] — 价值投资决策系统 v3（安全边际分 0.05 权重）
- [[cfo-ni-ttm]] — 盈利质量比率（非 FCF 绝对水平）
- [[dy-factor]] — 同为现金流回报维度
