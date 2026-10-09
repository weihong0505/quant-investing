---
title: The Deflated Sharpe Ratio 论文摄入（DSR）
source_url: G:/股市探究/quant-investing/wiki/raw/papers/deflated-sharpe-ratio-2014.pdf
ingested: 2026-09-11
sha256: ca4a1e834a2954b84eb560776e903329cd9cef318d458aadf6d67bc8166d10b5
tags: [backtest, factor-test]
---

# 摄入：The Deflated Sharpe Ratio（DSR 原始论文）

> 原始资料：`wiki/raw/papers/deflated-sharpe-ratio-2014.pdf`（作者 preprint，First version April 15 2014 / This version July 31 2014）
> 正式出版：Bailey, D. H. & López de Prado, M. (2014). "The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting, and Non-Normality", *Journal of Portfolio Management*, 40(5), 94–107.
> 规范出处：SSRN abstract_id=2460551 · 作者站 davidhbailey.com/dhbpapers/deflated-sharpe.pdf
> 本页为提炼层，原文不可修改；核对细节回 PDF。sha256 为全文 PDF 的 SHA-256。

## 摘要（原文）

With the advent in recent years of large financial data sets, machine learning and high-performance computing, analysts can backtest millions (if not billions) of alternative investment strategies. Backtest optimizers search for combinations of parameters that maximize the simulated historical performance of a strategy, leading to backtest overfitting. The problem of performance inflation extends beyond backtesting. More generally, researchers and investment managers tend to report only positive outcomes, a phenomenon known as selection bias. Not controlling for the number of trials involved in a particular discovery leads to over-optimistic performance expectations. The Deflated Sharpe Ratio (DSR) corrects for two leading sources of performance inflation: Selection bias under multiple testing and non-Normally distributed returns. In doing so, DSR helps separate legitimate empirical findings from statistical flukes.

## 核心结论

1. **问题**：回测优化器在数百万次试验中挑「最好」的那个 = 赢家诅咒，样本外很可能均值回归。论文断言：未控制搜索广度的回测「worthless，无论报告业绩多好」。

2. **DSR 定义（Eq.(2)）**：本质是「阈值换成期望最大夏普」的 PSR，分母与 PSR 完全相同：

   DSR = Φ[ (SR − SR₀) · √(n−1) / √(1 − γ₃·SR + (γ₄−1)/4·SR²) ]

   - SR₀ = E[max SR across N trials]（N 次独立试验的期望最大夏普），由两个量决定：试验次数 N、受检 SR 的方差 σ²。
   - 解析式（EVT）：SR₀ ≈ σ·[ (1−γ)·Φ⁻¹(1−1/N) + γ·Φ⁻¹(1−1/(N·e)) ]，γ = 欧拉-马歇罗尼常数 ≈ 0.5772；或蒙特卡洛模拟 N 次取 max 平均。

3. **五变量**：DSR 共纳入 5 个修正量——非正态（γ₃ 偏度、γ₄ 峰度）、样本长度 n、受检 SR 的方差 σ²、独立试验数 N。前三个进 PSR 的分子/分母，后两个（σ²、N）进 SR₀。

4. **结论**：DSR 把「统计上真的」与「纯运气」分开；与 Harvey & Liu (2014) 的阈值方法互补，可分别套用两套阈值算 DSR。

## 与项目关联

- 防过拟合页 [[overfitting-prevention]] §8 的 DSR 公式即取自本文 Eq.(2)；要点：方差项在 SR₀ 内，非分母附加项。
- 本文是 [[sharpe-ratio-efficient-frontier-2012]]（PSR）的后续。
