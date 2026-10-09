---

title: 回测引擎 backtest.py

created: 2026-08-21

updated: 2026-08-25

type: entity

tags: [system, tool, backtest]

sources: [G:/股市探究/quant-investing/code/backtest.py, backtest_engineering_spec_v2.1.md]

confidence: 80

---



# 回测引擎 backtest.py



## 概述

按 [[backtest-engineering-spec]] 实现的自研月度调仓回测引擎，

真实成本 + T+1 执行 + 涨跌停 + 停牌顺延 + 公司行为，引擎算术层经金样本对账验证（**103/103**，合成数据手算对账）——仅验证算术正确性，未接入全量真实数据，不构成策略验证。

> **当前状态**：真实数据回测：CSI300 试点已跑通（2026-08-22，e2e_pipeline --universe csi300，结果见 output/backtest_result_20260822.csv），全 A 未拉全；金样本 103/103 为合成数据手算对账验证（2026-08-22 实跑）——仅验证算术正确性，未接入全量真实数据，不构成策略验证。



## 代码位置

`G:/股市探究/quant-investing/code\backtest.py`

配套测试：`test_golden_samples.py`（手算逐分对账）



## 双口径铁律（已实现：2026-08-22 C3 方案 A 修复落地，金样本 Case 8 除息对账验证，实跑 103/103 PASS）

- **信号/收益层**：hfq（总收益口径，含分红再投）——组合日收益 = Σ 持仓权重 × hfq 日收益（hfq_t/hfq_{t-1} − 1）合成，权重用 t-1 日 raw 收盘市值；现金按 0 收益计入；执行日按执行价 raw→hfq 换算（hfq_exec = 成交价 × 当日复权因子 hfq_t/raw_t）拆隔夜/日内两段；成交成本作当日负向现金流；⚠️ 严禁 Σ shares × hfq_price 合成净值（hfq 价格水平跨股不可比）

- **执行/估值/成本层**：raw（成交价、股数、整手、税费、涨跌停判定、现金分红入现金、送转调股数）

- **对账**：raw 净值（nav）仅作交易对账；月收益与年化/波动/夏普/回撤全部基于合成 hfq 总收益序列（nav_hfq / daily_returns / monthly_returns）

- 复权因子 = hfq_t/raw_t（可推导常数；除息/送转日因子跳变即分红再投的体现）

## 核心能力

| 能力 | 实现 |

|------|------|

| 成本 | 佣金万2.5双边(最低5元) + 印花税时变(2023-08-28 千1→万5) + 过户万0.1 + 市值四档滑点 5/10/20/30bp |

| 执行 | T 收盘信号 → T+1 raw 开盘价；一字涨停不买/跌停不卖；免检白名单（新股前5日：科创 2019-07-22 起/创业 2020-08-24 起/主板 2023-02-17 后；北交所首日；恢复上市首日；退市整理期首日）跳过涨跌停判定（is_limit_free，list_dates 或行情推断上市日） |

| 顺延 | 停牌/涨跌停顺延 5 日，每日重判，开板成交；复牌首日跳空 >20% 该次顺延整体放弃（不再继续顺延） |

| 整手 | 买入 100 股取整；卖出零股一次性清仓；单笔 <2万跳过 |

| 公司行为 | 除息日现金分红入账 + 送转股数调整（逐日应用） |

| 现金缓冲 | 交易额+成本超现金时逐手递减（修复 100% 仓位买不进 bug） |

| 净值 | 首期从首次 T+1 开盘起算；月末收盘估值 + 持仓快照 positions_history（code→股数，与 trades 对账一致） |

| 年化 | annual_return 按实际日期跨度 365.25/days（修正首段非整月问题） |

| 换手 | 实际单边换手 actual_turnover = 月内 trades 成交金额 ÷ 月末净值（年化 = 12×月均，turnover_annualized）；目标换手 Σ\|Δw\| 保留作对照列（turnover） |

| 缺失市值 | _mcap_of 缺失按最保守档 30bp 计滑点 + verbose 告警 |

| 基准对比 | Performance 可选 benchmark_nav：超额年化/超额夏普/相对回撤/跟踪误差/信息比率；BacktestResult.benchmark_nav 携带基准净值 |



## 修复过的真实 Bug（金样本合成数据测试价值——仅验证算术正确性）

1. 持仓字典未回写（买入后持仓丢失）

2. 调仓 pending 列表未消费（每期重复执行）

3. 100% 仓位买不进（成本超现金）

4. 公司行为只在月末应用（月中除权日丢失）



## 相关页面

- [[backtest-engineering-spec]] — 实现依据（v2.1 定稿）

- [[sell-signals]] — 输入信号的上游模块

- [[sop-v1.1]] — §3.3 执行规则出处

