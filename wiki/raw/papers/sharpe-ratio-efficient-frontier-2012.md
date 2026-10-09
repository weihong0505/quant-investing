---
title: The Sharpe Ratio Efficient Frontier 论文摄入（PSR）
source_url: G:/股市探究/quant-investing/wiki/raw/papers/sharpe-ratio-efficient-frontier-2012.pdf
ingested: 2026-09-11
sha256: 7a756315dc645e343f9b619a727adbd10fde7347af14ae7000bdf3c99397b0e5
tags: [backtest, factor-test]
---

# 摄入：The Sharpe Ratio Efficient Frontier（PSR 原始论文）

> 原始资料：`wiki/raw/papers/sharpe-ratio-efficient-frontier-2012.pdf`（作者 preprint，First version May 2008 / This version July 2012）
> 正式出版：Bailey, D. H. & López de Prado, M. (2012). "The Sharpe Ratio Efficient Frontier", *Journal of Risk*, 15(2), 3–44.
> 规范出处：SSRN abstract_id=1821643 · 作者站 davidhbailey.com/dhbpapers/sharpe-frontier.pdf
> 本页为提炼层，原文不可修改；核对细节回 PDF。sha256 为全文 PDF 的 SHA-256。

## 摘要（原文）

We evaluate the probability that an estimated Sharpe ratio exceeds a given threshold in presence of non-Normal returns. We show that this new uncertainty-adjusted investment skill metric (called Probabilistic Sharpe ratio, or PSR) has a number of important applications: First, it allows us to establish the track record length needed for rejecting the hypothesis that a measured Sharpe ratio is below a certain threshold with a given confidence level. Second, it models the trade-off between track record length and undesirable statistical features (e.g., negative skewness with positive excess kurtosis). Third, it explains why track records with those undesirable traits would benefit from reporting performance with the highest sampling frequency such that the IID assumption is not violated. Fourth, it permits the computation of what we call the Sharpe ratio Efficient Frontier (SEF), which lets us optimize a portfolio under non-Normal, leveraged returns while incorporating the uncertainty derived from track record length. Results can be validated using the Python code in the Appendix.

## 核心结论

1. **PSR 定义**：在收益非正态下，估计夏普 SR 超过给定阈值 SR* 的概率（置信度）。收益点估计即使非正态仍渐近正态（Mertens 2002；Opdyke 2007 扩展到平稳遍历），但其方差会被偏度/峰度放大。

2. **关键公式**（分母即 SR 估计量的标准差，Eq.(8)）：

   PSR = Φ[ (SR − SR*) · √(n−1) / √(1 − γ₃·SR + (γ₄−1)/4·SR²) ]

   - γ₃ = 偏度，γ₄ = **普通峰度**（正态=3），n = 样本数，Φ = 标准正态 CDF。
   - 负偏 + 正超额峰度不改变夏普点估计本身，但会放大其方差、抬高置信带（不确定性）；需更长 track record 或更高采样频率补偿。

3. **四应用**：(a) 推算「证明 SR 超过阈值」所需的最小 track record 长度（minTRL）；(b) 刻画 track record 长度与负偏/峰度之间的权衡；(c) 解释为何「行为差」的收益分布应尽量用最高采样频率报告（IID 不违反前提下）；(d) Sharpe ratio Efficient Frontier（SEF）：在非正态、含杠杆收益下优化组合，并纳入 track record 长度带来的不确定性。

## 与项目关联

- 防过拟合页 [[overfitting-prevention]] §8 的 PSR 公式即取自本文 Eq.(8)。
- 本文是 [[deflated-sharpe-ratio-2014]]（DSR）的前作：PSR 用「固定阈值」，DSR 把阈值换成「期望最大夏普」。
