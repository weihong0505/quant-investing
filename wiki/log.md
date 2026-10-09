# Wiki Log — A股量化价值投资知识库

> 操作日志。追加写入，记录每次操作的缘由以便复盘。
> 格式：`## [YYYY-MM-DD] action | subject`
> 操作者: AI / 用户 | 原因: 为什么做 | 影响: 改了什么 | 备注: 复盘点
> 当文件超过 500 条时轮转：rename to log-YYYY.md，start fresh.

---

## [2026-08-21] create | Wiki 初始化

- **操作者**: AI (Hermes Agent)
- **原因**: 用户看完抖音视频（六郎Talk AI: Obsidian搭建AI知识库），决定为量化投资项目搭建 LLM Wiki 知识库。视频核心观点：LLM Wiki "资料进来时先整理" 优于 RAG "问的时候再找"。
- **影响**:
  - 创建目录结构：raw/, entities/, concepts/, comparisons/, queries/, _archive/
  - 创建 SCHEMA.md：定义了量化投资领域的标签体系、页面规范、操作日志规范
  - 创建 index.md：初始16个页面的内容目录
  - 创建 log.md（本文件）
- **备注**: Wiki 路径 `C:\Users\asus\wiki`，可直接用 Obsidian 打开作为 vault。

## [2026-08-21] create | 核心因子概念页 × 10

- **操作者**: AI (Hermes Agent)
- **原因**: 将 multi_factor_value.py 中的10个因子从代码注释升级为结构化知识页面，每个因子包含定义、计算公式、当前权重、方向、处理规则、已知问题。
- **影响**: 创建了 concepts/factors/ 下10个因子页面：ep-factor, bp-factor, roe-ttm, gpm-factor, cfo-ni-ttm, lev-factor, momentum-60d, turnover-factor, log-mcap, vol-ratio
- **备注**: 因子页面是 Wiki 的核心资产，后续每次回测/检验结果都应更新到对应因子页。

## [2026-08-21] create | 系统实体页 × 4

- **操作者**: AI (Hermes Agent)
- **原因**: 记录系统的关键组件，建立代码与知识的链接。
- **影响**: 创建了 entities/system/ 下4个页面：multi-factor-v2, akshare, mimo-review, sop-v1.1
- **备注**: 系统实体页记录的是"我们的工具是什么"，概念页记录的是"我们知道什么"。

## [2026-08-21] create | 对比页 — 因子方向与权重一览

- **操作者**: AI (Hermes Agent)
- **原因**: 将分散在代码中的权重和方向定义汇总为一张对比表，便于快速查阅和调整。
- **影响**: 创建 comparisons/factor-direction-map.md
- **备注**: 每次权重调整后必须同步更新此页。

## [2026-08-21] update | 同步 SOP v1.4 + 回测工程规范定稿 + 新代码模块

- **操作者**: AI (Hermes Agent)
- **原因**: 今日完成两大 P0 工程规范的两轮 MImo 审查定稿（因子检验方法论 v3、回测工程规范 v2.1），并落地 5 个新代码模块（回测引擎/卖出信号/IC监控/walk-forward/regime调权），全部通过测试（金样本对账 25/25 PASS）。同步入 Wiki。
- **影响**:
  - 更新: entities/system/sop-v1.1.md（内容升级至 v1.4 版本演进表）
  - 更新: entities/system/multi-factor-v2.md（模块化架构）
  - 创建: backtest-engine, factor-testing-methodology, backtest-engineering-spec, sell-signals, ic-monitor, walk-forward, regime-weights（7 个实体页）
  - 创建: concepts/risk-management/backtest-cost-model, dual-caliber-adjustment（2 个概念页）
  - 更新: index.md（16 → 26 页）
- **备注**: 关键知识沉淀——卡玛≥0.5 是标定错误（基准卡玛实测 0.006~0.010）；基准必须用 ETF 全收益（价格指数虚增超额2%/年）；东财接口跨两轮 ≥24h 持续被封（主源降级预案为刚需）。

## [2026-08-21] update | 项目路径迁移 C盘→G盘 + 全库路径修正

- **操作者**: AI (Hermes Agent)
- **原因**: 项目正式目录已迁移至 G:/quant-investing（code/docs/wiki 三层），本会话工作目录 G:/quant-investing/code 的新成果同步至 G 盘，并修正全部页面残留的 C 盘路径引用。
- **影响**:
  - 复制新代码模块至 G:/quant-investing/code/：backtest.py, sell_signals.py, ic_monitor.py, walk_forward.py, regime_weights.py, test_golden_samples.py
  - 复制 research/ 至 G:/quant-investing/docs/research/
  - 批量修正 wiki 11 个页面 + docs/SOP.md 的路径引用（G:/quant-investing/code → G:/quant-investing/code 或 /docs）
  - docs/SOP.md 版本号 v1.1 → v1.4 同步
- **备注**: G:/quant-investing/code 已不再是正式目录，仅剩本会话新建模块（已同步），后续工作一律在 G:/quant-investing 下进行。

> ⚠️ **勘误（2026-08-22，复盘 W3）**：本条「影响」末项原文「批量修正 wiki 11 个页面 + docs/SOP.md 的路径引用（G:/quant-investing/code → G:/quant-investing/code 或 /docs）」自相矛盾——箭头左侧写成了与右侧相同的 G 盘路径。**正确内容应为：C 盘路径 → G 盘路径的全量替换**（即把页面残留的 `C:/quant-investing/...`、`C:\\Users\\asus\\...` 等旧引用改为 G:/quant-investing 对应路径）。原文保留以示审计；本次勘误不影响该条目其余事实（代码/研究目录确已复制至 G 盘）。
> 补充（2026-08-22，W3 收尾）：原条「备注」中"G:/quant-investing/code 已不再是正式目录"指 **C 盘旧目录**（C:/quant-investing/...），非 G 盘新目录。

## [2026-08-22] create | 项目复盘诊断（错误与误区）

- **操作者**: AI (Hermes Agent)
- **原因**: 用户要求不留情面的项目复盘——明确指出错误和误区、提出改正方向，结果与全部思考过程入 Wiki。只诊断不实施。
- **影响**:
  - 创建 comparisons/project-review-2026-08.md（四层 22 项问题：结构 S1-S3 / 代码 C1-C10 / Wiki W1-W3 / 认知 M1-M6 + 改正方向 10 条 + 思考过程 + 项目状态盘点）
  - 更新 index.md（28 页）
- **备注**: 复盘实锤——10 因子零检验（registry 统计列全空）、run.py 三元解包二元组必崩、simple_backtest 未来函数+qfq 违规、px_hfq 零使用（hfq 铁律未落地）、G盘 data_cache/output/logs 不存在（主流程从未运行）、Wiki 两页声明与代码不符。详见复盘页，矛盾页面见 frontmatter contradictions 字段。

## [2026-08-22] create | 复盘分项任务包（供其他 AI 修改）

- **操作者**: AI (Hermes Agent)
- **原因**: 用户要求把 22 项问题拆成独立详细任务文件，以便逐个交给其他 AI 修改。
- **影响**: 创建 docs/review_2026-08/ 任务包：00_README.md（清单+修改顺序+环境须知）+ S1-S3/C1-C10/W1-W3/M1-M6 共 22 个自包含任务文件（现状/证据/为什么错/修改要求/验收标准/需同步文档）；复盘页头部挂任务包入口。
- **备注**: 任务包建议顺序：C1→C2→S3 打通入口 → C10→S2 数据地基 → S1→M5→M2 因子检验 → C3→C4→C5 引擎补齐 → C6/C7/C8 工具链；文档类（M1/M3/M4/M6/W1-W3）随时可做。README 内含 CRLF/BOM 编辑陷阱与 -E 运行等环境须知。


## [2026-08-21] create | 本地AI配置页面
- **操作者**: AI (Hermes Agent)
- **原因**: 用户要求搭建本地AI用于知识库前期数据整理。安装Ollama + Qwen2.5-7B，创建调用脚本和摄入脚本。
- **影响**: 
  - 安装 Ollama 0.32.15 到 G 盘
  - 创建 code/local_ai.py（基础调用封装）
  - 创建 code/wiki_ingest.py（资料摄入脚本）
  - 创建 entities/system/local-ai.md（配置文档）
  - 更新 index.md（+1页）
  - 更新 SOP.md（新增§8 本地AI）
- **备注**: 模型存储在 G:\quant-investingi\models\，推理时占用GPU但不影响CPU任务。

## [2026-08-21] update | 项目迁移至G盘
- **操作者**: AI (Hermes Agent)
- **原因**: 用户要求将所有项目文件迁移到G盘统一管理。
- **影响**:
  - quant_analysis → G:\quant-investing\code  - wiki → G:\quant-investing\wiki  - factor_docs → G:\quant-investing\docsactor_docs  - SOP → G:\quant-investing\docs\SOP.md
  - 旧目录已归档（_ARCHIVED_20260821）
  - 所有代码/配置/技能中的路径引用已更新
- **备注**: Obsidian vault 在 G:\quant-investing\wiki\，Local REST API 插件已配置（HTTPS port 27124）。

## [2026-08-21] create | Wiki 知识库初始化
- **操作者**: AI (Hermes Agent)
- **原因**: 基于抖音视频（六郎Talk AI: Obsidian搭建AI知识库）的启发，为量化投资项目搭建 LLM Wiki 知识库。
- **影响**:
  - 创建目录结构（raw/entities/concepts/comparisons/queries/_archive）
  - 创建 SCHEMA.md（领域定义+标签体系+规范）
  - 创建 index.md（16个初始页面索引）
  - 创建 log.md（操作日志）
  - 创建10个因子概念页 + 4个系统实体页 + 1个对比页
- **备注**: Wiki 路径 G:\quant-investing\wiki\，可通过 Obsidian + Local REST API 双向读写。


## [2026-08-22] fix | sell_signals.py 三处逻辑修复（复盘 C5）

- **操作者**: AI (Hermes Agent)
- **原因**: 项目复盘 C5 三处逻辑问题（止损基准价错位 / keep_rank 死代码 / 等权现金拖累），按用户拍板方案修复：方案 B（止损记账价改 T+1 开盘价）、方案 1（keep_rank 与 top_n 联动）、方案一（候选不足等比放大）。
- **影响**:
  - code/sell_signals.py：删除 SellRules.keep_rank；新增 exec_price_table（成交价表，T+1 开盘价口径，停牌缺数时止损暂停）与 sell_log（卖出原因记录）参数；等权改 1/len(candidates)（总权重恒 1.0）；docstring 全面声明口径；冒烟测试新增 3 组针对性断言（12 PASS / 0 FAIL）
  - 新增 code/validate_c5_fix.py（19 断言全过，含卖出路径不变量：任何消失持仓必有卖出记录）+ docs/review_2026-08/C5_validation_output.txt
  - 更新 wiki/entities/system/sell-signals.md（卖出规则口径按最终方案同步）
- **备注**: 未动 backtest.py / multi_factor_value.py（其他 AI 并行修改中）；SOP.md §4 未提及卖出规则参数，无需同步；validate_c5_fix.py 为验收交付物保留在 code/，后续可归档。

## [2026-08-22] fix | C6 ic_monitor 补 v3 主判定线（signed NW-t / Bonferroni）

- **操作者**: AI-C6
- **原因**: 复盘 C6 — ic_monitor.py 自述"与 v3 判定线一致"但只实现了 v3 §8 观察线（ICIR 分档），v3 §9 主判定线（signed NW-t ≥ max(3.0, Bonf(N'))）完全缺失，监控器永远给不出 通过/淘汰 结论；naive |t| 会放行反向强因子（v3 已纠正过的错误）。
- **影响**:
  - code/ic_monitor.py：新增 `nw_t()`（NW 1994 带宽 floor[4×(N/100)^(2/9)]，Bartlett 核，与 statsmodels cov_hac_simple 实测一致 ~1e-15）、`bonf_threshold()`（单侧 α=0.05，N'=37 处 z≈2.9997，max(3.0,·) 无缝衔接）；`ICAlerts.check(ic, expected_sign=1, n_star=1)` 增加主判定线（signed_t≥阈值→通过；signed_t≤−3.0→淘汰反向强因子；其余→观察），观察线保留为辅助监控；`ic_summary`/`report` 增加 nw_t、signed_t 字段与列
  - code/test_ic_monitor_c6.py：22 项验收用例全过（强正→通过 / 噪声→不通过 / 反向强→淘汰 / NW-t vs statsmodels <1e-6 / 冒烟+新列），输出 docs/review_2026-08/C6_validation_output.txt
  - docs/review_2026-08/C6_ic_monitor缺主判定线.md：验收勾选
- **备注**: 回归约束 — regime_weights.py 仅用 ic_series/rolling_icir，接口未变；check/report 新增参数均带默认值，向后兼容。

## [2026-08-22] fix | C3 落地 hfq 收益层（双口径铁律方案 A）

- **操作者**: AI-C3
- **原因**: 复盘 C3 — px_hfq 零使用：净值 = cash + Σ shares×raw 收盘价、月收益 = raw 净值 pct_change，hfq 收益层（含分红再投）铁律未落地；raw 净值被除息日跳水污染、分红收益丢失。
- **影响**:
  - code/backtest.py：run() 改逐日循环；新增 _compose_daily_return（组合日收益 = Σ t-1 收盘 raw 市值权重 × hfq 日收益；执行日按执行价 raw→hfq 换算拆隔夜/日内段；成本作负向现金流；严禁 Σ shares×hfq_price 合成净值）；新增 nav_hfq/daily_returns 输出，月收益与年化/波动/夏普/回撤全部基于合成 hfq 序列；raw 净值仅作交易对账；执行层（成交价/整手/税费/涨跌停/公司行为）保持 raw 不变
  - code/test_golden_samples.py：新增 Case 8 除息金样本（raw 除息日跌 2%、hfq 平、cash_div 0.2 元/股），4 项断言（除息日日收益 0 / 除息月合成月收益无跳变 / 有无 cash_div 合成月收益一致 / 合成净值 = 初始−总成本）——29/29 全 PASS（原 25 项保持）
  - 实测对账：价格波动+多股+多次调仓场景月末合成净值与 raw 净值误差 ~1e-9；除息日恰为执行日场景 hfq 平、raw = 合成 + 分红现金（双口径语义正确）；顺延成交场景月末对账 ~1e-11
  - docs/review_2026-08/C3_px_hfq零使用.md：验收勾选；wiki/entities/system/backtest-engine.md：双口径铁律一节按实现同步
- **备注**: 未改 backtest_engineering_spec_v2.1.md（方案 A 无需改规范）。行为变化：现金分红入账时点由"月末统一入账"改为"除息日当日入账"（更符合 v2.1，无金样本依赖）。顺延成交（停牌/涨跌停 5 日内）的收益归因近似记在执行调用日，误差仅影响单日归因不影响月末对账。C4 任务后续修改与本改动无重叠（本改动集中在 run()/_compose_daily_return）。

## [2026-08-22] fix | C4 回测引擎 7 项规范缺口修复（免检白名单/复牌跳空/基准对比/持仓快照/缺失市值/年化/实际换手）

- **操作者**: AI-C4
- **原因**: 复盘 C4 — 引擎与 v2.1 规范存在 7 项缺口：新股免检白名单未实现（新股前5日开盘价超涨跌停价被误判一字板，虚假拒单）、复牌首日跳空未处理、绩效层无基准对比（净超额是七条判定标准核心）、positions_history 恒空 stub、缺失市值静默按中盘档 10bp、annual_return 假设严格月度等间隔（首段非整月年化偏小）、换手是目标权重换手而非实际成交（系统性高估）。
- **影响**:
  - code/backtest.py：① is_limit_free 免检白名单——科创板/创业板新股上市前 5 个交易日（2019-07-22/2020-08-24 起）、主板 2023-02-17 后新股前 5 日、北交所首日、恢复上市首日（limit_free_dates 显式名单）、退市整理期首日；上市日输入约定：list_dates 参数或 px_close 首个非 NaN 日期推断；在 _buy/_sell/_sell_shares 一字板判定前短路。② 复牌首日跳空 >20% 该次顺延整体放弃（_gap_too_large，不再继续顺延，拍板方案写入注释）。③ Performance 可选 benchmark_nav：超额年化/超额夏普/相对回撤/跟踪误差/信息比率；BacktestResult.benchmark_nav 携带基准净值。④ positions_history 每次月末估值快照（code→股数）。⑤ _mcap_of 缺失市值按最保守档 30bp 计滑点 + verbose 告警（-1.0 哨兵落入滑点末档）。⑥ annual_return 按实际日期跨度 total**(365.25/days)−1。⑦ 实际换手 actual_turnover = 月内 trades 成交金额 ÷ 月末净值（单边，每笔计一次，与 Σ|Δw| 同量纲；年化 = 12×月均 → turnover_annualized）；目标换手保留作对照列。
  - code/test_golden_samples.py：新增 Case 9（科创板上市第2日 +100% 买入成交 / 白名单过期后连续一字涨停放弃）、Case 9c（恢复上市首日跌停价卖出成交 + 板块×时间矩阵直测）、Case 10（停牌2日复牌 +25% 放弃 / +10% 成交）、Case 11（基准超额指标含平基准/实际日期年化）、Case 12（持仓快照与 trades 对账 + 实际换手）、Case 13（缺失市值滑点 30bp + verbose 告警 + 基准常数增长 +1%/月 超额指标手算对账 + BacktestResult 携带基准净值）、Case 14（5 月调仓卖/买双双放弃 → 实际换手 0 < 目标换手 2.0 + 年化手算 + 股数守恒）——103 PASS / 0 FAIL（原 29 项保持）
  - docs/review_2026-08/C4_引擎与规范缺口7项.md：验收勾选；docs/review_2026-08/C4_validation_output.txt：实测输出
  - docs/factor_docs/backtest_engineering_spec_v2.1.md：L117 复牌跳空"放弃"选择写入规范（强制规则）
  - wiki/entities/system/backtest-engine.md：能力表补 7 项
- **备注**: 与并发 AI 的 C4 实现合并——其 3 处缺陷已修正：_mcap_of 返回 0.0 实得 20bp（注释声称 30bp）、实际换手 /2 口径与任务原文"累计实际成交金额/组合净值"不符、Case 9 负对照场景（固定 12 元开盘）第 2 日即开板误成交、Case 12 手算 B=14800 应为 9900。合并后 103/103 全 PASS。



## [2026-08-22] review-prep | C8a regime_weights 审批材料已备 + 代码冻结
- **操作者**: AI-C8a
- **原因**: 复盘 C8 要求"先补审批，再动代码"；本任务仅准备 MImo 独立审批材料并对半成品代码加冻结标注，审批结论由后续独立 AI（C8b）裁决
- **影响**:
  - 新增 docs/factor_docs/regime_based_weights_review_request.md（自包含审批请求：设计要点摘要 / 代码现状 / 5 项待审问题 / 结论填写区 / 实施前置条件清单）
  - code/regime_weights.py：docstring 顶部加冻结标注（不改任何逻辑，冒烟复跑通过）
  - docs/review_2026-08/C8_regime_weights半成品.md：标题下加"审批材料已备，待 C8b 审批"
- **备注**: NotImplementedError 与死代码段未动（属 C8b 审批后处理）；未触碰 backtest.py / sell_signals.py / ic_monitor.py / walk_forward.py

## [2026-08-22] fix | C7 walk_forward.py 名不副实 → 改名 rolling_stats.py（方案 B）

- **操作者**: AI-C7
- **原因**: 复盘 C7 — walk_forward.py 自称"Walk-Forward 滚动回测、防过拟合验证"，实际只对已算好的月收益序列做滑动窗口描述统计；strategy_fn 死参数从未调用；verdict 判定线"oos_win>=0.5 and oos_cum>0 → 通过"无功效依据（项目实测 90 月回测检出功效仅 20.3%，短窗 50% 胜率线会给随机策略 ~40%+ 通过概率）。
- **影响**:
  - code/walk_forward.py → **code/rolling_stats.py**（函数 rolling_window_stats / rolling_stats_summary / one_time_confirmation；docstring 如实写"滚动窗口描述统计（非 walk-forward）"）；删除 strategy_fn 死参数；删除"通过/观察"判定措辞；summary 新增 verdict=证据强度分级（strong/weak/none，按 OOS 总月数 <24/24~89/≥90 分档）+ power_warning（强制附 90 月/20.3% 功效警示）；train_test_consistency 保留为报告项；一次确认制保留
  - 全项目无 .py import walk_forward（已 grep 核实），改名无引用改动
  - 冒烟测试更新并通过（5 窗 OOS=60 月 → verdict=weak；衰减策略被一次确认制拦截；verdict 无"通过"措辞；20.3% 警示在场）→ docs/review_2026-08/C7_validation_output.txt
  - wiki/entities/system/walk-forward.md 改写为"滚动窗口统计 rolling_stats.py（非 walk-forward）"；wiki/index.md、multi-factor-v2.md、docs/SOP.md §3.3-5 措辞同步
- **备注**: 未动 backtest.py / sell_signals.py / ic_monitor.py（其他 AI 并行修改中）；真 walk-forward（训练段选参→测试段重跑）仍为待建项，防过拟合判定统一由 ic_monitor.ICAlerts（signed NW-t 主判定线）负责。

## [2026-08-22] fix | walk_forward.py 正名（复盘 C7，方案 B）

- **操作者**: AI-C8
- **原因**: 复盘 C7 — 模块自称"Walk-Forward 滚动回测/防过拟合验证"，实际只对已算好的月收益序列做滑动窗口描述统计；strategy_fn 死参数从未调用；"OOS 胜率≥50% 且累计>0 → 通过"判定线无功效依据（项目实测 90 月功效仅 20.3%）。用户拍板方案 B（最简诚实：改名 + 去伪判定）。
- **影响**:
  - code/walk_forward.py：`walk_forward` → `rolling_window_stats`、`walk_forward_verdict` → `rolling_stats_summary`；删除 strategy_fn 死参数；删除"通过/观察"判定，只输出统计量（windows/oos_win_rate/oos_cum_return/train_test_consistency），docstring 如实写"滚动窗口描述统计（非 walk-forward）"，判定职责明确归 ic_monitor 主判定线；one_time_confirmation 保持不变；冒烟测试更新（含 `'verdict' not in summary` 断言）并通过
  - wiki/entities/system/walk-forward.md：标题改"滚动窗口统计"，内容按实现同步
  - docs/SOP.md：§2 结构树注释改为"滚动窗口描述统计（非 walk-forward；真 WF 验证待建）"
- **备注**: 并行 AI-C7 采用文件改名方案（walk_forward.py → rolling_stats.py，含证据强度分级与功效警示），为最终形态；真实 walk-forward 验证（训练段选参→测试段跑一次）项目内尚未实现，属遗留待办。

## [2026-08-22] decision | regime_based_weights 设计审批（复盘 C8，SOP §3.0）

- **操作者**: AI-C8
- **原因**: 设计文档标注"实施前须经 MImo 审批"但审批未做代码已写，违反 SOP §3.0 强制流程；按 SOP §3.0 补审批。
- **影响**:
  - 审查报告存档 docs/factor_docs/regime_weights_review_20260822.md：**有条件通过**（用于研究验证）
  - 审查重点结论：① 36m ICIR 噪声大但用途是相对强弱排序（±50% 上限封顶伤害），增量价值须实测（§5 验证为前提）；② 相关因子同步加成风险真实存在——不加相关性惩罚（保持方案 A 简单可解释），但调权只作用于已过 v3 检验+共线性闸门的因子，验证须检查同簇因子同步顶限；③ floor/max_dev/ic_window 参数敏感性 ±20% 必做（已全部暴露为函数参数）；④ 与先检验后集成纪律：WEIGHTS 层操作，未检验因子不得参与调权
  - 红线：调权增益（净成本）不稳健或 2x 成本下消失 → 方案 A 终止
- **备注**: 设计审批 ≠ 统计检验（SOP §3.0.1）；真实 IC 数据到位后须执行 §5 验证并回填本 decision。

## [2026-08-22] fix | regime_weights.py 实现 regime_weight_history（复盘 C8）

- **操作者**: AI-C8
- **原因**: 复盘 C8 — regime_weight_history 函数体无条件 raise NotImplementedError（含空转死循环代码段），设计文档 §5 核心验证要求（历史 PIT 调权）在代码层面被掐断；审批通过后按设计文档方案 A 实现。
- **影响**:
  - code/regime_weights.py：实现 `regime_weight_history(base_weights, factors_ic, quarterly_dates, ic_window=36, floor=0.1, max_dev=0.5)`——每调权日取 index<=qd 的最近 ic_window 个月 IC 算 ICIR → 交 regime_weights() 调权 → 输出权重历史 DataFrame；严格 PIT（未来数据不影响历史权重）；删除 NotImplementedError 与死代码段；模块头部标注审批报告路径与"研究验证工具"定位；regime_weights() 单点函数保持不动
  - 新增 code/validate_c8_regime.py：4/4 验收通过（抽查 2 调权日与逐期手算一致 / 与单期函数窗口化等价 / 未来数据污染不影响历史权重 / <12m 短样本保持基准权重），输出 docs/review_2026-08/C8_validation_output.txt
  - wiki/entities/system/regime-weights.md：状态改"设计已审（有条件通过）"，标注硬性实施前提与红线
- **备注**: 禁止在因子通过 v3 检验 + 调权增益验证前将输出用于实盘权重（SOP §3.0.2）。


## [2026-08-22] review-prep | C8a 与并行 AI-C8 完成情况核对（审批已完成，C8a 标注已更正）
- **操作者**: AI-C8a
- **原因**: C8a 准备审批材料期间发现并行任务 AI-C8 已先完成 C8 全流程（审批报告+实现+验证）；C8a 基于旧前提写入的冻结标注与状态行已过时，予以更正避免文件内自相矛盾
- **影响**:
  - code/regime_weights.py：C8a 冻结标注改为状态标注（指向正式审批报告 regime_weights_review_20260822.md，有条件通过/研究验证用途），未改任何逻辑
  - docs/review_2026-08/C8_regime_weights半成品.md：状态行由"待 C8b 审批"更新为"审批已完成（有条件通过）"，未写已验收
  - docs/factor_docs/regime_based_weights_review_request.md：标注被正式审批报告取代，保留存档；20.3% 功效出处按 AI-C8 报告口径更正（90 月回测对 3% 超额 TE10% 检出功效）
- **备注**: C8a 送审材料与 AI-C8 审批报告内容一致（4 项重点问题结论吻合）；最终以 AI-C8 报告为审批结论存档。

## [2026-08-22] build | S1 因子零检验：基础设施就绪 + 价格类因子试点（MOM_60D / VOL_RATIO）

- **操作者**: AI (subagent, Hermes)
- **原因**: S1 要求 10 因子完整 v3 检验，但数据层（S2）未就绪——先交付检验基础设施 + 真实数据试点，防止方法论零执行。
- **影响**:
  - 新增 code/factor_test_suite.py：v3 全文流水线（IC 关 signed NW-t≥max(3.0,Bonf(N'))+ICIR>0.5+|mean IC|≥0.02；分层关 PT MR 时间层 stationary bootstrap 块长3 R=9999 null recentering + 三重稳健性=市值加权/微盘剔除<30亿/规模中性 3×5 dependent sort 分格计成本；经济闸门净多空年化≥8% 且 2x 成本为正、夏普≥0.8；样本 2017-01 起+最近 24m 样本外一次确认；registry 追加式回填行生成）。合成数据自检通过：有效→保留 / 噪声→淘汰 / 反向→淘汰（REVERSE signed_t=-18.1 被防反向闸拦截）
  - 新增 code/pilot_mom60d.py + docs/factor_docs/test_MOM_60D_20260822.md、test_VOL_RATIO_20260822.md：新浪（akshare stock_zh_a_daily）hfq+raw 真实日线，120 只分层抽样，2023-02~2026-07（42 月）；市值=raw 收盘×流通股本代理；结论一律"初步"（<60 月，v3 §1），**未写入 registry、未入主策略**
  - 新增 docs/factor_docs/FACTOR_TEST_RUNBOOK.md：数据就绪后完整执行说明（数据清单/因子口径/命令/耗时/N' 口径核对）
  - docs/review_2026-08/S1_因子零检验.md：标题下如实标注"基础设施就绪+部分检验（试点）"，验收标准保持 [ ] 未勾选
- **备注**: 前置核对发现 VOL_RATIO 已弃用于主策略（multi_factor_value.py L59）但 registry 未同步——正式批次前需裁决；N'=10（≤37）→ 显著性线恒 3.0，bonf_threshold 实现与 ic_monitor 一致；数据层（S2）完成后按 RUNBOOK §4 批量执行即可。
## [2026-08-22] ingest | W1 Wiki摄入原始资料（复盘 W1）

- **操作者**: AI（Wiki修复子任务）
- **原因**: 复盘 W1 — Wiki 三层工作流 raw 摄入层为空，原始资料（审查报告/实测结论）从未摄入；concepts/regime 目录为空
- **影响**:
  - 创建 wiki/raw/papers/backtest-engineering-spec-v2-review.md（回测工程规范 v1/v2 两轮审查报告核心结论，sha256 见 frontmatter）
  - 创建 wiki/raw/papers/factor-testing-methodology-review.md（因子检验方法论 v1/v2 两轮审查报告核心结论）
  - 创建 wiki/raw/articles/data-source-testing-2026-08.md（数据源实测：东财限流模式 / qfq 负价实弹 / 腾讯 hfq 缺陷 / 新浪 raw 可用）
  - 创建 wiki/concepts/regime/ 3 页：2017-style-shift、2021-bubble-burst、2024-microcap-crisis（sources 标"项目研究记录+公开市场事实"）
  - 更新 wiki/index.md（28 → 34 页，新增 Regime 条目 + Raw 摄入层条目）
- **备注**: 摄入文件带 frontmatter（source_url/ingested/sha256/tags），sha256 为源文档正文哈希，Re-ingest 时比对防 drift；三个 regime 页与回测样本分层/观察线结构断点直接挂钩

## [2026-08-22] update | W2 Wiki错误声明修正（复盘 W2）

- **操作者**: AI（Wiki修复子任务）
- **原因**: 复盘 W2 — Wiki 页面声明与代码事实不符（hfq 收益层未实现时标"已实现"、simple_backtest 未删除时标"已替代"、行数失实、momentum 矛盾"有记录无行动"）；对应代码任务 C2/C3/C4 已定案，按定案同步修正
- **影响**:
  - wiki/entities/system/backtest-engine.md：删除"~800 行"表述；双口径铁律标注"已实现：2026-08-22 C3 方案 A 修复落地，金样本 Case 8 除息对账验证，29/29 PASS"；概述保留"真实数据回测：未执行（依赖 data_fetcher，见复盘 S2）"与"仅验证算术正确性，不构成策略验证"限定
  - wiki/entities/system/multi-factor-v2.md：backtest.py 表述改为"真实成本回测引擎（金样本验证），旧 simple_backtest() 已删除（复盘 C2，2026-08-22）"
  - wiki/concepts/factors/momentum-60d.md：confidence medium→low + contested: true + 新增"待决事项"区块（指向复盘 M5 FM 增量检验裁决，含裁决规则与前置依赖）
  - 巡检其余 9 个因子页：ep/bp/roe-ttm/turnover/vol-ratio 的"已知问题"含未验证矛盾/风险 → 加 contested: true + "待决事项"区块（指向 S1 因子零检验 / M2 / M5）
- **备注**: 验收口径：实体页所有"已实现"均可对应真实代码逻辑；"25/25"成就式表述已清除；M5 裁决后回填 momentum/ep/bp 页并移除 contested

## [2026-08-22] update | W3 文档三轨漂移同步（复盘 W3）

- **操作者**: AI（Wiki修复子任务）
- **原因**: 复盘 W3 — SOP / factor_docs / Wiki 三轨各自为政，参数与结论重复定义导致漂移（SOP §3.3 基准条款与 v2 规范冲突、Wiki 两页声明与代码不符即其后果）
- **影响**:
  - docs/SOP.md §2 新增 §2.1"文档分工与同步机制"：SOP = 流程与规则唯一事实源（参数默认值只在此定义）；factor_docs = 工作文档（设计稿/审查报告/检验报告）；Wiki = 知识提炼层（只引用 SOP/规范条款编号与检验报告编号，不复制参数值；必须复制时标注"同步自 X，更新于 Y"）
  - wiki/SCHEMA.md 更新策略新增第 5 条：事实冲突时以 SOP/定稿规范为准，Wiki 页标注来源版本号
  - wiki/log.md 对 2026-08-21"项目路径迁移 C盘→G盘"条目加勘误注记（原路径改写笔误 G→G 自指，正确应为 C 盘路径 → G 盘路径全量替换；原文保留以示审计）
- **备注**: 三轨同步为持续机制：此后任何参数/费率/阈值变更须按 SOP §2.1 流程（改 SOP → 记两处日志 → 涉及页面按"同步自 X，更新于 Y"刷新）

## [2026-08-22] build | 批量修复复盘 22 项问题（AI 批处理）

- **操作者**: AI (Hermes Agent, DeepSeek 并行子代理 ×9)
- **原因**: 项目复盘 2026-08-22 分项问题任务包（docs/review_2026-08/）22 项分配 AI 解决
- **影响**:
  - 代码修复 12 项：C1(入口崩溃)/C2(simple_backtest删除)/C3(hfq收益层)/C4(引擎7项缺口)/C5(sell_signals)/C6(ic_monitor主判定线)/C7(rolling_stats改名)/C8(regime_weights实现+审批)/C9(因子口径6项)/C10(数据降级链)/S2(data_fetcher+e2e_pipeline)/S3(run.bat -E)
  - 文档/Wiki 8 项：M1(叙事冻结)/M3(执行顺序条款)/M4(金样本表述+阶段门)/M6(口径审计表)/W1(raw摄入)/W2(错误声明修正)/W3(三轨同步机制)/S3(SOP结构树)
  - 金样本回归：103 PASS / 0 FAIL（原25+新增78，全合成数据手算对账）
  - 专项验证：C5 19/19、C6 22/22、C8 4/4、NW-t与statsmodels误差2.8e-14
- **搁置项**: S1/M5/M2 依赖真实数据（检验管线已建成 code/factor_tests/，数据拉取按用户指示暂停）；S2 真实数据端到端验证搁置
- **备注**: 真实数据（东财/腾讯/新浪行情）按用户指示 2026-08-22 暂时搁置；数据源实测结论：东财push2被封、腾讯WAF 501、新浪quotes可用但datalen上限800

## [2026-08-22] update | 文件整理: 2026年A股价值投资策略研报摘录.txt
- 操作者: AI (文件整理代理)
- 原因: 按规范归位
- 影响: 2026年A股价值投资策略研报摘录.txt → wiki\raw\articles\2026年A股价值投资策略研报摘录.txt
- 备注: 依据 FILE-MANAGEMENT-STANDARD.md 自动执行

## [2026-08-22] update | 文件整理: backtest_result_20260822.csv
- 操作者: AI (文件整理代理)
- 原因: 按规范归位
- 影响: backtest_result_20260822.csv → output\backtest_result_20260822.csv
- 备注: 依据 FILE-MANAGEMENT-STANDARD.md 自动执行

## [2026-08-22] delete | 清理: 0
- 操作者: AI (文件整理代理)
- 原因: 规则判定：0 为临时/0字节文件
- 影响: 0
- 备注: 依据 FILE-MANAGEMENT-STANDARD.md 自动执行

## [2026-08-22] delete | 清理: wikilink.md
- 操作者: AI (文件整理代理)
- 原因: 规则判定：wikilink.md 为临时/0字节文件
- 影响: wikilink.md
- 备注: 依据 FILE-MANAGEMENT-STANDARD.md 自动执行
## [2026-08-22] update | 文件整理: 因子检验报告.md
- 操作者: AI (文件整理代理)
- 原因: 按规范归位
- 影响: 因子检验报告.md → docs\research\因子检验报告.md
- 备注: 依据 FILE-MANAGEMENT-STANDARD.md 自动执行
## [2026-08-22] update | 文件整理: 我的笔记.md
- 操作者: AI (文件整理代理)
- 原因: 按规范归位
- 影响: 我的笔记.md → docs\research\我的笔记.md
- 备注: 依据 FILE-MANAGEMENT-STANDARD.md 自动执行
## [2026-08-22] update | 文件整理: 守护测试.txt
- 操作者: AI (文件整理代理)
- 原因: 按规范归位
- 影响: 守护测试.txt → wiki\raw\articles\守护测试.txt
- 备注: 依据 FILE-MANAGEMENT-STANDARD.md 自动执行

## [2026-08-22] update | 文件整理: 自动整理测试.txt
- 操作者: AI (文件整理代理)
- 原因: 按规范归位
- 影响: 自动整理测试.txt → wiki\raw\articles\自动整理测试.txt
- 备注: 依据 FILE-MANAGEMENT-STANDARD.md 自动执行
## [2026-08-22] fix | S2 端到端管线落地 + C9③④口径实测 + M6 收尾
- **操作者**: AI (Hermes Agent)
- **原因**: 复盘任务 S2/C9/M6 收尾
- **影响**:
  - 新建 code/e2e_pipeline.py（数据→因子→信号→引擎→报告五段编排，东财→新浪→腾讯三级降级+退市股纳入；CSI300 试点真实数据首跑：excess_annual_return=16.5%、IR=0.50；退市股 600401/002450 纳入验证 2/2）
  - code/factor_test_suite.py（v3 全流水线：IC关/分层关 stationary bootstrap/经济闸门；合成自检通过）
  - C9③④口径实测：yjbb 销售毛利率=报告期累计口径（40/40）；MOM_60D qfq/hfq 区间收益恒等、raw 差=分红；东财 f24 待解封复核；新浪降级源下 60日涨跌幅全 NaN→因子中性 0 分（安全降级）
  - data_caliber_audit.md 回填（M6）；SOP §3.2 新增第 0 步字段口径登记；v2.1 铁律适用范围补选股层
  - SOP §2 结构树更新（data_fetcher/e2e_pipeline/factor_test_suite 已实现）
- **备注**: 全 A 历史行情未拉全（CSI300 试点子集），全量执行见 e2e_pipeline.py 说明；GPM 已建议改 lrb TTM 口径（multi_factor_value.py 未动，待用户拍板）


## [2026-08-22] create | 文件整理代理
- **操作者**: AI (Hermes Agent)
- **原因**: 用户要求本地AI按 FILE-MANAGEMENT-STANDARD.md 规范自动整理文件，无需人工指令。
- **影响**:
  - 创建 code/file_organizer.py（规则引擎+本地AI分类）
  - 创建 code/file_organizer_watch.py（守护进程，5秒检测）
  - 配置 cron 定时任务（30分钟兜底）
  - 创建 _inbox/（用户文件入口）与 _hermes_out/（Hermes产出入口）
  - 更新 docs/SOP.md（新增§9）
  - 创建 entities/system/file-organizer.md
- **备注**: 只整理 _inbox/ 和 _hermes_out/ 两个来源，不做全库扫描。

## [2026-08-22] create | 组合层检验方法论 v1 草案（M2 交付）

- **操作者**: AI (Hermes 子代理)
- **原因**: 复盘任务 M2（检验与策略脱节：单因子过检 ≠ 加权组合有效）要求先产出组合层检验方法论文档，待 MImo 审批。
- **影响**:
  - 创建 docs/factor_docs/composite_testing_methodology_v1.md（v1 草案）：组合层必要性、五步检验（合成 SCORE 横截面检验 + 加权单因子 IC 基准 / 组合引擎回测按 v2.1 全文 / 权重证据编号制度 W-<因子>-<类型>-<日期>-<序号> + weight-change 日志 / 因子交互检查按 v3 共线性闸门 / 结论三档）、与 v3 判定线一致性要求、数据依赖与前置条件（S1 完成硬闸门）、报告模板、附录 A 审查请求区（待审问题 A-1~A-6）
  - 更新 docs/review_2026-08/M2_检验与策略脱节.md：标题下加状态行（方法论文档已产出/审批待执行）
  - 更新 comparisons/factor-direction-map.md：权重表新增"依据（待 M2 审批回填）"列（11 行×7 列），含三种证据标签说明（检验报告编号/设计审批引用/主观先验待验）、weight-change 日志衔接、变更记录追加一行；备注标注 TURNOVER/VOL_RATIO 行与代码合并口径的待同步差异
- **备注**: 文档为 v1 草案未生效；MImo 审批通过前不得执行组合层检验；未改任何代码。待 M2 审批后回填各权重"依据"具体值。

## [2026-08-22] update | 文件整理: 12144079.pdf
- 操作者: AI (文件整理代理)
- 原因: 按规范归位
- 影响: 12144079.pdf → wiki\raw\papers\12144079.pdf
- 备注: 依据 FILE-MANAGEMENT-STANDARD.md 自动执行

## [2026-08-22] update | 文件整理: 自启测试.txt
- 操作者: AI (文件整理代理)
- 原因: 按规范归位
- 影响: 自启测试.txt → wiki\raw\articles\自启测试.txt
- 备注: 依据 FILE-MANAGEMENT-STANDARD.md 自动执行

---

## [2026-08-22] ingest | W1 第二批摄入：质量因子 v2 + regime 调权审查（raw/papers×2）+ GPM/MOM 口径实测（raw/articles×2）

- **操作者**: AI (Hermes Agent)
- **原因**: 复盘 W1「Wiki 空知识库」整改第二批。首批（raw/papers×2、raw/articles×1、concepts/regime×3）已由批处理摄入；本批补齐 4 份 MImo 审查报告清单中的剩余 2 份（quality_factors_v2、regime_weights_review_20260822），并摄入两份数据口径实测（GPM 累计口径、MOM_60D 复权口径 + v3 检验结论）。
- **影响**:
  - 创建 raw/papers/quality-factors-v2-review.md（sha256 9e851723…）
  - 创建 raw/papers/regime-weights-review-20260822.md（sha256 9d5e9fff…）
  - 创建 raw/articles/gpm-caliber-verify-2026-08.md（sha256 e8ceaa29…）
  - 创建 raw/articles/mom60-caliber-and-test-2026-08.md（sha256 a166b844…）
- **备注**: 每页 frontmatter 含 source_url/ingested/sha256（源文件全文哈希，Re-ingest 漂移检测）/tags；正文为要点摘录+原文路径引用，不复制原文（raw 不可修改原则，原文仍在 docs/factor_docs/）。

---

## [2026-08-22] create | 市场状态识别概念页 + queries 实测记录归档 2 条

- **操作者**: AI (Hermes Agent)
- **原因**: W1 整改收尾：concepts/regime/ 已有 3 个结构断点页（批处理建），本批补「市场状态识别」综合页；queries/ 首批归档 2 条实测记录（S1 试点检验、金样本 103 PASS）。
- **影响**:
  - 创建 concepts/regime/market-state-identification.md（confidence low：断点为定性事实、无量化验证；sources 指向 4 个 raw/ 页）
  - 创建 queries/s1-pilot-factor-tests-20260822.md（MOM_60D signed NW-t −3.63 反向显著淘汰 / VOL_RATIO 淘汰；CSI300 101~120 只/2023-02 起 43 月，样本<60月结论初步）
  - 创建 queries/golden-samples-103-pass-20260822.md（引擎金样本 103 PASS / 0 FAIL，合成数据仅验证算术正确性，非策略验证——复盘 M4）
  - 更新 index.md（Total pages 34 → 41）
- **备注**: 10 因子完整检验待 S2 数据层；MOM_60D 回填行未写入 registry（待 MImo 审批后追加）。

## [2026-08-22] update | 文件整理: A股质量因子研究笔记.md
- 操作者: AI (文件整理代理)
- 原因: 按规范归位
- 影响: A股质量因子研究笔记.md → docs\research\A股质量因子研究笔记.md
- 备注: 依据 FILE-MANAGEMENT-STANDARD.md 自动执行


## [2026-08-22] update | M5 先验当结论：DIRECTION 符号本地验证 + MOM×价值 FM 裁决（试点执行）
- **操作者**: AI (Hermes Agent 子代理)
- **原因**: 复盘任务包 M5 验收——S1 试点数据（pilot_mom60d 101 只 CSI300 子集，2023-02~2026-08）可用后执行符号验证与 FM 增量裁决
- **影响**:
  - 新增 code/_fm_increment.py（FM 多元回归 + yjbb EP/BP 试点构建 + 合成自检 PASS + 权重影响测算）
  - 新增 docs/factor_docs/test_value_vs_momentum_20260822.md（裁决报告：MOM 单变量反向显著 NW-t=-3.63 → 防改口反转重登记 MOM_60D_R1；FM 控制规模/行业后 MOM t=-1.08 无增量；EP t=+1.94/BP t=+0.61 未达 2.0 → 观察；建议权重归零/反转）
  - factor_registry.md 追加 #12~#17（MOM_60D_R1 重登记、MOM/VOL 回填淘汰、EP/BP 观察、M5 裁决行），N'=1
  - wiki momentum-60d/ep-factor/bp-factor 页试点裁决回填（contested 保留至正式复核）；factor-direction-map 记待拍板权重调整
- **备注**: 全部结论初步（样本<60 月、幸存者偏差、东财行业非申万非 PIT）；multi_factor_value.py 未改动，权重方案待用户拍板；全 A 2017+ 数据就绪后须复核

## [2026-08-22] ingest | 银行业投资分析.docx 知识化
- **操作者**: AI (本地AI知识化)
- **原因**: 用户提供文件，转化为 Obsidian 笔记并串联 Wiki
- **影响**: 原始文件保留 G:\quant-investing\wiki\raw\articles\银行业投资分析.docx；知识页 G:\quant-investing\wiki\concepts\银行业投资分析.md；index.md 更新
- **备注**: 原文件未删除，知识页通过 [[wikilinks]] 与现有页面串联

## [2026-08-22] update | 文件整理: 银行业投资分析.docx
- 操作者: AI (文件整理代理)
- 原因: 按规范归位
- 影响: 银行业投资分析.docx → wiki\raw\articles\银行业投资分析.docx
- 备注: 依据 FILE-MANAGEMENT-STANDARD.md 自动执行
## [2026-08-22] ingest | 因子月度检验表.xlsx 知识化
- **操作者**: AI (本地AI知识化)
- **原因**: 用户提供文件，转化为 Obsidian 笔记并串联 Wiki
- **影响**: 原始文件保留 G:\quant-investing\wiki\raw\articles\因子月度检验表.xlsx；知识页 G:\quant-investing\wiki\concepts\因子月度检验报告.md；index.md 更新
- **备注**: 原文件未删除，知识页通过 [[wikilinks]] 与现有页面串联

## [2026-08-22] ingest | 季度策略展望.pptx 知识化
- **操作者**: AI (本地AI知识化)
- **原因**: 用户提供文件，转化为 Obsidian 笔记并串联 Wiki
- **影响**: 原始文件保留 G:\quant-investing\wiki\raw\articles\季度策略展望.pptx；知识页 G:\quant-investing\wiki\concepts\2026年三季度策略展望.md；index.md 更新
- **备注**: 原文件未删除，知识页通过 [[wikilinks]] 与现有页面串联

## [2026-08-22] update | 文件整理: 因子月度检验表.xlsx
- 操作者: AI (文件整理代理)
- 原因: 按规范归位
- 影响: 因子月度检验表.xlsx → wiki\raw\articles\因子月度检验表.xlsx
- 备注: 依据 FILE-MANAGEMENT-STANDARD.md 自动执行

## [2026-08-22] update | 文件整理: 季度策略展望.pptx
- 操作者: AI (文件整理代理)
- 原因: 按规范归位
- 影响: 季度策略展望.pptx → wiki\raw\articles\季度策略展望.pptx
- 备注: 依据 FILE-MANAGEMENT-STANDARD.md 自动执行
## [2026-08-22] ingest | 银行业投资分析.docx 知识化
- **操作者**: AI (本地AI知识化)
- **原因**: 用户提供文件，转化为 Obsidian 笔记并串联 Wiki
- **影响**: 原始文件保留 G:\quant-investing\wiki\raw\articles\银行业投资分析.docx；知识页 G:\quant-investing\wiki\concepts\银行业投资分析.md；index.md 更新
- **备注**: 原文件未删除，知识页通过 [[wikilinks]] 与现有页面串联


## [2026-08-22] update | 文件知识化支持办公格式
- **操作者**: AI (Hermes Agent)
- **原因**: 用户要求加入平常办公格式文件的转化。
- **影响**:
  - file_to_wiki.py 新增 extract_text()：支持 docx/xlsx/pptx/pdf/txt 文本提取
  - 新增 postprocess_page()：修正 AI 幻觉日期、sources 路径、剔除无效 [[wikilinks]]
  - file_organizer.py 路由办公格式到 wiki/raw/articles/
  - 安装 python-pptx + pymupdf 依赖
  - 实测：docx → 银行业投资分析.md / xlsx → 因子月度检验报告.md / pptx → 2026年三季度策略展望.md 全部串联成功
- **备注**: 原文件保留在 wiki/raw/，知识页通过有效 wikilinks 与现有页面串联。
## [2026-08-22] update | W3 文档三轨漂移收尾：confidence 重标 + 参数页同步标注

- 操作者: AI-W3（复盘修复子代理）
- 原因: 复盘 W3 剩余项——因子页 confidence 与检验证据不一致、VOL 页未挂检验报告、参数页裸复制无同步标注
- 影响:
  - 6 因子页 confidence medium→low + 待决事项加「先验待验」标签：roe-ttm / turnover-factor / gpm-factor / cfo-ni-ttm / lev-factor / log-mcap（均无 v3 检验证据，S1 未完成）
  - vol-ratio.md：回填 test_VOL_RATIO_20260822.md 淘汰结论（初步，<60月）+ 挂报告编号 + 变更历史
  - momentum-60d.md：补挂 test_MOM_60D_20260822.md（v3 全流程判定淘汰，与试点一致）
  - backtest-cost-model.md：费率表加「同步自 SOP v1.4 §7 附录A，更新于 2026-08-21」标注
  - factor-direction-map.md：confidence high→medium；权重表加「同步自 code WEIGHTS+DIRECTION / factor_registry.md」标注
  - wiki/log.md 2026-08-21 迁移条目勘误补充（「已不再是正式目录」指 C 盘旧目录）
- 备注: EP/BP 保留 medium（已挂 test_value_vs_momentum_20260822 试点报告 + registry #15/#16）；MOM/VOL 标 low 与「淘汰」结论一致；S1 完整检验完成后按结论再调

## [2026-08-22] decision | M1 叙事统一完成：设计审查 ≠ 统计检验全项目落地

- **操作者**: AI（M1 交付）
- **原因**: 复盘 M1（docs/review_2026-08/M1_审查偷换为有效.md）——'MImo 审查通过'被误读为'因子有效'；本轮为剩余叙事统一（代码 banner/registry 状态列/SOP §3.0 已于前轮修正）
- **影响**:
  - mimo-review.md：补'审查 ≠ 检验'节（设计审查='设计已审（MImo v2，2026-08-20）'；统计检验='有效性未验（v3 检验未执行）'或'已检验：test_XXX_20260822.md 结论 XX'）；'已通过审查的因子'改'已通过设计审查的因子'并加注，日期改 2026-08-20
  - multi-factor-v2.md：概述加注'因子有效性状态：多数待检验（见 registry，补检为复盘 S1）；MOM_60D/VOL_RATIO 试点已淘汰（M5）'
  - factor-direction-map.md：依据列回填——MOM_60D→test_MOM_60D_20260822.md 反向显著/待拍板、VOL_RATIO→test_VOL_RATIO_20260822.md 淘汰、EP/BP→M5 试点观察（test_value_vs_momentum_20260822.md，初步）；未检验因子标'先验待验（有效性未验，见 S1）'
  - quality_factors_v2.md：状态行加注'设计审查通过（MImo v2，2026-08-20），非统计有效性结论'
  - factor_registry.md：#7（MOM_60D 方向+）备注加注指向 #12/#13（该方向检验作废，反转以 #12 MOM_60D_R1 为准）；审计日志追加
  - grep '审批通过|已批准|已通过' 复查：残留均为正确表述（SOP §3.0'已通过设计审批的因子'、regime_based_weights_review_request.md'已通过设计审批的 v2 因子'、明确标注'审查'的历史记录等）
- **备注**: 统计有效性补检仍为复盘 S1 任务（10 个在册因子零检验，🔴 最致命）；MOM_60D 权重归零/反转待用户拍板（M5）

## [2026-08-22] update | W2/M4 验收补全：CSI300 状态回填 + 因子页巡检收尾（复盘 W2/M4 第二批）

- **操作者**: AI（Wiki修复子任务，第二批）
- **原因**: 前序批处理完成 backtest-engine/multi-factor-v2/momentum 主体与 5 因子页 contested；本批验收发现并补全：① backtest-engine 当前状态行过时（"真实数据回测：未执行"与 CSI300 试点已跑通矛盾）；② 金样本 PASS 数字统一为实跑 103/103（本批实跑 test_golden_samples.py 确认 103 PASS / 0 FAIL）；③ 9 因子页巡检收尾；④ ep 公式与 vol-ratio/turnover 权重与代码失实
- **影响**:
  - wiki/entities/system/backtest-engine.md：概述 PASS 29/29→103/103 带 M4 限定语（合成数据手算对账——仅验证算术正确性，未接入全量真实数据，不构成策略验证）；当前状态行改为"真实数据回测：CSI300 试点已跑通（2026-08-22，e2e_pipeline --universe csi300，output/backtest_result_20260822.csv），全 A 未拉全"；双口径铁律标题 PASS 数同步 103/103（已实现声明与代码一致：nav_hfq/daily_returns/_compose_daily_return 实存）
  - wiki/entities/system/multi-factor-v2.md：架构段去除重复/未闭合代码块（保留含 e2e_pipeline+hfq 的最新图）；"旧 simple_backtest() 已删除"表述核对通过（C2 已删）
  - wiki/concepts/factors/gpm-factor.md、cfo-ni-ttm.md、lev-factor.md、log-mcap.md：frontmatter 补 contested: true（confidence 已由并行批次降 low），待决事项补口径审计指向；gpm 页记录 W2 类新发现：M6 审计表"已改毛利TTM/营收TTM"勾选与代码不符（multi_factor_value.py L247 仍取 yjbb 销售毛利率，data_fetcher 无 lrb 实现）
  - wiki/concepts/factors/ep-factor.md：计算公式改 TTM 口径（EP = EPS_TTM/最新价；市盈率-动态 降为参考列 EP_DYN）
  - wiki/concepts/factors/vol-ratio.md：当前配置标注已弃用（权重 0.05 并入 TURNOVER）、registry #14 淘汰结论同步
  - wiki/concepts/factors/turnover-factor.md：权重 0.10→0.15（吸收 VOL_RATIO）+ 口径指向
  - wiki/concepts/factors/momentum-60d.md：待决事项补口径风险（f24 未终判/raw 低估高股息动量/新浪降级 NaN）
  - docs/review_2026-08/W2_Wiki错误声明.md、M4_金样本虚假安全感.md：补第二批验收行
- **备注**: 巡检结论——9 因子页全部 contested: true + confidence low（ep/bp 有 M5 试点证据维持 medium）；与并行 M5 批次共存（其已给 9 页加先验待验/S1 指向，本批补 frontmatter contested 与口径审计指向，未覆盖其内容）；grep '25/25' wiki/ 仅剩复盘页与历史 log（上下文明确，无裸成就表述）；grep '已实现' wiki/entities/system/ 仅 backtest-engine.md 1 处且与代码一致；GPM"已改TTM"声明不符为遗留 W2 类问题，已记入 gpm 页待决事项

## [2026-08-22] review | M2 组合层检验方法论独立审查：有条件通过（P0×4）

- **操作者**: MImo（独立审查会话，SOP §3.0 流程）
- **原因**: docs/factor_docs/composite_testing_methodology_v1.md（M2 产出物，v1 草案）须经独立审批；附录 A 六问（A-1~A-6）待裁决
- **影响**:
  - 审查报告归档 docs/factor_docs/composite_testing_methodology_v1_review_20260822.md，结论 **有条件通过**
  - **P0×4（必须修订出 v1.1）**：P0-1 A-1① B 基准 signed IC 自我抵消（方向失效时合成 IC 与基准同步下降，vs-B 检测力为零，数学推导复核）→ 改 |IC| 口径（L38/L74）；P0-2 A-2① §3.2 #7 M4 替代口径与 §5.1 硬闸门自相矛盾（L102 vs L193）→ §5.1 优先；P0-3 A-4① 三档"≤2 项观察线告警"无清单/等权计数/不可操作（L155/L158）→ A/B 类分类加权显式清单；P0-4 A-5③ 交互处置"取 ICIR 较强者"缺组合贡献标准，可能保留组合内负贡献因子（L145）→ 保留 = ICIR 强者且训练段 ΔIC_f > 0
  - **P1×15**：vs-B 容差挂 SE(Δ)、ΔIC 解读/容差/训练段裁决、变体硬线降级 + Top20/50 敏感性、分层经济闸门触发条件、合成 IC 预登记方向 = +1、B 重算窗口、池口径（北交所）、容量检查 M13、变体拆分、归因口径、日志涉及因子列、"降级观察"映射部分通过、不通过③定义化、L26 失效权重加注、告警计数防歧义句
  - **P2×8**：交互损耗措辞、N' 扩展声明、单因子对照定位、模板补数据状态、清零顺序、三重稳健性统一、档位优先级、编号粒度维持
  - M2 任务书补审批状态行；被审文档未改动（只读审查）
- **备注**: 审查核对基准 = factor_testing_methodology_v3.md（定稿）/ backtest_engineering_spec_v2.1.md（定稿）/ SOP §3.0；无自创统计量、阈值整体对齐 v3 §11 与 v2.1 §4.4（§4.2 表逐项核对）；v1 草案保持"未生效"，待 v1.1 修订复审

## [2026-08-22] verify | C1/C2/C10 实跑验收（入口崩溃 / 未来函数回测 / 数据降级）

- **操作者**: AI（实跑验收子任务）
- **原因**: C1/C2/C10 三修复项代码改动已由 AI 批处理完成，需要实跑验证入口不再崩溃、无回测残留、降级链真实可用
- **影响**:
  - C1（run.py 入口）**通过**：`D:/pyh/python.exe -E run.py` 18s 完成、无 ValueError；`scored, selected = run_full_pipeline(top_n=30)` 与 return 二元组一致；import 回归通过
  - C2（simple_backtest）**通过**：grep simple_backtest/with_backtest/backtest_days 仅剩 multi_factor_value.py L389 注释；实跑输出仅选股表、无"回测结果"字样
  - C10（数据降级）**部分通过**：东财 ConnectionError×3 → 新浪降级真实触发（5548 只，[数据源] sina 声明一致）；PE/PB 合成抽查 600519/000001/601318 与手算偏差 0%；**但 pick_20260822.csv 无选股价值**——30 行全北交所 bj 前缀 + SCORE 全 NaN，根因：① 新浪代码带前缀（bj920000/sh600000）与财务 qdf 纯数字代码 merge 全失败（0/1291，剥前缀后 1291/1291）；② 北交所过滤 startswith(('4','8')) 对 bj 前缀失效；③ 旧 spot 缓存（合成修复前，PE/PB 全 NaN）被缓存命中 → 首次实跑入池 0 只空表
- **备注**: 遗留问题（本次未改代码，另行安排）：① `_normalize_spot` 新浪路径剥代码前缀；② 缓存命中校验 PE/PB 覆盖；③ 缺失字段（60日涨跌幅/量比）声明补全。已同步 docs/review_2026-08/C1/C2/C10 三页验收标记

## [2026-08-22] update | S3/M3 收尾：运行日志落地 + SOP §1.2 补 .bat -E + 模块头部状态标注巡检

- **操作者**: AI（S3/M3 收尾子代理）
- **原因**: 复盘 S3 剩余（SOP §3.4 要求 logs/run_{时间戳}.log，但 multi_factor_value.py/run.py 无日志代码）与 M3 剩余（code/ 各策略模块头部审批/检验依据标注巡检，SOP §3.0.2 第 3 条）
- **影响**:
  - code/run_logger.py 新建：单例运行日志工具，logs/run_{时间戳}.log（自动建目录，UTF-8），并挂 root handler 使 data_fetcher 的缓存/降级日志一并落盘
  - code/multi_factor_value.py：run_full_pipeline 关键节点加日志（启动时间/缓存命中/数据源 _source/入池股数/质量因子覆盖/因子覆盖率/选股输出路径/总耗时）+ try/except 异常堆栈记录；因子计算逻辑零改动
  - code/run.py：入口 try/except 记录异常堆栈并 exit(1)
  - docs/SOP.md：§1.2 补「.bat 也必须带 -E」条款；版本 v1.4→v1.5 + 演进表 v1.5 行
  - 模块头部状态标注（SOP §3.0.2）：backtest（v2.1 审批+金样本 103/103）、sell_signals（未审批/未检验（实验）+C5 验收）、ic_monitor（v3 方法论审批+C6 验收）、rolling_stats（C7 方案B+实验）、data_fetcher（S2/C10 验收）、e2e_pipeline（S2 部分验收）、factor_test_suite（v3 审批+S1 就绪）、test_golden_samples（v2.1 依据+103/103）、pilot_mom60d（S1 试点实验）；regime_weights/multi_factor_value 原有标注确认
  - docs/review_2026-08/S3_SOP与代码不同步.md、M3_先集成后检验.md：补本批验收行
- **备注**: 验证=全模块 import 冒烟通过 + 离线缓存干跑 run.py 实测生成 logs/run_*.log 且含全部要求字段；金样本在 import 冒烟中顺带复跑 103 PASS / 0 FAIL

## [2026-08-22] update | 复盘 22 项任务全部委派完成（7 批 AI）
- **操作者**: AI (Hermes Agent)
- **原因**: 用户要求 review_2026-08 目录每个问题分配一个 AI 解决
- **影响**:
  - 7 批 × 3 并行子代理覆盖全部 22 项：C1-C10 代码修复全落地（金样本 103/103、入口 18s 实跑通过、C10 新浪降级链+PE/PB 合成+前缀修复实测出票）、S1 检验设施+2 因子试点（MOM_60D 反向显著 signed_t=-3.63）、S2 e2e_pipeline 真实数据首跑、S3 日志+标注、M1 叙事统一（grep 27 处核对）、M2 组合检验方法论 v1（MImo 审批评审：有条件通过 P0×4 待 v1.1）、M3 强制条款、M4 金样本表述、M5 符号验证+FM 裁决（建议砍 MOM 待拍板）、M6 口径审计表、W1 raw 摄入 7 份+regime 4 页、W2 Wiki 纠错、W3 三轨分工
  - 关键实测结论：MOM_60D 在 CSI300 试点样本（101 只×43 月）反向显著→已按防改口重登记 MOM_60D_R1；GPM=报告期累计口径（40/40）；新浪降级下 60日涨跌幅全 NaN→安全中性化
- **备注**: 全 A 2017+ 数据未拉全（CSI300 试点），S1 完整 10 因子检验待数据就绪（RUNBOOK 已备）；GPM lrb TTM 改法、MOM 权重处置（归零/反转）、regime 调权启用三项待用户拍板；审计表 GPM 行已勘误（lrb 改法为建议未落地）

## [2026-08-22] create | 本地AI批量摄入本次修复产出（用户要求）
- **操作者**: AI (Hermes Agent) + 本地 AI (Qwen2.5-7B)
- **原因**: 用户要求所有文件和操作经本地 AI 处理进入 Wiki
- **影响**:
  - queries/mom60d-v3-test-20260822.md（MOM v3 检验：NW-t=-3.63 反向显著→淘汰）
  - queries/volratio-v3-test-20260822.md（VOL v3 检验：不显著→淘汰）
  - queries/value-vs-momentum-fm-20260822.md（FM 裁决：MOM 无独立增量）
  - raw/papers/composite-testing-methodology-review.md（M2 审查报告：有条件通过 P0×4）
  - comparisons/project-review-2026-08.md 追加"2026-08-22 问题解决状态"节（22 项）
  - index.md 41→45 页
- **备注**: 本地 AI 生成页面已清理嵌套代码块；frontmatter 由脚本兜底补齐

## [2026-08-25] update | 价值投资转型 v2.1 设计定稿：registry 登记 4 新因子 + SOP/Wiki 三轨文档同步（P3）

- **操作者**: AI（P3 文档同步子代理）
- **原因**: 价值投资转型设计 v2.1 终审通过定稿（docs/factor_docs/value_investing_transition_v2.1.md，P0-A/P1-A/P1-B/P1-C 必改项清零），P3 阶段执行 registry 前置登记与三轨（registry/SOP/Wiki）文档同步，为 P4 统计检验铺路
- **影响**:
  - docs/factor_docs/factor_registry.md：⓪ 步前置登记 4 新因子（PE_PCTL/PB_PCTL/DY/FCF_YIELD，#18-21，预期符号 −/−/+/+，样本期 2018-01+，MImo审批"已审(v2.1定稿)"）；N' 1→5，历史全量 17→21；审计日志 2026-08-25 条目；#13 备注同步（原方向已淘汰出打分体系、反转 #12 保持待检）
  - docs/SOP.md：v1.5→v1.6；新增 §3.4 价值投资决策流程（四层管线/4 新因子登记表/生产开关 fail-closed/卖出信号完整快照语义）；§2 结构树 +value_investing.py（计划）；原 §3.4/§3.5 顺延为 §3.5/§3.6
  - wiki/entities/system/multi-factor-v2.md：更新为价值投资决策系统 v3（设计定稿 2026-08-25）描述
  - wiki/concepts/factors/：新建 4 因子概念页（pe-pctl / pb-pctl / dy-factor / fcf-yield，状态"待检验"）；momentum-60d.md 状态更新（原方向已淘汰（#13，试点反向显著）；反转方向待检（#12））
  - wiki/index.md：+4 页（49→53）
- **备注**: 决策原因——4 新因子均为"设计已审 ≠ 统计检验"（M1 口径），P4 前权重一律实验性；生产开关 fail-closed 默认拒绝实验性权重、禁止实盘信号输出；卖出信号行=完整持仓快照语义（P1-B 必改项）已写入 SOP §3.4 与 registry 审计日志；data_caliber_audit.md 字段口径登记属 P1 阶段（设计 §6），本次未动

## [2026-08-25] build | 价值投资转型实施完成（P1/P2/P2.5/P3）

- **操作者**: AI (Hermes Agent, 子代理 ×3)
- **原因**: 用户指令"将项目全面转向为价值投资方向"（方法论重构）；设计稿经三轮独立审查定稿（v1→v2→v2.1，P0-A/P1-A/P1-B/P1-C清零）
- **影响**:
  - 设计定稿：docs/factor_docs/value_investing_transition_v2.1.md（四层管线：过滤→质量门槛→估值打分→组合构建；安全边际分0.30/0.30/0.15/0.15/0.05/0.05）
  - P1 数据层：data_fetcher.py 新增4接口（get_valuation_history/get_fcf/get_dividends/get_industry_map，实测通过）；yjbb公告日=首次披露日结论（PIT安全）
  - P2 主策略：value_investing.py 新建（900行）；multi_factor_value.py MOM_60D归零+8因子重归一化（和=1.000，旧系统保留对照）；run.py 生产开关fail-closed
  - P3 文档：registry 登记4新因子（#18-21，N'=5）；SOP v1.6 §3.4；Wiki 4新概念页
  - 顺带修复：get_delisted_stocks() akshare新版签名（367家退市股）
  - 验证：金样本103 PASS、P2验收55/55、全模块import 10/10
- **备注**: P4统计检验/P5真实回测待真实数据恢复；4新因子权重为"实验性"（生产开关拒绝实盘使用）


## [2026-08-25] update | confidence 全库重评为 0-100

- **操作者**: AI
- **原因**: 用户要求将 confidence 从 high/medium/low 三档细分为 0-100 数字评分，全库统一。
- **影响**:
  - SCHEMA.md：confidence 改 0-100 整数 + 新增 5 档映射表（90-100 极高 / 70-89 高 / 50-69 中 / 30-49 低 / 0-29 极低）
  - FILE-MANAGEMENT-STANDARD.md：§4.2 改 0-100，升 v1.4
  - 代码 3 处 emitter 输出改 0-100：local_ai.py（新增 _coerce_confidence）、wiki_ingest.py、file_to_wiki.py
  - 重评 46 个 Wiki 页 confidence：权威定稿/复盘（sop-v1.1 / backtest-engineering-spec / factor-testing-methodology / mimo-review / project-review-2026-08）→85；测试结果页保留 AI 重评；其余按原档位 high→80 / medium→60 / low→35
- **备注**: raw/papers/composite-testing-methodology-review.md 因 raw/ 不可改保留旧档位，待后续处理。因子页零检验（见 project-review-2026-08），故 low 因子统一 35、medium 因子统一 60。

## [2026-08-29] build | 初筛管线三模块完成（1 万元价值投资支持）

- **操作者**: AI (Hermes Agent, 子代理 ×3 独立审核)
- **原因**: 用户1万元实盘价值投资需求，初筛需市值/ST/估值分位三过滤
- **影响**:
  - code/screening/ 三模块：st_filter.py（ST/退市前缀匹配，两源一致性0冲突）、mcap_filter.py（腾讯qt市值，缓存）、valuation_percentile.py（PE/PB历史分位，2018起滚动窗口，手算对照0.0000pp）
  - code/run_screen.py 组装全链路：1587→1532(ST剔)→7(质量门槛)→6(市值)→0(分位<50%)
  - 结论：当前无候选同时满足PE/PB分位<50%（周期股PB分位偏高），空仓等待符合价值投资纪律
- **备注**: 各模块独立验证报告 docs/factor_docs/screen_{st,mcap,pctl}_report.md；演示级非投资建议

## [2026-09-10] create | 防过拟合方法论概念页

- **操作者**: AI (Claude)
- **原因**: 用户量化项目收尾，将「防过拟合方法」详细版沉淀进知识库；同时精简条款并入 G:\AI-通用准则.md 第 9 条，并同步 CLAUDE.md 与记忆索引。
- **影响**:
  - 创建 wiki/concepts/risk-management/overfitting-prevention.md（通用 ML 方法 + 量化专属方法，链接 walk-forward/factor-testing-methodology/backtest-engineering-spec/factor-decay）
  - 更新 wiki/index.md（Total pages 53 → 54）
- **备注**: 页面为方法论综合页，非新来源摄入（无 raw/ 来源）；通用 ML 方法为标准方法论，confidence 70。

## [2026-09-10] update | overfitting-prevention 页对抗性审查修复

- **操作者**: AI (Claude)
- **原因**: 按准则第 6 条对防过拟合页做独立对抗性审查，发现 1 项 P0 事实错误、2 项代码 bug、1 项 Schema 违规、若干 P2 细节；据实修复。
- **影响**:
  - wiki/concepts/risk-management/overfitting-prevention.md：§8 修正 PSR(2012)/DSR(2014) 区分与引文（原把 PSR 公式误标为 DSR）；§1/§6 代码 bug 修复（时序同步切 y、删不存在参数 early_stopping）；frontmatter 补 sources + confidence 70→75；§4 共线性阈值对齐 SOP 0.7；γ₄=普通峰度、i.i.d. 前提、N'=同期受检口径、「7 条=策略判定」等措辞修正
- **备注**: 审查确认 7/8 通用 ML 方法正确、项目引用与 SOP/spec 逐字一致、无断链；遗留：PSR/DSR 原始论文未摄入 raw/（页面已声明）。

## [2026-09-11] create | PSR/DSR 原始论文摄入 raw/papers

- **操作者**: AI (Claude)
- **原因**: 闭合防过拟合页遗留口子——PSR(2012)/DSR(2014) 原始论文此前未摄入 raw/，导致溯源链中断、confidence 止步 75。按 raw/papers/ 规范找回并摄入两篇原始论文。
- **影响**:
  - 下载两篇作者 preprint PDF 至 wiki/raw/papers/（sharpe-ratio-efficient-frontier-2012.pdf / deflated-sharpe-ratio-2014.pdf），sha256 校验通过
  - 新建两个 raw 摘要页（同名前缀 .md）：frontmatter 含 source_url/sha256/tags，正文为原文摘要 + 核心结论 + 与项目关联
- **备注**: 出处为作者 David H. Bailey 站（davidhbailey.com/dhbpapers/），SSRN 与 quantresearch.org 直连超时不可达；sha256 为全文 PDF 的 SHA-256。

## [2026-09-11] update | overfitting-prevention DSR 公式修正 + confidence 85

- **操作者**: AI (Claude)
- **原因**: 摄入论文时对照 DSR 原文 Eq.(2) 发现此前 DSR 公式有误——分母多加了 σ²_SR0·(n−1) 项；原文明确「DSR is a PSR where the rejection threshold is adjusted」，受检 SR 方差 σ² 折在 SR₀ 内、非分母附加项。据原文修正。
- **影响**:
  - wiki/concepts/risk-management/overfitting-prevention.md：§8 DSR 公式删分母 σ²_SR0·(n−1) 项、SR* 改为 SR₀ 并说明其由 N 与 σ² 决定；sources 补两篇 raw 论文；confidence 75→85；「论文未摄入」遗留项闭合
- **备注**: 该误差为上一轮对抗性审查遗漏项；本轮以原始 PDF 一手文本裁决（附录代码 SR₀ = μ+σ·maxZ 印证 σ 在 SR₀ 内）。

## [2026-09-11] audit | 独立对抗审计 PSR/DSR 页（无 P0，1 P1 + 3 P2 已修）

- **操作者**: AI (Claude) → 独立 agent（fresh 上下文）
- **原因**: 用户指出「独立审计的部分」未落地；按准则第 6 条起 fresh agent 对抗审查本次 DSR 公式修正 + 两个 raw 页。
- **影响**:
  - 结论：无 P0。PSR Eq.(8)/DSR Eq.(2)/峰度口径经与两 PDF 附录代码逐字符核对全部正确；两 sha256 逐字符匹配；schema/tags 合规；7 个 wikilink 目标齐全。confidence 85 站得住。
  - 修复 1 P1：sharpe-ratio 页「虚高夏普点估计」→「不改变点估计本身、放大方差抬高置信带」（论文 2.4 节原意）。
  - 修复 3 P2：DSR 摘要连字符 highperformance→high-performance；PSR 摘要补末句「Results can be validated using the Python code in the Appendix.」；「样本外必均值回归」→「很可能」（原文 likely）。
- **备注**: 卷期页码（JOR 15(2)3-44 / JPM 40(5)94-107）来自 PDF 之外，PDF 首页仅写「Forthcoming」，无法用原始 PDF 证实，保留为补充信息。

## [2026-09-13] create | 从 Hermes 会话归档沉淀本地库与初筛管线知识

- **操作者**: AI (MiMo)
- **原因**: 用户从 `G:\conversation-archive` 做「知识沉淀」；对照 vault 查重后，2026-08-29 本地股票数据库与初筛管线结论仅有 docs/code，无 Wiki 实体页。
- **影响**:
  - 创建 wiki/entities/system/quant-db.md（表结构、可支撑场景审计、补齐成本、6 处首灌坑）
  - 创建 wiki/entities/system/screening-pipeline.md（五道过滤、分位严格 AND 取舍、诚实限制、验证记录）
  - 更新 wiki/index.md（56→58 页）
- **备注**: 排除项——会话库含私人剧情/生活/非量化内容，按隐私与 Domain 范围不入 vault；设计稿 value_investing_transition_v2.1 仍以 docs/factor_docs 路径引用（未建 Wiki 页）。归档中大量 08-21~08-25 修复/审查结论已在既有 log 与页面中，不重复建页。

## [2026-09-16] organize | 文件整理代理例行扫描

- **操作者**: AI (MiMo) — cron 定时任务
- **原因**: 定时扫描 `_inbox/` 与 `_hermes_out/`，按 FILE-MANAGEMENT-STANDARD.md 归类散落文件。
- **影响**: 无。两个目录均为空，无需移动任何文件。
- **备注**: 脚本正常退出 (exit 0)。

## [2026-09-18] decision | 禁用 QuantDBUpdate 计划任务

- **操作者**: AI (Claude)
- **原因**: 系统后台自启动清理时，发现 `QuantDBUpdate` 计划任务（每日 18:30 运行 `D:\pyh\python.exe -E G:\quant-investing\code\update_db.py --tables spot,fin,mcap`，2026-08-29 创建）被列入待清理项，按用户要求禁用。
- **影响**:
  - 禁用计划任务 `QuantDBUpdate`（TaskPath `\`），备份 XML 至 `G:\sysclean-backup\2026-09-18\QuantDBUpdate.xml`
  - 数据库 spot/fin/mcap 表不再每日自动更新，需手动运行 `python code\update_db.py --tables spot,fin,mcap` 或重新启用任务
- **备注**: 恢复方法 `Enable-ScheduledTask -TaskName QuantDBUpdate`，或从备份 XML 重新导入。对应实体页 [[quant-db]]。

## [2026-09-18] create | AI 协作工具链经验页 + 新建 ai-tools 子目录
- **操作者**: AI (DSH)
- **原因**: 用户要求把 AI 协作工具链经验沉淀进知识库专用目录；先全库查重（无同类主题页，[[local-ai]]/[[mimo-review]]/[[file-organizer]] 均为项目组件页），并按 FILE-MANAGEMENT-STANDARD 决策树确认无语义冲突。
- **影响**:
  - 新建 wiki/entities/system/ai-tools/ 子目录（路径经用户确认）
  - 创建 wiki/entities/system/ai-tools/ai-toolchain-notes.md（type entity，tags [system, tool]，链 [[local-ai]]/[[mimo-review]]/[[file-organizer]]/[[sop-v1.1]]）
  - 登记 SCHEMA.md 三层架构目录树（system/ 改为非末位，新增 ai-tools/ 子目录；327 -> 329 行，前后缀哈希对账不变）
  - 登记 FILE-MANAGEMENT-STANDARD.md §2.1 目录树 entities/ 行注释（408 行不变，前后缀哈希对账不变）
  - 更新 wiki/index.md（Entities — Tools 分组加条目；Total pages 58 -> 59）
- **备注**: 规则本体仍以 SOP 为唯一事实源，本页只记机制与实测证据、引用条款编号；改动前已备份原文件至 G:\deeeseek\ai-toolchain-backup-20260918\。未触碰 wiki/.env。

## [2026-09-18] decision | 主库初始化 git 留痕（依准则第 10 条）
- **操作者**: AI (DSH)
- **原因**: 用户要求落实准则第 10 条；此前 `G:\quant-investing` **无 git**，改动无回滚点（AI 曾在此写过规范/索引/日志而无快照）。
- **影响**:
  - `git init -b main` + 首次提交 `51a32b3`，入库 245 文件 / 19.63 MB
  - 新增 `.gitignore`：排除 `wiki/.env` 等密钥、`data/quant.db`(24MB)、`code/data_cache/`(96MB parquet)、`__pycache__`/`*.pyc`、`_` 前缀临时文件、Obsidian workspace 状态
  - 新增 `.gitattributes`（`* -text`）+ 本地 `core.autocrlf=false`：本机 **system 级 autocrlf=true** 会静默改写行尾，已阻断；抽查 5 文件入库字节与磁盘一致
- **备注**: 代码与目录未移动、未改内容，仅新增版本控制；`wiki/.env` 确认未入库（命中 0）；详见 [[ai-toolchain-notes]] 坑 8。

## [2026-09-18] fix | 主库卫生整改：SOP 校正 / 日志修复 / 杂物清理 / 密钥迁出
- **操作者**: AI (DSH)
- **原因**: 知识库通读发现 20 项问题，用户拍板处理前三类。
- **影响**:
  - `docs/SOP.md` v1.6→**v1.7**：§8.1 环境表按实测校正（Ollama 0.32.15→0.34.2；补 `qwen2.5vl:7b` 视觉模型；修正模型存储路径笔误 `quant-investingi`；补端点与 DSH 路由）；§8.5 补两条本地 AI 限制（OpenAI 端点静默丢 tools、视觉模型会编造）；§6 迭代记录加 v1.7 行
  - `wiki/log.md`：修复 3 条格式损坏条目（`2026-08-22 批量修复…`/`2026-08-25 价值投资转型…`/`2026-08-29 初筛管线…` 补 action 与 `|` 分隔符）→ 73 条主条目 100% 合规
  - `wiki/SCHEMA.md`：补登记 8 种实际在用但未登记的 action（`fix`/`build`/`verify`/`audit`/`review`/`review-prep`/`organize`/`delete`）
  - 删除库根 2 个 0 字节杂物（`审计范围：选股层因子`、`最后更新：2026-08-22`）与 wiki 根 6 个杂物（4 个空表/画布 + `untitled-session-20260822.json` 73KB，其 `session` 为 null）
  - **密钥迁出 vault**：`wiki/.env` → `G:\deeeseek\secrets\quant-investing-wiki.env`（SHA256 校验一致后删除原位）；`code/setup_obsidian.py` 写入路径改到 vault 外；`code/wiki_ingest.py` 与 `code/json_to_note.py` 增加"环境变量→secrets→旧位置"读取顺序；实测 `OBSIDIAN_KEY` 长度 64 加载成功
- **备注**: 三处脚本改动均通过 `ast.parse` 语法检查与 runpy 模块级加载实测；`.gitignore` 增加 `*.env`/`*.key`/`secrets/` 保险。FMS:364/387/392/393 登记的待清理项中，杂物与密钥两条已消除；`code/_draft/` 缺失与 factor_docs frontmatter 缺失仍待办。

## [2026-09-19] build | 新建 DSH 插件内部机制页：`@local/btw-side` v1.2.0 + 两个 skill
- **操作者**: AI (DSH)
- **原因**: 用户要求把本次「旁支提问」插件的实战结论沉淀入库。本次排查出的三条机制性结论（常驻子代理会唤醒父代理、工具过滤方向、会话日志是多帧 zstd）此前无任何可复用载体。
- **影响**:
  - 新增 `wiki/entities/system/ai-tools/dsh-plugin-internals.md`（七节：Host/Client 重载差异 / 常驻子代理唤醒父代理 / `allow` vs `deny` / 命令生命周期 / 会话日志多帧 zstd / 两个静默坑 / 判据层级）
  - 新增 skill **`dsh-host-plugin`**（Host 半边与子代理编排）；与既有 `dsh-web-ui-plugin`（Client 半边）分工，两者互相引用
  - **修正一条自己记错的约定**：wiki 页行尾是 **LF**，不是此前记录的 CRLF（`index.md`/`log.md`/`ai-toolchain-notes.md` 三个文件实测 `CRLF=0`）。若照错约定转换，会重演 SOP.md 那次整文件假 diff
  - 工作区侧同步：`DSH-PLUGIN-AUTHORING.md`（新增 §12 两个坑 / §13 唤醒机制）、`KNOWLEDGE-MAP.md`、`交接-HANDOFF/HANDOFF.md`、新增 `btw-side-plugin/REVIEW.md`
  - 新增工具 `G:\deeeseek\tools\read-session-log.mjs`（读多帧 zstd 会话日志）
- **备注**: 本轮最贵的一课是「**锚到卡片 ≠ 锚到按钮**」—— 代码一行没错，是参照系错了；读代码发现不了，用户看一眼截图就指出来了。据此在 skill 里立了判据层级：`座位注册 active:true` ＜ `渲染` ＜ `能交互` ＜ `位置观感` ＜ `用户看到的输出正确`，并明确**不许把低层证据当高层结论**。v1.2.0 尚未实测（Host 半边需重启 DSH）。

## [2026-09-19] build | DSH 工具呈现模式实测：PTC vs native 成本曲线 + 决策卡
- **操作者**: AI (DSH)
- **原因**: 用户依次追问「PTC 的运用场景」「能否自主判断模式」「好处坏处」，最后要求实测数字与固化。三轮实测（2026-09-19，DSH 0.1.6-alpha.2 / deepseek-flash / reasoningEffort=max）产出了此前无载体的定量结论：PTC 的累计新输入 token 恒定、native 随"读文件 vs 写脚本"漂移，以及三档成本优势与两个可复现的坑。
- **影响**:
  - 新增 `wiki/entities/system/ai-tools/dsh-tool-presentation-modes.md`（六节：结论曲线 / 判据 / 任务措辞 / 反模式 / 测量方法 / 关联），confidence 85（定量实测，n=2/单元格）
  - 更新 `wiki/index.md`：Entities — Tools 增补 1 条，总页数 59 → 60
  - 工作区侧产出：`G:\deeeseek\ptc-vs-native-bench\`（REVIEW.md 三轮复盘 / docs/decision-card.md 一页决策卡 / data/summary-sizes3.json / code/analyze-size3.mjs / logs/S3-*.out.jsonl 16 份）
  - 修正前两轮的自行结论：**"小文件 PTC 更贵 1.5×"是措辞与模型行为污染造成的**，干净复测下 2.8 KB 上 PTC 仍省 1.39×；"大文件省 2.2×"被加强为 24.8 KB 省 3.53×
- **备注**: 本轮最贵的一课是「**fixture 隔离**」——模型找不到指定文件时会 `glob("**/app.log")` 捞到上一轮的 fixture，把上一轮的答案当成结果返回（实测作废 4 个样本）。判据：**每个样本独立目录 + 任务里写绝对路径 + 分析脚本带跨 fixture 引用检测**。另两条：fixture 里的 marker 行会改变答案（模型对、答案键错）；并行重跑抢同一日志文件会写出截断日志。详细过程见工作区 `REVIEW.md` 第 8 节。

## [2026-09-19] create | DSH Agent Teams 能力页 + 与《AI 通用准则》v1.3 对标

- **操作者**: AI (DSH)
- **原因**: 用户先问「智能体团队的功能和作用」，再要求「与全局准则放大对比」。Agent Teams 是本机 `web` profile 当前**唯一**的模型委派路径（旧 `tool-subagent*` 四个控件已被 `agent-team-profile` 补丁禁用），而「准则哪些纪律能靠机制兜住」此前无可复用载体。查重：`entities/system/ai-tools/` 下 3 页均无此主题。
- **影响**:
  - 新增 `wiki/entities/system/ai-tools/agent-teams.md`（type entity，tags [system, tool]）：是什么（九个工具/持久日志/CAS 任务板/本机参数）/ 强制力四档 / 反向加压三处 / 机制不管的四件事 / 操作坑 / 与 subagent·workflow 分工
  - 更新 `wiki/index.md`：Entities — Tools 增补 1 条，总页数 60 → 61
  - 工作区侧产出：`G:\deeeseek\agent-teams-vs-准则\`（`AGENT-TEAMS-对标-通用准则v1.3.md` 逐条放大对比 + `REVIEW.md` + `.gitignore`）
  - 一手依据：`G:/AI-通用准则.md` v1.3 十二条全文、`docs/subsystems/agent-team.zh.md`、两个包 README、`agent-team-profile/cordis.patch.yml`
- **备注**: 关键结论——强制力分档：**工具层强制** §1/§6a/§6b/§7；**结构性支持** §2/§5/§10；**完全不覆盖** §3/§4/§9/§11；**反向加压** §7/§8/§12。最贵的三处：①§12 时间校准在团队内失效（fresh 成员不继承 Lead 历史，必须把当前时间写进初始任务）；②§6 审查方必须 `context: fresh`，否则继承 Lead 推理即违反「不复用同一段推理」；③§8 隐私落盘面翻倍（peer 消息进 target 历史、任务板快照进 Lead 日志）。另记三项机制不保证：`writeScopes` 非锁（Bash/codegen 绕过）、owner 永不自动释放、最终 diff 与测试是 Lead 不可外包的边界。已列 6 条**准则反哺建议**（时间注入/fresh 审查/隐私落盘面/writeScope 非锁/验收不稳不建队/建队前先问），**待用户裁决，本轮未改准则任何文件**。


## [2026-09-21] update | 本地模型升级（qwen3-30b-a3b）+ 模型库迁移 G 盘 + 坑 5 更正

- **操作者**: AI (DSH)
- **原因**: 用户要求「升级一下本地模型」，追问「模型体量可不可以再大一点」，随后要求「放到 G 盘中」。原环境仅 `qwen2.5:7b` / `qwen2.5vl:7b`（2.5 代）。
- **影响**:
  - 新增模型 `qwen3:30b-a3b`（17.28 GB，MoE）+ 固化变体 `qwen3-30b-a3b-cpu`（`num_gpu 0`）
  - 更新 `C:\Users\asus\.dsh\settings.yaml`：`ollama` 路由改为 3 模型，新增 CPU 变体（ctx 16384 / maxTokens 4096）；`qwen2.5vl:7b` 的 `contextWindow` 由 128000 改为诚实的 32768
  - **模型库迁移**：`C:\Users\asus\.ollama\models` → `G:\quant-investing\ai\models`（robocopy /MOVE，34 文件 / 27.203 GB），C 盘释放约 6.3 GB
  - 更正本页坑 5（原结论作废）、`wiki/index.md` 无需变动
  - 工作区侧产出：`G:\deeeseek\dsh-portable-rc2-inspect\docs\本地模型升级记录.md`（含全部实测数据与 server.log 证据）
- **备注**: 最贵的三课——① **`OLLAMA_MODELS` 改动后必须重启 Ollama**：server 启动早于变量设值时整套生命周期都用默认 C 盘路径；且**不能用 PowerShell `StartInfo` 判断进程环境**（它反映当前用户环境，会显示已生效的假象），唯一可信的是 `%LOCALAPPDATA%\Ollama\server.log` 里 server 自报的 `server config`。② **MoE 在纯 CPU 上可用、往 GPU 塞层反而更慢**：30B-a3b 每 token 只激活 3B，纯 CPU 19.5 tok/s；`num_gpu=4/8/12` 降到 9.2/3.7/1.1 tok/s（层间搬运拖累）。这推翻了「8 GB 显存只能跑 8B」的先前判断。③ **测试工具的缺陷容易被误当成被测系统的缺陷**：我一度以为 OpenAI 兼容端点有 UTF-8 缺陷（模型回「你发了一堆问号」），实际是我用 PowerShell 构造请求体时编码错误；改正编码后中文与 reasoning 字段分离均正常。另：`OLLAMA_NUM_GPU` 环境变量**无效**（官方 issue #11437），要固化只能写进 Modelfile。
## [2026-09-22] update | 本地模型选型实测：纯 GPU 61 tok/s，30B 因思考泄漏反而更差

- **操作者**: AI (DSH)
- **原因**: 用户问「哪个模型更好」，并明确要求「纯 GPU 的数据，同时要测质量」。此前一轮的对比把三只都强制 `num_gpu=0`，对 7B 不公平。
- **影响**:
  - 工作区新增 `G:\deeeseek\dsh-portable-rc2-inspect\docs\本地模型选型结论.md`（含全部实测数据、复现脚本）
  - 更新本页 `local-ai.md`：引擎版本 0.32.15→0.34.2、补入三只模型、新增「选型结论」节、更正显存为 8151 MiB、更正模型存储说明、分工表补四行
  - 新增可复用测试脚本：`data\gpu-only-bench.mjs`（纯 GPU 速度+6 道可判分质量题）、`data\q30b-quality.mjs`、`data\think-probe.mjs`
- **备注**: 三条关键实测——① **纯 GPU 对 7B 是 6.4 倍提升**：`qwen2.5:7b` 4.99GB 全进显存、61.1 tok/s（CPU 时仅 9.5），`qwen2.5vl:7b` 5.73GB、62.3 tok/s。② **「参数更大=更好」被否定**：`qwen3-30b-a3b` 只能纯 CPU（17.28GB 权重装不进 8GB 显存，部分 offload 反而更慢：9.2/3.7/1.1 tok/s < 纯 CPU 19.5），且质量 **4/6 低于 7B 的 5/6**。③ **30B 更差的机制是「思考泄漏」**：`think=false` 对它无效，思考混进正文（约束题输出 887 汉字，要求 ≤20）→ JSON 题也无法解析；而 `think=true` 时正文为空、token 全被思考吃光。针对 `think` 三态的探针实测：false→正文 420 汉字/thinking 0；不传→正文 0/thinking 550；true→正文 0/thinking 559。**结论：思考型模型与 DSH 的 OpenAI 兼容端点配合不良，本地默认应用非思考型的 `qwen2.5:7b`**。另：三只的**多步算术均不可靠**（7B 答 221/280，正确 226），该类任务应走云端。
## [2026-09-22] update | NPU 推理加速可行性：有硬件但走不通 Ollama 路线

- **操作者**: AI (DSH)
- **原因**: 用户问「可用 NPU 作为推理加速吗」。
- **影响**:
  - 工作区新增 `G:\deeeseek\dsh-portable-rc2-inspect\docs\NPU推理加速可行性核查.md`
  - 更新本页 `local-ai.md`：硬件表新增 NPU 行 + 新增「NPU 能否用于推理加速」节
  - `wiki/index.md` 无需变动（未新增页面）
- **备注**: 三条结论——① **硬件有**：`Intel(R) AI Boost`（PnP `Class=ComputeAccelerator`、`PCI\VEN_8086&DEV_AD1D`、驱动 32.0.100.3717 已装）。**我先前的推测「HX 系列常砍掉 NPU」被实测推翻，已纠正**——教训是不该用产品线惯例替代本机设备查询。② **Ollama 用不了**：本机 Ollama 0.34.2 的 `lib\` 仅有 `ggml-cpu-*`/`ggml-cuda.dll`/`ggml-vulkan.dll`，**无任何 openvino/npu 后端**（与官方 issue #5747 开放状态一致），故 DSH 的 ollama 路由不可能走 NPU。③ **理论可行但不划算**：llama.cpp 的 OpenVINO 后端支持 `GGML_OPENVINO_DEVICE=NPU`（需 UD32+，已满足），但 NPU 主要支持 `Q4_0`（本机三模型均 `Q4_K_M`）、建议上下文 512、不支持模型缓存、不支持 `llama-server -np > 1`；而独显已实测 61.1 tok/s。**显存被游戏占用时的更简单答案**：CPU 固化变体（17.7 tok/s）或 7B `num_gpu 0`（9.5 tok/s）。核验边界：「NPU 比独显慢」是架构定位推断，**未实测**；要把这条变事实需装 OpenVINO 栈 + Q4_0 模型跑基准。
## [2026-09-22] update | 卸载 qwen3-30b-a3b-cpu（本地路由缩回 2 个模型）

- **操作者**: AI (DSH)
- **原因**: 用户指令「qwen3-30b-a3b-cpu 将其卸载了」。
- **影响**:
  - `ollama rm qwen3-30b-a3b-cpu` → 成功；`ollama list` 剩 `qwen3:30b-a3b`、`qwen2.5vl:7b`、`qwen2.5:7b`
  - 更新 `C:\Users\asus\.dsh\settings.yaml`：移除该模型条目，`ollama` 路由由 3 个缩回 **2 个**（`qwen2.5:7b` ctx 32768 / `qwen2.5vl:7b` ctx 32768）；已用便携包自带 `yaml` 库严格解析验证通过，**无悬空引用**
  - 配置备份：`backup\20260922-005852\ollama-config\settings.yaml`
  - 更新本页 `local-ai.md`：配置表标注「已卸载」、选型结论表加「当前状态」列
- **备注**: 两个要点——① **卸载未释放磁盘**：该变体是 `FROM qwen3:30b-a3b` + `PARAMETER num_gpu 0` 创建，**复用基础模型的 blob**，故删除只移除 manifest 与极小的参数层；G 盘可用空间保持 62.85 GB 不变，模型库仍 27.20 GB。若要真正回收 18 GB 需 `ollama rm qwen3:30b-a3b`（基础模型，本轮**保留未删**）。② 卸载依据是前一日的实测：该模型质量 4/6 < 7B 的 5/6，且有**思考泄漏**（`think=false` 无效，思考混进正文，约束题输出 887 汉字 vs 要求 ≤20），另需 19 GB 内存与 32 秒冷启动。
## [2026-09-22] update | 删除基础模型 qwen3:30b-a3b（实际释放 17.29 GB）

- **操作者**: AI (DSH)
- **原因**: 用户指令「把基础模型 qwen3:30b-a3b 也删掉」。
- **影响**:
  - `ollama rm qwen3:30b-a3b` → 成功；`ollama list` 剩 **2 只**：`qwen2.5vl:7b`（6.0GB）、`qwen2.5:7b`（4.7GB）
  - **实测释放 17.29 GB**：G 盘可用 62.85 → **80.14 GB**；模型库目录 27.20 → **9.92 GB**（回到 2026-09-21 升级前水平）；blobs 15 → 10
  - 两只剩余模型各实测一次推理，**均正常返回**（`qwen2.5:7b` / `qwen2.5vl:7b`）
  - 更新本页 `local-ai.md`：配置表改为「已删除」、选型结论表状态列、变更历史加行
  - 工作区 `data\Modelfile.qwen3-30b-a3b-cpu` 加 **作废标注**（基础模型已删，不可再用），保留作记录
  - `wiki/index.md` 无需变动
- **备注**: 三点——① **变体删除不释放磁盘、基础模型才释放**：前一轮删 `qwen3-30b-a3b-cpu` 时 G 盘可用空间**纹丝不动**（62.85 GB），因为它 `FROM qwen3:30b-a3b` 复用同一批 blob；本轮删基础模型才真正回收。② **我的脚本算错过一次**：首次核算打印「释放 533.63 GB」，是换算写成 `6285*1MB*100` 的 bug，已用「G 盘可用差值」与「模型库目录差值」两路交叉核对得正确值 17.29 GB。③ 本机本地模型自此收敛为 **`qwen2.5:7b` + `qwen2.5vl:7b`**，DSH 的 `ollama` 路由同为这 2 只，配置无悬空引用。
## [2026-09-22] update | NPU 能力边界探索（实测）：游戏帧率不可能、数学计算不可用、并行不抢资源

- **操作者**: AI (DSH)
- **原因**: 用户要求「探索 NPU 的能力边界，游戏帧率加成，数学模型的计算等」。
- **影响**:
  - 新增任务目录 `G:\deeeseek\npu-capability-explore\`（docs 报告 + data 脚本与原始 JSON）
  - 更新本页 `local-ai.md`：新增「NPU 能力边界（实测）」节
  - `wiki/index.md` 无需变动（未新增页面）
- **备注**: 六条关键实测——① **实测算力远低于理论**：声明 13,107 GOPS(INT8)，有效仅 158→761 GOPS（512³→2048³），达理论 1.2%–5.8%，且随规模强增长。② **形状交叉点**：固定开销约 0.9ms，L<~450 CPU 更快、L>~500 NPU 更快。③ **动态形状会让宿主进程原生崩溃**（`STATUS_STACK_BUFFER_OVERRUN`，非可捕获异常）——这是最危险的边界，测试必须子进程隔离。④ **游戏帧率不可能直接提升**：NPU 设备类为 `ComputeAccelerator`，无渲染/显示能力（显示适配器注册表仅 iGPU/独显/虚拟显示），帧生成类技术都跑在 GPU 上。⑤ **但游戏时并行成立**：NPU 满载时 GPU 利用率仅 +0.1 个百分点、显存 −16MiB、CPU 2.3% 单核——NPU 是真正独立的计算引擎，可在游戏时承担本地 AI 而不掉帧，这是它唯一不可替代的价值。⑥ **数学模型计算不可用**：比 CPU 慢 1–24×（蒙特卡洛 GBM 23.6×、Black-Scholes 7.6×），且 NPU 走 FP16 导致精度差约 1000×（误差 1e-1 vs CPU 1e-5）。另：7B LLM 的 NPU 编译 >10 分钟未完成，小模型仅 0.2s，说明编译成本随规模非线性上升。定位：**NPU = 低功耗独立的小模型定长前向协处理器**，不适用于 LLM 生成与数值计算。
## [2026-09-22] update | Jev 决策模型 NPU 端到端探索 + 两处自我纠错

- **操作者**: AI (DSH)
- **原因**: 用户要求「探索 NPU 能力边界、游戏帧率、数学模型计算」，并「尝试 Jev 决策模型在 NPU 的运行」，全程走代理。
- **影响**:
  - 新增 `G:\deeeseek\npu-capability-explore\`（docs 三份报告 + data 20+ 脚本与原始 JSON）
  - 更新本页 `local-ai.md`：新增「NPU 能力边界（实测）」与「Jev 决策模型在 NPU 上的实测」两节
  - 环境新增：torch 2.11.0+cu128、onnx/onnxruntime/onnxscript、datasets、openvino-genai
  - 新数据集与模型：`G:\npu-experiment\`（typed-decisions 1.9MB、ModernBERT-base、jevlite.pt）
- **备注**: 三条主线结论——① **能力边界**：声明 13,107 GOPS(INT8) 而实测有效仅 158→761 GOPS（1.2%–5.8%），固定开销 0.9ms、交叉点 L≈450；**动态形状会让宿主进程原生崩溃**（`STATUS_STACK_BUFFER_OVERRUN`），必须子进程隔离测试；11/11 常用算子可用；7B 编译 >10 分钟不完成。② **游戏帧率**：NPU 设备类为 `ComputeAccelerator`、**无渲染/显示能力**，**不可能直接提升帧率**；但**满载时 GPU 利用率仅 +0.1 个百分点**，可在游戏时并行承担 AI 而不掉帧。③ **数学模型计算**：**不可用**——比 CPU 慢 1–24×（蒙特卡洛 23.6×、Black-Scholes 7.6×），且 FP16 精度差约 1000×。④ **Jev 全链路打通**（训练→ONNX→OpenVINO→NPU），但**完整模型 NPU 1625ms vs CPU 568ms 慢 2.9×**；**编码器单独则 NPU 全面胜出**（L=768: 253 vs 383ms），根因是 torch.export 的动态形状脚手架。修掉两个真实障碍：torch 需 cu128 才有 Blackwell sm_120 内核；NPU 不支持 IsNaN，用 `Not(Equal(x,x))` 等价替换后编译通过。**两处自我纠错**：(a) 串行配置扫描报的 TURBO +75.6% 是编译缓存导致的假象，A/B 交错复核后真实增益仅 0.7–4%；(b) 据编码器数据推断「Jev 适合 NPU」被完整模型否定。教训：涉及编译缓存的性能对比必须 A/B 交错。

## [2026-09-22] update | Jev 决策端点服务化（NPU 混合推理常驻 HTTP 服务）+ 接入 DSH 可选 provider

- **操作者**: AI (DSH)
- **原因**: 用户要求把上一轮已跑通的 Jev NPU 混合推理管线做成常驻本地 HTTP 服务，并接进 DSH 作为可选 provider。查重：[[local-ai]] 已有「NPU 能力边界（实测）」「Jev 决策模型在 NPU 上的实测」两节，本轮为**增量**（新增一节 + 就地更正三处冲突），既有内容一律保留未删。
- **影响**:
  - 新增任务目录 `G:\deeeseek\jev-endpoint\`：`code\jev_server.py`（服务本体，FastAPI + OpenVINO 原生 API）+ 验证脚手架（`verify_parity.py` / `verify_latency.py` / `smoke_call.py` / `tools_probe.py` / `verify_dsh_config.mjs` / `dump_providers.py`）、`data\`（`parity.json` / `latency.json` / `smoke-call.txt` / `tools-probe.txt` / `providers.json` 等原始实测数据）、`docs\使用与集成说明.md`
  - 更新 `wiki/entities/system/local-ai.md`：新增「Jev 决策端点服务化 + DSH 集成」节（实测数据 / DSH 集成 / `tools` 限制 / 两条正确性约束 / 两个 bug / 可复用配方 / 遗留），变更历史加行；并**就地更正三处冲突**（见备注 ⑩）
  - 更新 `C:\Users\asus\.dsh\settings.yaml`：`llm-pi-ai.providers` 新增 `jev`（**可选 provider，默认路由未改动**），另修掉一条过期注释；改动前已备份 `backup\20260922-132848\settings.yaml.bak`
  - 本次文档改动的文件级备份：`G:\deeeseek\kb-archive-jev-endpoint\backup\20260922-133534\`（`local-ai.md.bak` / `log.md.bak`）
  - `wiki/index.md` 无需变动（未新增页面，页数不变）
- **备注**: 十条要点——① **决策一致率 100/100 = 100%**（NPU 混合管线 vs CPU 全量 PyTorch；20 条真实测试样本，`LocalLLaMA/typed-decisions` test split 的 `agent_trace_observability` 工作流，共 100 个决策）。② **logit 相对误差中位 0.984%、最大 1.927%**，绝对误差中位 0.0270；**余量很薄**——最大相对误差距验收线 2% 只剩 **0.073 个百分点**，换样本批或更长序列必须重跑对账，不能假定仍过关。③ **延迟**（60 轮交错测量 + 40 次预热）：服务端端到端中位 **192.7 ms** / p95 196.0（原生 `/decide`）；OpenAI `/v1/chat/completions` 中位 **192.6 ms** / p95 195.9 —— **两条通道无可测差异**（OpenAI 那层只是协议翻译）；HTTP 往返中位 **209.8 ms**；**首次调用（冷）380.0 ms = 稳态的 1.8×**。④ **口径必须分开报**：**2.71× 是 HTTP 往返口径**（568.4 / 209.8），用服务端 e2e 192.7 ms 算则是 **2.95×**；服务端 e2e 192.7 ms 与上一轮同进程实测 **189.18 ms 吻合**，说明服务化只增加约 17 ms（网络+序列化），**没有回归**。⑤ **DSH 集成不是靠猜**：直接调用 DSH 编译产物里的**同一个** `resolveProfiles(providers, 'strict')`（`packages/llm/llm-pi-ai/lib/types/config.js`）严格校验通过，`jev` 路由可用（`piProvider` 已构造、无 `catalogError`）；**默认路由未改动**（仍是 `deepseek-official` / `deepseek-flash`）。⑥ **关键限制**：带 `tools` 的请求被接受，但服务**返回纯文本、永不产生 `tool_calls`**（HTTP 200 / `finish_reason=stop`）；含 `assistant(tool_calls)` + `tool` 角色的多轮消息**能被接受**；`stream=true` 的 SSE 正常（**3 个事件 + `data: [DONE]`**）→ 这条路由在 DSH 里**只能当纯文本决策模型用，无法驱动 agent 工具循环**（分类模型没有解码器，本来就没有工具调用能力）。⑦ **编码器必须用 `enc_realmask.onnx`**（导出 dummy mask 含 padding），**不是** `enc_dynamo_eager.onnx`（全 1 mask）——后者会静默固化错误掩码逻辑，**决策一致率掉到 78%**，管线照样跑、速度也快，**只有对账才发现它算的是错东西**；运行中服务已用 `GET /health` 核实用的是 `enc_realmask.onnx`。⑧ **启动**：NPU 编译缓存**命中 0.5 s** / **未命中 28.3 s**（本轮自检另捕获一次 18.1 s；三档按条件并存，运行中服务 `/health` 复核 `compile_s=0.51`）。⑨ **两个真实 bug**：(a) `from __future__ import annotations` ＋ **把 FastAPI 请求模型定义在 `build_app()` 函数内部** → FastAPI 无法解析前向引用，**静默降级**把请求体当查询参数，每个 POST 回 `422 {"loc":["query","r"],"Field required"}`；**import 成功、健康检查也过，只有真发一次 POST 才暴露**；修法＝请求模型定义在**模块级** + 启动自检 `_assert_body_params()`。(b) Windows 控制台默认 **GBK**：`print` 里带 `✓`/`✅` 这类**排版符号**抛 `UnicodeEncodeError` **把服务直接打死**（**中文本身没问题**，危险的是符号）；修法＝启动 `sys.stdout.reconfigure(encoding="utf-8")`；同一个坑本轮在**两个不同脚本**里各踩了一次。⑩ 另修 `settings.yaml` 一条过期注释（原写「基础模型 qwen3:30b-a3b 保留未删」，实际已删除并回收 **17.29 GB**）；**就地更正 `local-ai.md` 三处冲突并注明**：配置表 NPU 行「但**当前不可用**」→ 2026-09-22 起已实际投用（澄清那是「不能加速 Ollama/LLM」的语境，不等于 NPU 本身不可用）；「NPU 能力边界」节定位行的「38.4ms 快 CPU 1.58×」→ 补注那是第 5 轮**编码器单独**数据，已被本轮 192.7 ms 服务端端到端取代（定位结论不变）；「Jev 决策模型在 NPU 上的实测」节「**未实施但可行的架构**」→ 混合执行**已实施且已服务化**，仅「手写精简 OpenVINO 图绕开 torch.export 脚手架」仍未做。
## [2026-09-23] create | 本地 QLoRA 微调 7B 实践方法论
- 操作者: AI (DSH)
- 原因: 用户要求为已归档的本地情感模型微调项目留一条方法论笔记（只含技术栈与教训，语料/个人数据不入库）
- 影响:
  - 新增 wiki/entities/system/ai-tools/qlora-local-finetuning-methodology.md（type: entity, tags: [system, tool], confidence: 65）
  - 更新 wiki/index.md：Tools 分组新增该页一行条目
- 备注: 内容涵盖环境选型、四个训练卡点、curl 下载校验、GPU 疑难杂症七步排查法（含张量核慢 3× 未解案）；与 [[local-ai]]、[[ai-toolchain-notes]] 互链

## [2026-10-08] create | 豆包 Seedream 生图接入 DSH

- **操作者**: AI (DSH)
- **原因**: 用户要求把火山方舟 Seedream 生图接进 DSH，且明确「面板出图显示在面板里、对话的图显示在对话里、面板不能影响主对话」
- **影响**:
  - 新增 `wiki/entities/system/ai-tools/doubao-image-generation.md`（type: entity, tags: [system, tool], confidence: 95）
  - 更新 `wiki/index.md`：Entities — Tools 分组新增该页一行条目
  - 源目录与交付物：`G:/deeeseek/doubao-image/`（bundle `@local/doubao-image`，装入 `profiles/web`；11 个 git 提交）
  - 第三方核实留档：`G:/deeeseek/ark-verify/`（官方文档渲染正文 + REPORT.md）
- **备注**: 十条坑，其中三条最值钱——① **方舟有两台互不相通的接口面**（订阅制 key 只认 `/api/plan/v3`、走量 key 只认 `/api/v3`），用错面的报错正好是 401 `AuthenticationError`，与「key 抄错了」**同一个错误码**，害我走了一整条错路（试三种 key 长度变体、怀疑地域、准备重新签发），而真正要改的只是一个路径段；② **命令名不允许中文**且失败会连坐（同一 apply 里已注册的工具被一起回滚，现象是「工具没出现」、根因在函数末尾）；③ **Host 半不热重载**，`set_plugin` 也不重新 import 模块，判断新代码是否生效只能靠「报错行号与当前文件内容的对应关系」。
  另有两条可复用的方法：**自检要验「可用」而不是「存在」**（用超范围尺寸探测，走完鉴权/账户/模型/参数四层却不出图不计费）；**用可观测副作用事后判定走了哪条路径**（面板产物不入附件库、对话产物必入库，逐个算 sha256 即可分辨，6 个产物实测吻合）。
  三条路径均已端到端验证：对话工具、`/draw` 命令（会话日志零消息事件）、面板回环通道（用户确认对话无新增）。

## [2026-10-08] fix | 修正 doubao-image-generation 里一条错误的核对判据

- **操作者**: AI (DSH)
- **原因**: 用户要求「在主对话里生成图片」做验收时，我用错了对照物，把「落盘文件与附件对象逐字节一致」当成通过判据写进了文档，实际哈希并不相等
- **影响**:
  - 更新 `wiki/entities/system/ai-tools/doubao-image-generation.md`：「路径归属的判定方法」一节改写，把错误判据与正确判据并列写清
  - 源项目 `G:/deeeseek/doubao-image/REVIEW.md` 同步修正（验证表 + 路径归属一节 + 新增第 22 条教训）
- **备注**: 两个错叠加 —— ① **对照物错**：正确对照对象是**工具结果里给出的 attachmentId**，不是文件名、也不是落盘文件；② **前提错**：落盘的是接口返回的**原始字节**（`result.bytesRaw`），入库的是 `saveImage` **归一化重编码**后的图（实测 1773×2364 → 1134×1512，470 KB → 501 KB），两者本来就不该相等。
  正确判据：该 id 指向的对象存在，且其**自身** sha256 内容哈希 == 该 id（内容寻址自校验）。按此复核，对话路径完全正常。
  **可复用教训：核对时「拿哪个数字去比」本身就是结论的一部分。** 用错对照物算出的「不一致」，与一个真实缺陷长得一模一样 —— 这次是靠换判据重算把它拦下，而不是靠第一遍就想对。

## [2026-10-08] update | ai-toolchain-notes 新增 Ollama 打包与分享大文件两坑

- **操作者**: AI (DSH)
- **原因**: 用户要求把本地 `tongnai-nsfw`（Qwen2.5-7B 派生、LoRA 已合并、Q5_K_M）打包并生成分享链接（选内网穿透 + 自行分发）。过程中踩到两条会静默坑人的工具链问题，且**看文档看不出来、必须实测才暴露**，故沉淀。
- **影响**:
  - 更新 `wiki/entities/system/ai-tools/ai-toolchain-notes.md`：新增坑 10、坑 11，frontmatter `updated` → 2026-10-08，补变更历史一行（**未新建页面**，查重后并入既有页面）
  - 未改 `wiki/index.md`：本次为既有页面更新，无新页需挂目录
  - 任务目录与交付物：`G:/deeeseek/tongnai-nsfw-分享包/`（GGUF 5.07 GB + Modelfile×2 + 双平台导入脚本 + README + REVIEW.md；权重经 NTFS 硬链接入包，零额外占用）
- **备注**: 两坑的核心事实——
  ① **`ollama show --modelfile` 的输出无法回灌 `ollama create`**（0.35.0）：`SYSTEM """` 必须与首行内容同行、`TEMPLATE` 必须压成单行（换行转义为字面 `\n`，渲染时会正确还原）。REST `/api/create` 另有一坑：对**本地 GGUF 路径**一律报 `invalid model name`，而 registry 模型名同端点正常 —— **导入本地 GGUF 只能走 CLI**。附带实测澄清一条安全疑虑：`ollama create` **不会写透硬链接**（命中已有 blob 即复用，源文件链接数与 hash 均不变）。
  ② **`SimpleHTTPRequestHandler` 根本不处理 `Range` 头** —— 5 GB 文件断点续传会静默失效（返回 200 整包而非 206），需自实现；且统计流量不能按 `Content-Length` 计数。**cloudflared 在本机 Mihomo fake-IP 环境下 QUIC 必失败**（UDP 7844 出不去、TCP 被代理），必须 `--protocol http2`。
  **验证纪律**：这条链路没有只 ping 首页就收工 —— 完整下载 5 GB 比对 SHA256 通过，再从**公网域名**拉前 1 MB 与本地文件逐字节比对通过。
  另有一条与隐私边界相关、需用户自行判断的遗留：公网链接一旦外流不可收回，Quick Tunnel 官方不保证可用性。

## [2026-10-08] create | 小额账户两条新页（1800 元实盘方案的知识提炼）

- **操作者**: AI (DSH)
- **原因**: 用户要求为 1,800 元闲钱账户做一份可执行的 A 股实盘方案。取证过程中得到两条**本库尚无**的知识：① 佣金下限对小额账户的策略级支配效应（含 ETF 同样适用 5 元下限这一非直觉事实）；② 小额账户的整手/权限/成本三重约束与执行框架。按准则第 7 条沉淀入库；查重后确认与 [[backtest-cost-model]] 不重复（该页有费率参数，但未展开小额场景的策略级影响）。
- **影响**:
  - 新增 `wiki/concepts/risk-management/small-account-minimum-commission.md`（type: concept, tags: [system, tool, decision], confidence: 75, **contested: true** —— "免5"可得性未获一手依据）
  - 新增 `wiki/entities/system/small-account-execution.md`（type: entity, tags: [system, tool, decision], confidence: 65）
  - 更新 `wiki/index.md`：Entities — System 与 Concepts — Risk Management 各加一行；页数 61 → 63；Last updated → 2026-10-08
  - 任务目录与交付物：`G:/股市探究/`（方案 v1 + 市场快照 + 5 份 raw 留痕 + 3 个可复算脚本 + REVIEW.md）
  - 改动前备份：`G:/股市探究/backup/vaultkb-20261008-195344/`（index.md.bak / log.md.bak）
- **备注**: 五条要点——
  ① **交叉印证**：本库既有 [[backtest-cost-model]] 独立记载"佣金 万2.5 双边（最低 5 元/笔）"，与本次从券商官网取得的一手费率公示一致，二者构成独立来源互证，**该页费率假设无需修改**。
  ② **非直觉事实**：券商公示页写明**场内基金（含 ETF）同样执行"每笔不足 5 元按 5 元"**。即 ETF 免印花税、却躲不掉佣金下限；常见说法"小额买 ETF 省钱"只对了一半。这直接改变了小额账户的成本结构。
  ③ **量级**：1,800 元本金、800 元持仓、股票口径 —— 月频交易全年费用 124.99 元 = **本金的 6.94%**；周频 30.09%；日频 144.67%（本金不够付手续费）。**佣金下限让"交易频率"而非"选股能力"成为第一决策变量。**
  ④ **三次自我纠错**（均已写入页面）：(a) 交易日历不能从第三方日历页推断 —— 初稿据二手日历写"10-08 休市"，被黄金 ETF 净值表出现 `2026/10/8` 行推翻；(b) 不能用指数点位推断市场状态 —— 上证 3842 点看似上涨周期，实际三季度科创50 **-30.7%**、沪深300 -12.5%、电子 -32.6%，指数与板块差 5 倍；(c) 不能用记忆代替取证 —— 2026 年美联储处**加息**通道（09 月加息至 3.75%~4.00%，2023-07 以来首次），沿用"降息=利好"叙事会得出相反结论。
  ⑤ **未取得项一律未填补**：全部 ETF 二级市场收盘价（现有均 NAV）、沪深300/中证500 估值分位、沪深主板"100股起买"的 2026 年官方条文、"免5"的监管依据、经手费/证管费一手费率表。

## [2026-10-09] update | 全库迁移 `G:\quant-investing` → `G:\股市探究\quant-investing` + 模型库清理

- **操作者**: AI (DSH)
- **原因**: 用户要求清理 Ollama 模型（只留千问原版 2 个 + `tongnai-nsfw`），并把知识库全量迁移到工作区 `G:\股市探究\` 下。**关键前提**：`OLLAMA_MODELS` 正指向 `G:\quant-investing\ai\models`，即本库同时是 Ollama 的**活动模型库**（不是备份）——清理模型与迁移目录是同一件事的两半，动完必须改环境变量并重启服务。
- **影响**:
  - **模型清理**（走 `ollama rm`，非手工删 `blobs/`）：删除 `tongnai`、`tongnai-v2/v3/v4/v5`、`tongnai-lora`、`tongnai-lora-v6` 共 7 个；保留 `qwen2.5:7b`、`qwen2.5vl:7b`、`tongnai-nsfw:latest`。blob 24 → 14 个，模型库 20.06 GB → **14.99 GB**
  - **整库改名移动**（同卷零复制）：`G:\quant-investing\` → `G:\股市探究\quant-investing\`，1396 文件 / 15.14 GB，git 历史 10 次提交完整
  - **环境与外部配置**：`OLLAMA_MODELS`（User）→ `G:\股市探究\quant-investing\ai\models`；Obsidian `obsidian.json` 的 vault 路径；计划任务 `QuantDBUpdate`（Disabled）的 arg；`G:\deeeseek\secrets\quant-investing-wiki.env` 的 `WIKI_PATH`
  - **路径引用批量修正**：82 个文件 / 182 处（code 22 个脚本，含 **14 个 `_` 前缀一次性脚本**；docs 15 份；wiki 25 页；`FILE-MANAGEMENT-STANDARD.md`；`SCHEMA.md`）
  - **`.gitignore` 补 `ai/`**：迁移前 `git check-ignore` 对该路径**返回空**——15 GB 大二进制处于「未入库但也未被忽略」状态，`git add -A` 会一次性灌进一个 8.6 MB 的仓库，且 blob 进历史后基本清不掉
  - **文件整理守护进程**重启（PID 29252）指向新路径
- **备注**: 四条最值钱的事实 ——
  ① **`ollama rm` 比预估更彻底**：原以为只删 manifest、留下 5.07 GB 孤儿 blob，实测孤儿被一并回收（14 个保留 blob 零缺失；`fsutil hardlink list` 显示无额外硬链接）。**清模型应走 `ollama rm`，手工删 `blobs/` 会破坏 manifest→blob 一致性。**
  ② **同卷移动是改名不是复制**：G: 盘内移动 15 GB 耗时 < 1 秒、可用空间变化 **0.00 GB**（前后均 18.56 GB）。这是「G: 仅剩 13.5 GB、放不下复制」约束下唯一可行的路径。
  ③ **`Move-Item` 会被「进程把该目录当工作目录」卡死**：整库移动第一次在 `code` 处中断（`used by another process`）。根因不是文件被锁——逐文件试开独占**全部可打开**——而是 `file_organizer_watch.py` 的 CWD 钉在 `code\`，而 Windows 不允许改名任何进程的当前工作目录或其祖先。**逐文件锁检测查不出这类占用**，得用「谁的命令行/CWD 指向它」来查。
  ④ **Ollama 桌面版会在启动后自动拉取 `llamacpp` 引擎**：迁移完成、server 重启后，`ollama app` 于 00:31:52 自动拉入 `llamacpp:4879c1a6…`（model 4.47 GB + projector 1.23 GB），模型库 14.99 → 20.55 GB，**G: 可用 18.56 → 13.00 GB**。非迁移缺陷，但把清理释放的空间又吃回去，磁盘余量需按 **13 GB** 计。
  **故意未改**：`wiki/log.md` 历史条目与 `docs/review_2026-08/` 22 份复盘的旧路径**保持原样**——操作日志与审计证据是「当时真实状态」的记录，回改等于伪造留痕，沿用 2026-08-21 那次迁移的处置先例。此决定在此披露。

## [2026-10-09] update | 全库迁移 `G:\quant-investing` → `G:\股市探究\quant-investing` + 模型库清理

- **操作者**: AI (DSH)｜**独立审查**: 1 路对抗性审查（只读，2026-10-09 00:35–00:48），结论「不能判定完成」，本条目已按其发现修正
- **原因**: 用户要求清理 Ollama 模型（只留千问原版 2 个 + `tongnai-nsfw`），并把知识库全量迁移到工作区 `G:\股市探究\` 下。**关键前提**：`OLLAMA_MODELS` 正指向 `G:\quant-investing\ai\models`，即本库同时是 Ollama 的**活动模型库**（不是备份）——清理模型与迁移目录是同一件事的两半。
- **影响**:
  - **模型清理**（走 `ollama rm`，非手工删 `blobs/`）：删除 `tongnai`、`tongnai-v2/v3/v4/v5`、`tongnai-lora`、`tongnai-lora-v6` 共 7 个；保留 `qwen2.5:7b`、`qwen2.5vl:7b`、`tongnai-nsfw:latest`。blob 24 → 14 个，模型库 20.06 GB → **14.99 GB**
  - **整库改名移动**（同卷零复制）：`G:\quant-investing\` → `G:\股市探究\quant-investing\`，git 历史完整（迁移前 **9** 次提交，迁移后 10 次）
  - **路径引用修正**：提交 `7e74543` 共 63 文件 / +2293 −1636。引用替换约百个文件（库内 code 22 个脚本 + docs/wiki 数十页 + 规范三份；库外另有 agent 配置与启动项）
  - **库外同步修正**（不在本库 git 内）：`OLLAMA_MODELS`(User)、Obsidian `obsidian.json`、计划任务 `QuantDBUpdate`、`G:\deeeseek\secrets\quant-investing-wiki.env`、三个 agent 指令文件（`.dsh/AGENTS.md`/`.claude/CLAUDE.md`/`.codex/AGENTS.md`）、`G:\AI-通用准则.md`、`G:\deeeseek\AGENTS.md`、`.claude` 记忆 4 份、doubao-image 的 `append-kb-log*.mjs`（源 + 已装副本）
  - **`.gitignore` 补 `ai/`**：迁移前 `git check-ignore` 对该路径**返回空**——大二进制处于「未入库但也未被忽略」状态，`git add -A` 会一次性灌进一个 8.6 MB 的仓库
  - **开机自启改造**：原 `启动\文件整理守护进程.vbs` 因 `WshShell.CurrentDirectory` 不吃非 ASCII 路径而失效 → 改建计划任务 `FileOrganizerWatcher`（登录触发、隐藏窗口、Unicode 路径原生支持）
- **备注**: 六条最值钱的事实 ——
  ① **`ollama rm` 比预估更彻底**：原以为只删 manifest、留下 5.07 GB 孤儿 blob，实测孤儿被一并回收（14 个保留 blob 零缺失）。**清模型应走 `ollama rm`，手工删 `blobs/` 会破坏 manifest→blob 一致性。**
  ② **同卷移动是改名不是复制**：G: 盘内移动 15 GB 耗时 < 1 秒、可用空间变化 **0.00 GB**。这是「G: 仅剩 13.5 GB、放不下复制」约束下唯一可行的路径。
  ③ **`Move-Item` 会被「进程把该目录当工作目录」卡死**：整库移动第一次在 `code` 处中断。根因不是文件被锁（逐文件试开独占**全部可打开**），而是 `file_organizer_watch.py` 的 CWD 钉在 `code\`，Windows 不允许改名任何进程的当前工作目录**或其祖先**。**逐文件锁检测查不出这类占用。**
  ④ **`WshShell.CurrentDirectory` 不接受含非 ASCII 的路径**：实测 `G:\股市探究` 必报「系统找不到指定的路径」。**编码不是原因**（同文件里中文 Echo 正常输出），是这个属性本身的问题；且 G: 盘**关闭了 8.3 短名生成**，`ShortPath` 返回长路径本身，没有 ASCII 别名可绕。另：`wscript.exe` 出错时弹的是**隐藏模态框**，表现为「无报错、无输出、进程未起」，极易误判。
  ⑤ **Ollama 桌面版会在启动后自动拉取 `llamacpp` 引擎**：迁移后 `ollama app` 自动拉入 model 4.47 GB + projector 1.23 GB，模型库 14.99 → 20.55 GB，**G: 可用 18.56 → 13.00 GB**。**「释放的空间」不等于「净增的余量」——释放后必须复测。** 另：`api/tags` 会返回非 manifest 条目（runner 清单、重复项），**判断模型库真实内容要看 `manifests/` 目录**。
  ⑥ **行尾指控的自我推翻（方法学）**：审查指出「14 个文件行尾被翻转」，复核为**测量假象**——`code/file_organizer.py` 从头到尾都是 CRLF 408 行，HEAD 与工作区逐字节相同；错误读数的来源是 **PowerShell 的 `>` 重定向以 UTF-16 写文件**，再按 UTF-8 解码即得虚假的 `\r\n`。**教训：行尾/编码类断言必须用 `git hash-object` 逐字节比对，不能用中间经过 PowerShell 管道或重定向的读数。** 该文件 447 B 的字节增量恰等于路径字符串变更（`G:\quant-investing` → `G:\股市探究\quant-investing`，前者 18 字节、后者 30 字节）× 出现次数，尺寸自洽。
  **审查发现的真缺陷（已全部修复，留档）**：
  (a) `obsidian.json` **首次改盘未落地**（回读发现与备份逐字节相同）——外部配置文件写完必须回读验证；已重写并 15 秒后复测留住。
  (b) **4 个已跟踪的 `code/logs/*.log` 被我的扫描排除规则误伤**，`git grep` 在 HEAD 里能查到旧路径；已明确列入豁免清单（历史运行日志）。
  (c) **两处双反斜杠转义形态漏改**（`_fm_increment.py`、`factor_tests/_update_s1_wiki.py`）——替换脚本未覆盖 `G:\\quant-investing` 形态，而这两个脚本会**把旧路径写回新文档**；已修。
  (d) **(c) 的同类**：`docs/review_2026-08/W3_文档三轨漂移.md` 里**引用的历史原文**被一并替换，导致引文与被引的 `log.md` L61 互相矛盾——**「引用不改」原则被我自己的批量替换破坏了**；已把引文恢复为原文并加注说明。
  (e) **测试污染知识库**：验收时往 `_inbox` 放的两个测试文件被守护进程正常处理（这恰好证明改造成功），但本地 AI 摄入进程据此**自动生成了知识页并改了 `index.md`**；已删除产物并把 `index.md` 恢复至 HEAD（`Total pages: 63` 未变）。
  **豁免清单（旧路径故意保留，附理由）**：`wiki/log.md` 历史条目（操作日志＝当时真实状态）；`docs/review_2026-08/` 的 C/M/W 证据摘要（复盘留痕）；4 个已跟踪的 `code/logs/run_2026*.log`（历史运行记录）；`.gitignore`/`.gitattributes` 首行自述注释；`G:\deeeseek` 下的 `backup/` 与 `archive/` 目录（冻结快照）。

## [2026-10-09] fix | 修 `get_full_stock_pool()` 重复列名致退市股静默丢失（生存者偏差防线失效）

- **操作者**: AI (DSH)｜任务目录 `G:\股市探究\fullA-检验与回测\`
- **原因**: 做数据新鲜度体检时，`get_full_stock_pool()` 抛 `InvalidIndexError: Reindexing only valid with uniquely valued Index objects`。追根因发现这是**长期存在且被静默吞掉**的缺陷，不是新问题。
- **根因**（一手定位，非推测）：`data_fetcher.py` 原第 540-544 行按「列名含『代码』」逐列改名，而退市股表是**沪/深 concat** 的结果，同时含 `公司代码`（沪 159 只非空）与 `证券代码`（深 208 只非空）→ 两列都被改成 `代码` → DataFrame 出现**重复列名** → 下一行按 `['代码','名称']` 取列时抛 `InvalidIndexError`；而该分支外层是 `except Exception: pass`，异常被静默吞掉。
- **影响**（实测）：`stock_master` 里 `delisted` 计数**长期为 0**——主表根本不含退市股。而回测股票池取自该主表 → **生存者偏差防线在最需要它的地方静默失效**。
- **修复**:
  - 显式按优先级**只取一列**并合并两列取值（`证券代码`/`公司代码`/`代码`/...），去重后输出，杜绝重复列名
  - **移除静默 `except: pass`**，改为 `logger.error` 显式报错——退市股缺失属必须可见的失败
  - 代码列/名称列缺失时给出 warning 并列出实际列名
- **验证**:
  - `get_full_stock_pool()` 返回 **5932 只 = 在市 5571 + 退市 361**，重复代码 0（修复前抛异常）
  - 手动重刷 `stock_master`：**5563 → 5932 只，退市标记 0 → 361**，`updated_at` → 2026-10-09
  - 补回 8 只 09-17 后新上市股票（`001246`/`301686`/`301716`/`601091` + 北交所 `920025`/`920201`/`920202`/`920229`）
  - 手动重刷 `mcap_snapshot`：66708 → **72279 行**，最新日期 2026-09-17 → **2026-10-09**
- **备注**: 三条可复用教训 ——
  ① **同一张表的两套代码列，是 concat 的产物，不是冗余**：沪市只在 `公司代码` 有值、深市只在 `证券代码` 有值（实测 159 + 208 = 367），按「列名包含关键词」批量改名会把两列撞成同一个名字。**批量改名前必须检查目标列名是否唯一。**
  ② **`except: pass` 让一场静默失败伪装成正常运行**：这个函数一直"能返回结果"（只有在市股票），调用方拿到的池子看着正常，只是少了 361 只退市股。**关键数据缺失必须响亮失败**，不能靠「函数没抛异常」判断它做对了。
  ③ 附带确认：`QuantDBUpdate` 计划任务处于 **Disabled** 且**系用户主动关闭**，非故障。本轮为手动刷新，未改动该任务状态。

## [2026-10-09] note | 数据新鲜度体检结论

- **操作者**: AI (DSH)｜脚本 `fullA-检验与回测/code/freshness.py`
- **体检时点**: 2026-10-09 01:32（当日未开盘，最近收盘 = 10-08）
- **休市依据**: 三大交易所 2026 中秋国庆休市安排 —— 10-01~10-07 休市，**10-08（周四）起照常开市**。故 10-08 为最新可得收盘日。
- **结论**:
  - ✅ **日线行情够新**：本轮抓的 5199 只 hfq + raw 均到 **2026-10-08**
  - ✅ **季度财务正常**：最新报告期 2026-06-30；2026Q3 法定截止 10-31，实测该期接口尚无数据
  - ⚠️ 刷新后可交易池与市值已到 2026-10-09（见上一条）
  - ❌ **`valuation_daily` 仅 8 只股票**（000933/002215/002532/002582/002611/002648/600000/600595，2018-01-02~2026-08-28）→ **PE_PCTL / PB_PCTL 撑不起**
  - ❌ **`dividends` 仅 26 行 / 1 只股票**（600000）→ **DY 撑不起**
  - ❌ **`daily_bars` 0 行** → 真实回测需先灌库
- **备注**: **「字段最大值很新」不等于「数据本身很新」**——`quarterly_fin.notice_date` 最大值 2026-09-28 看着新，但那是修订日；按报告期看 2026Q2 的实际披露集中在 08-21~08-29。同一坑源与 `notice_date` 不可作 PIT 一事同源。

## [2026-10-09] result | **首次全 A 因子检验**：EP / BP / ROE_TTM / GPM 四因子全部未过闸门

- **操作者**: AI (DSH)｜任务目录 `G:\股市探究\fullA-检验与回测\`
- **原因**: 本项目此前**所有**因子结论都建立在 101 只试点样本上（registry 标记「初步」）。本次把样本升级到全 A，对四个核心因子做首次可裁决检验。
- **样本与口径**（检验前冻结，落 `output/tests/frozen_config.json`）:
  - 样本池 **全 A 5,179 只（含退市股 361 只）**，面板 492,342 行 / 117 个月
  - 期间 2017-01-31 ~ 2026-09-30（116 个月），OOS 最近 24 个月
  - **PIT = 法定披露截止日**（非 notice_date，后者实测是修订日）
  - **TTM = eps(最近已披露财年) + eps(本年累计) − eps(上年同期累计)**
  - **因子分母 = raw 未复权价**（实测裁决：raw 口径 PE 中位 28.7 / PB 2.44 落在真实区间；hfq 口径 PE 372 荒谬）
  - N'=4；registry 锁定符号未作任何改动
- **结果**（全部淘汰）:

  | 因子 | mean IC | ICIR | NW-t | 净多空年化 | 夏普 |
  |---|---|---|---|---|---|
  | BP | 0.0519 | 0.322 | 3.47 | **5.7%** | 0.30 |
  | EP | 0.0411 | 0.282 | 3.04 | **4.6%** | 0.33 |
  | ROE_TTM | 0.0166 | 0.123 | 1.32 | 2.9% | 0.22 |
  | GPM | 0.0054 | 0.059 | 0.63 | 0.8% | 0.09 |

- **影响**:
  - `docs/factor_docs/factor_registry.md` 追加「全 A 检验回填」节（A1-A4 行）+ 变更日志行；**原 26 行登记表逐字未动**（追加式，符合 v3 §9/§12）
  - 结论汇总：`fullA-检验与回测/output/全A因子检验结论-20261009.md`
  - 四份完整报告 + 回填行：`output/tests/`
- **备注**: 三条最值钱的事实 ——
  ① **试点量级不可外推**：EP 在全 A 的 IC（0.0411）是 101 只试点（0.0108）的 **3.8 倍**，而 BP 略降（0.0519 vs 0.0672）。**方向不一 → 小样本既不能低估也不能高估，只能标「初步」。** 这是对 registry 里「T<60 月降级初步」纪律的实证支持。
  ② **「单因子未过线」≠「该因子无用」**：EP/BP 净多空年化 4.6%/5.7% 是**真实经济信号**，只是未达本项目自设门槛（ICIR>0.5、NW-t≥3.0 等）。且 ROE_TTM/GPM 在设计上属**质量门槛层（一票否决）**，门槛有效性不能用 IC 关裁决——本次只证明它们不适合当独立打分因子。
  ③ **GPM 是「几乎完美的不显著」**（IC 0.0054 / PT MR p=0.8291），如实报告，未做选择性汇报。
- **本次检验的限制（与结论同时生效，已写入 registry）**: 生存者偏差敞口 6~12%（面板覆盖 87.7%(2017)~94.1%(2025) 上市数）｜未做行业中性化（无申万一级列）｜LEV / CFO_NI_TTM 因数据缺失未能检验。

## [2026-10-09] new | **期货保证金与强平机制**入库（郑商所实证，跨出 A 股领域）

- **操作者**: AI (DSH)｜任务目录 `G:\股市探究\郑商所杯-50万模拟\`
- **原因**: 用户提出「郑商所期货交易，50万模拟资金」，确认是第九届「郑商所杯」模拟盘。
  产出作战方案过程中得到一批**机制性**（而非行情性）结论，与 A 股侧既有页面形成对照，值得沉淀。
- **新增页面**: `concepts/risk-management/futures-margin-and-liquidation.md`（index 已登记，总数 63→64）
- **核心内容（四条，均可由 code/czce_calc.py 复算）**:
  1. **强平距离与开仓手数无关** —— 手数在强平不等式两边同比例出现被约掉，
     故"少开手"不让你更安全地扛，只等比例缩小盈亏。仓位控制解决"亏多少"，止损解决"会不会死"。
  2. **手续费结构与 A 股相反，且大头是滑点** —— 期货无"每笔最低 5 元"下限，
     日内往返 1.50~22.50 元/手；但含滑点后全成本 0.025%~0.265% 名义，**滑点占 76.9%**。
     通行说法"日内成本是隔夜一半"**只在 10/21 个品种成立**，AP 苹果日内反而翻倍更贵。
  3. **单位错误是静默杀手** —— 郑商所手续费字段有"绝对值(元/手)"与"比例值(万分之X)"两种计费方式，
     把后者当前者用会**低估成本 2.0~13.1 倍**（PR 瓶片 13.1 倍）。此类错误不报错只算错。
  4. **"每笔风险 X%"不能直接当组合规则** —— 该规则隐含"同时只持 1~2 个品种"；
     实测信号平均同持 18 个品种时，标称 1% 实为**组合层 14.68% 风险**，需 3,772% 权益保证金。
     解法是限制同时持仓品种数（限到 4~5 个后 R=3% 的占用仅 6.1%~6.5%）。
- **与既有页面的关系**:
  - 与 [[small-account-minimum-commission]] 构成**对照**：A 股侧是"最低佣金支配策略形态"，
    期货侧是"保证金机制支配生存"。两者共同点是**成本/资金约束的量级足以让策略类别不可行**。
  - 第 4 条与 [[dual-caliber-adjustment]] 同源（口径冲突时的裁决方法）：
    冲突时不要挑"更保守"的那个，要查清两个数字各自的口径定义 + 业务规则原文。
- **影响**: 仅新增 1 页 + index 登记；未改动既有页面结论。
- **备注（三条复盘点）**:
  ① 本次最值钱的产出全部来自**冲突**而非"一致确认"：高校转发通知的日期互相矛盾、
     两个数据源对同一保证金率给出 7% vs 14.6%、费率单位歧义、回测里一个"数学上永不成交"的
     突破条件。**只收一致确认的话，这四处错误一个都发现不了。**
  ② 回测的诚实结论：walk-forward 样本外年化 +2.54%/夏普 0.22/去偏夏普 0.156/bootstrap p=0.867，
     **无任何策略通过显著性检验**；均线夏普 0.54 需 2,328 个交易日（9.2 年）才能确认，
     而比赛只剩 38 个交易日。**样本外最好的"策略"是等权买入持有，打败了全部择时策略。**
     —— 这是对 [[overfitting-prevention]] 的一次实战印证：认真做防过拟合，业绩一定会变难看。
  ③ 本次复核了「交易所保证金率 ≠ 实收保证金率」：期货公司加收可达 3.12 倍（RS）。
     教训：**两个数据源冲突时，先查口径定义，别靠"哪个更保守"来选**。
