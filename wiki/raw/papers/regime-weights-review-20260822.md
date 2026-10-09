---
title: regime_based_weights 设计审查报告（SOP §3.0，2026-08-22）核心结论
source_url: G:/股市探究/quant-investing/docs/factor_docs/regime_weights_review_20260822.md
ingested: 2026-08-22
sources: [docs/factor_docs/regime_weights_review_20260822.md]
sha256: 9d5e9fff474922408c9a345e760155d45b21b376e7ad3949546d8dae111ba204
tags: [regime, factor-test, review, decision]
---

# 摄入：regime 动态调权设计审查结论

> 原始资料：`docs/factor_docs/regime_weights_review_20260822.md`（2026-08-22，审查人 AI-C8）
> 审查对象：`docs/research/regime_based_weights.md`（方案 A：滚动 36m ICIR 季度调权）
> 审查性质：设计审批（≠ 统计检验，SOP §3.0.1）　|　结论：**有条件通过（用于研究验证）**
> 本页为提炼层，原文不可修改；核对细节回原始文件。

## 一、核心裁决

1. **36m ICIR 噪声下的季度调权**：ICIR 绝对值不足作为「因子有效」判定依据（项目实测 90 月回测检 3% 超额功效仅 20.3%）；但方案只用 ICIR 做**相对强弱排序**（raw_i/mean 缩放）决定权重微调方向——用途不同，可接受；±50% 上限 + floor=0.1 封顶单期伤害。**增量价值必须实测**（PIT 调权 walk-forward vs 固定权重、2x 成本敏感性）是批准实施的前提。
2. **相关因子同步加成风险**：EP/BP、ROE/GPM/CFO 簇内高相关，公式无相关性惩罚 → 本次不加惩罚（保持「规则简单可解释」红线），缓解三件：① 调权只作用于已过 v3 统计检验 + 共线性闸门的因子；② 验证报告输出每期权重偏离度，检查同簇因子是否同步顶 ±50% 上限；③ 若出现同步顶限 → 加簇级权重上限（另行审批）。
3. **参数敏感性必做**：floor∈{0.05,0.1,0.15}、max_dev∈{0.4,0.5,0.6}、ic_window∈{30,36,42} 各 ±20% 扰动；floor=0.1 语义提醒：ICIR≈0 时 raw=0.1 而非 0——防归零的同时拖慢「失效→降权」响应。
4. **先检验后集成纪律**：未被 v3 检验的因子不得参与调权；调权规则样本外确定（公式与参数以定稿日冻结，禁止按回测回调参数，一次确认制）；本模块定位研究验证工具，实盘接入需另走审批。
5. **流程违规已纠正**：原 regime_weight_history 无条件 NotImplementedError + 死循环代码先于审批写成 → 本次按 SOP §3.0 补审批，审批通过后才实现，死代码已删除。

## 二、已实施内容（2026-08-22，审批通过后）

- `code/regime_weights.py`：`regime_weight_history(base_weights, factors_ic, quarterly_dates, ic_window=36, floor=0.1, max_dev=0.5)`——每调权日取 index≤qd 的最近 ic_window 个月 IC 算 ICIR → 调权 → 权重历史 DataFrame；严格 PIT
- 验证：`code/validate_c8_regime.py` **4/4 通过**（抽查 2 调权日与逐期手算一致、与单期函数窗口化等价、未来数据污染不影响历史权重、<12m 短样本保持基准权重）；输出 `docs/review_2026-08/C8_validation_output.txt`

## 三、红线与遗留

- **红线**：验证显示调权增益（净成本）不稳健或 2x 成本下消失 → 方案 A 终止，回设计阶段
- **遗留**：真实历史 IC 数据（依赖数据层/东财解封）到位后执行 §5 验证（对比固定权重、换手增量、2x 成本、参数敏感性）；验证报告完成后回填本报告；同簇顶限出现 → 簇级上限方案另走审批

## 相关页面

- [[market-state-identification]] — 市场状态识别概念页（本方案为当前唯一量化 regime 机制）
- [[factor-testing-methodology-review]] — v3 滚动 36m ICIR 观察线（本方案复用的统计量）
- [[backtest-engineering-spec-v2-review]] — 90 月回测功效 20.3% 实测（本审查第 2.1 节依据）
