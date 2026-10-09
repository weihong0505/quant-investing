---
title: 质量因子组设计方案 v2（MImo V2.5 Pro 审查通过）核心结论
source_url: G:/股市探究/quant-investing/docs/factor_docs/quality_factors_v2.md
ingested: 2026-08-22
sources: [docs/factor_docs/quality_factors_v2.md + docs/factor_docs/quality_factors_v1_review.md]
sha256: 9e8517233569c9d4083e1ce98a69924dc017f32b592ebf725fb696a2a93f6526
tags: [quality, factor-test, review, decision]
---

# 摄入：质量因子组设计方案 v2 审查结论

> 原始资料：`docs/factor_docs/quality_factors_v2.md`（v2 定稿，2026-08-20）
> 审查报告：`docs/factor_docs/quality_factors_v1_review.md`（MImo V2.5 Pro 对 v1 的独立审查）
> 本页为提炼层，原文不可修改；核对细节回原始文件。

## 一、审查状态

- v1 经 MImo V2.5 Pro 独立审查（quality_factors_v1_review.md）后出 v2；**v2 已通过审查（✅）**，v1 的 4 项 P0 全部修复 + P1 建议采纳 + 学术引用修正。

## 二、v1→v2 关键修订（审查裁决）

1. **删除 NPM_TTM**（与 ROE 冗余，审查 Q1/Q4 裁定）——质量因子定稿 4 个：ROE_TTM / GPM / CFO_NI_TTM / LEV
2. **ROE_TTM 改每股口径**（P0-1）：TTM每股收益 / 最新每股净资产（归母）——zcfz 无「归母所有者权益」字段，原分子归母÷分母合并口径错配
3. **CFO_NI 改 TTM 口径**（P1），声明两处偏差：合并现金流÷归母净利、期末 vs 加权股本
4. **逐股 PIT 最新报告期**（P0-2）：L = max{报告期 | 公告日期 ≤ 今日}，未披露自动回退上一期；拉 7 个报告期（20241231~20260630）
5. **金融行业中性化**（P0-3）：金融股 4 个质量因子全赋中性分 0；非金融股 GPM/ROE_TTM/LEV 行业内 z-score，CFO_NI 全市场
6. **负利润符号保护**（P0-4）：TTM每股收益 ≤0 → CFO_NI 直接赋 −3，防「双负得正」
7. **打分体系**：winsorize ±3σ → z-score → 乘方向系数 → 加权求和（v1 排名法改 z-score 加权）

## 三、权重与共线性闸门

- 10 因子权重：EP 0.20 / BP 0.20 / MOM_60D 0.15 / ROE_TTM 0.12 / TURNOVER 0.10 / GPM 0.06 / CFO_NI 0.05 / LOG_MCAP 0.05 / VOL_RATIO 0.05 / LEV 0.02（价值40%+质量25%+动量15%+流动性10%+规模5%+情绪5%）
- 集成前共线性闸门：|corr|>0.7 的两因子砍 IC 较弱者或权重减半；EP 必须纳入（与 ROE_TTM 天然高相关）；单因子权重 ≥0.12 或 ≤0.02 的调整须附 RankIC 依据

## 四、学术引用修正（v2）

- ROE：Fama-French (2015) RMW；Piotroski (2000) F-Score 首项实为 ROA>0（措辞修正）；F-Score 结论限于高 BM 价值股子样本（外推降级表述）
- GPM：Porter 竞争战略议价权代理；Novy-Marx (2013) 实为 GP/A（毛利润/总资产），与销售毛利率不同 → GP/A 列 v1.1 路线
- CFO_NI：Sloan (1996) 应计异象的代理变量（非应计项本身）
- LEV：Piotroski LEVER 项实为「长期杠杆率同比下降」（Δ），非低杠杆水平；Graham 防御型低负债标准为独立依据

## 五、检验计划（集成后，截至 2026-08-22 未执行）

- |ICIR|>0.5 保留；0.3–0.5 且多空单调显著 → 观察期；5 分组多空单调性；因子自相关；8 月中报季覆盖率报告
- ⚠️ 10 因子统计检验列实测全空（复盘 S1）：本方案目前只过设计审批，未过统计检验；MOM_60D 试点检验已淘汰（见 [[s1-pilot-factor-tests-20260822]]）

## 相关页面

- [[factor-testing-methodology-review]] — v3 检验方法论（本方案检验计划的执行规范）
- [[gpm-caliber-verify-2026-08]] — GPM 字段口径实测（累计口径 → 修改建议 TTM）
- [[s1-pilot-factor-tests-20260822]] — S1 试点检验输出
