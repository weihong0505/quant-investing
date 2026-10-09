---
title: 价值×动量 FM 增量检验裁决（M5）
created: 2026-08-22
updated: 2026-08-25
type: query
tags: factor, momentum, value, factor-test, backtest, decision
sources: 
  - docs/review_2026-08/M5_先验当结论.md
  - factor_testing_methodology_v3.md
confidence: 85
---

# 价值×动量 FM 增量检验裁决（M5）

## 核心结论

1. **MOM_60D 单变量 signed IC 反向显著**：NW-t≈−3.6，41 月，超过 3.0 显著线，方向与 registry 锁定 + 相反。按防改口三件套淘汰并待反转重登记。
2. **FM 控制 ln_mcap+行业后 MOM 增量不显著**：NW-t=−1.08，42 月。反向效应主要由规模/行业渠道传导，独立截面预测力弱。
3. **EP/BP 试点窗口 FM 增量未达 2.0 线**：EP t=+1.94 / BP t=+0.61，16 月全模型。数据未就绪前不下淘汰结论，维持观察。

## 数据与样本说明

- **样本范围**：2023-02~2026-08（43 月 < 60 月，v3 §1）
- **样本限制**：仅现存股票（幸存者偏差）、行业=东财行业最新快照（非申万、非 PIT）、市值=流通市值代理、财务仅 3 期 TTM 试点窗口。
- **数据来源**：pilot_mom60d 缓存 2026-08-22（CSI300 试点 101 只）

## 对项目决策的含义

- **MOM_60D 权重归零（或方向反转后重检）**：独立截面预测力弱，需重新评估。
- **其余 8 因子重归一化**：待用户拍板。

## 相关页面

[[momentum-60d]] [[factor-direction-map]] [[project-review-2026-08]]