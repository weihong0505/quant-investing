---
title: S1 试点因子检验输出（2026-08-22）：MOM_60D 反向显著淘汰 / VOL_RATIO 淘汰
created: 2026-08-22
updated: 2026-08-25
type: query
tags: [factor-test, backtest, decision, momentum]
sources: [raw/articles/mom60-caliber-and-test-2026-08.md, docs/factor_docs/test_MOM_60D_20260822.md, docs/factor_docs/test_VOL_RATIO_20260822.md]
confidence: 85
---

# 查询归档：S1 试点因子检验输出

## 查询目的

复盘 S1（10 因子零检验）：跑通 v3 方法论全流程的**首次真实数据试点**，验证检验管线可用性并产出首批结论。

## 环境与复现

- 脚本：`code/factor_test_suite.py`（v3 全文流水线）+ `code/pilot_mom60d.py`
- 数据：新浪 hfq+raw 真实行情；样本 101~120 只 CSI300 成分，2023-02~2026-07（43 月，**<60 月 → 结论初步**，v3 §1）
- 种子 20260822；数据版本 hash `da0a3831cc4816dc…`；N'=10 → 显著性线 max(3.0, Bonf(10)) = **3.000**
- 方法论：factor_testing_methodology_v3.md（MImo 两轮审查定稿）

## 结果

| 因子 | 判定 | 关键证据 |
|------|------|---------|
| MOM_60D | **淘汰**（初步） | ICIR −0.412；signed NW-t **−3.63**（预登记方向 + 上显著反向）；下跌月/高波动月条件 IC <0；PT MR p=0.9885 未达；三重稳健性全未过；净多空年化 −30.0%；夏普 −1.02；OOS 24m 确认失败 |
| VOL_RATIO | **淘汰**（初步） | 同批试点完整检验（test_VOL_RATIO_20260822.md）；且已弃用（multi_factor_value.py L59）但 registry 仍登记——正式批次前需裁决（RUNBOOK §1.1） |

## 结论与后续

- 管线可用：合成数据自检 + 真实数据试点均跑通（有效→保留 / 噪声→淘汰 / 反向→淘汰 三分类行为正常）
- MOM_60D 在 43 月样本内显著反向 → 待全 A 长样本（2017+）复核后再定去留
- 10 因子完整检验待 S2 数据层（2015+ 全 A hfq+raw 日线、逐期 PIT 财务、退市股、ETF 基准）；回填行见 `docs/factor_docs/backfill_*_20260822.md`，**未写入 registry**（待 MImo 审批后追加，防改口三件套）

## 相关页面

- [[mom60-caliber-and-test-2026-08]] — 口径实测 + 检验全文提炼（raw/articles）
- [[momentum-60d]] — MOM_60D 因子概念页
- [[golden-samples-103-pass-20260822]] — 引擎层对账（本查询之上的统计层试点）
