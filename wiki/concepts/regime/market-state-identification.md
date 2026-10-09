---
title: 市场状态识别（Regime Identification）
created: 2026-08-22
updated: 2026-08-25
type: concept
tags: [regime, macro, factor-test, backtest]
sources: [raw/papers/backtest-engineering-spec-v2-review.md, raw/papers/factor-testing-methodology-review.md, raw/papers/regime-weights-review-20260822.md, raw/articles/data-source-testing-2026-08.md]
confidence: 35
contested: false
---

# 市场状态识别（Regime Identification）

## 定义

市场状态（regime）= 影响因子/策略收益结构的持续性市场环境（风格、流动性、制度特征）。市场状态识别 = 判断当前处于哪种状态、状态何时切换，用于回测样本分层、判定标准锚定、因子衰减监控与权重调整。

## 当前认知状态（2026-08-22）

**项目对 A 股结构断点的认知全部来自定性事实 + 回测分层锚点，无量化验证**（confidence: 35）：

1. **三个结构断点（定性事实，公开市场事件）**：
   - [[2017-style-shift]] — 2017 风格切换：白马蓝筹行情、小盘溢价终结（参考段 2017-2018 依据）
   - [[2021-bubble-burst]] — 2021-02 抱团瓦解：核心资产泡沫破裂（核心段起点）
   - [[2024-microcap-crisis]] — 2024 微盘危机：微盘流动性踩踏 + 924 行情（观察线结构断点）
2. **回测分层锚点（规范已写死，见 [[backtest-engineering-spec-v2-review]]）**：2017-2018 = 参考段（辅助证据，触发线 = 净超额年化 ≤−3% 或超额回撤 <−5%）；2019+ = 主段；2021-02+ = 核心段（结构最接近当前，~66 月）；判定标准（净超额 >0、回撤不劣于双基准）必须在此背景下解读
3. **观察线结构断点（[[factor-testing-methodology-review]] Q7）**：滚动 36m ICIR 观察线第③条——标注结构断点（2021-02 抱团瓦解、2024 微盘危机）后 12 个月 ICIR 未回正 → 因子至少降级「观察」
4. **唯一量化 regime 机制**：滚动 36m ICIR 季度调权（方案 A）——设计审批**有条件通过**（[[regime-weights-review-20260822]]），定位研究验证工具；增量价值（调权增益 vs 换手成本增量）**尚未实测**（依赖真实历史 IC 数据）

## 未解决问题或争议

- 无显式市场状态分类器（牛/熊/震荡/风格状态的判定指标未定义）——现状只有「断点 + 锚点」，没有「当前状态」的实时判定
- 三个结构断点本身**无量化检验**（无断点检测统计量，如结构突变/ICIR 分段检验）
- 36m ICIR 调权增益未验证：参数敏感性（floor/max_dev/ic_window ±20%）、同簇因子同步顶限检查、2x 成本敏感性均未执行（红线：不稳健即终止方案 A）
- 数据降级期（东财 spot 被封，MOM_60D 全中性 0 分）→ 「状态判定依赖的数据」与「状态本身」的耦合可靠性未评估

## 相关概念

- [[2017-style-shift]] / [[2021-bubble-burst]] / [[2024-microcap-crisis]] — 三个结构断点
- [[factor-decay]] — 因子衰减检测（滚动 36m ICIR 观察线）
- [[regime-weights-review-20260822]] — 唯一量化调权机制（raw/papers）
- [[backtest-engineering-spec-v2-review]] — 样本分层与判定锚点（raw/papers）
