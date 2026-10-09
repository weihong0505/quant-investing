# Wiki Index — A股量化价值投资知识库

> 内容目录。所有 Wiki 页面按类型分组，每条一行：wikilink + 一句话摘要。
> 首次读此文件可快速定位相关页面。
> Last updated: 2026-10-09 | Total pages: 64

---

## Entities — System

- [[multi-factor-v2]] — 价值投资决策系统 v3（v2.1 设计定稿 2026-08-25：四层管线+安全边际分+集中持仓12只季度调仓；旧 v2 保留对照）
- [[akshare]] — 主数据源，A股行情+财务数据，需处理代理和限流
- [[mimo-review]] — MImo V2.5 Pro 因子审查流程，新因子上线必经关卡
- [[sop-v1.1]] — 量化投资标准操作流程文档（当前 v1.4），踩坑记录的唯一事实源
- [[backtest-engine]] — 自研回测引擎（真实成本+T+1+涨跌停+公司行为），金样本对账验证（合成数据手算，仅验证算术正确性，非策略验证）；真实数据回测未执行（见复盘 S2）
- [[factor-testing-methodology]] — 因子检验方法论 v3（MImo 两轮审查定稿）：IC/分层/经济闸门判定线
- [[backtest-engineering-spec]] — 回测工程规范 v2.1（定稿）：hfq 复权/双口径/样本分层/策略判定 7 条
- [[sell-signals]] — 卖出信号模块：时间止盈+信号衰减+止损+冷却期
- [[ic-monitor]] — 因子 IC 月度跟踪与衰减预警（滚动 36m 观察线）
- [[walk-forward]] — 滚动窗口统计（非 walk-forward）+ 一次确认制（防过拟合）
- [[regime-weights]] — Regime 动态调权（设计稿 P2，待 MImo 审批）
- [[quant-db]] — 本地股票数据库 quant.db：管道已建、内容残缺（估值/分红/FCF 未全量；daily_bars 空）
- [[screening-pipeline]] — 初筛管线 v1.0：五道过滤（ST/基础/市值/PE·PB 分位严格 AND）；演示级、0 候选可为纪律结果
- [[small-account-execution]] — **小额账户执行框架（1800 元实盘）**：整手/佣金下限/板块权限三重硬约束 / 三个可复算工具 / 止损止盈按波动分档 / 五条自我纠错（交易日历、指数≠市场状态、加息周期、NAV≠成交价、上证红利≠中证红利）

## Entities — Market Events

<!-- 待积累 -->

## Entities — Stocks

<!-- 待积累：纳入重点跟踪的个股 -->

## Entities — Sectors

<!-- 待积累：重点行业板块 -->

## Entities — Tools

- [[file-organizer]] — 文件整理代理：按 FILE-MANAGEMENT-STANDARD.md 自动归类
- [[local-ai]] — 本地AI配置与实测：Ollama + Qwen2.5 选型 / **NPU（Intel AI Boost）能力边界** / **Jev 决策模型 NPU 混合推理与常驻端点**
- [[qlora-local-finetuning-methodology]] — 本地 QLoRA 微调 7B 实践方法论：8GB 显存环境选型 / 四个训练卡点（含 optimizer 序列化挂起）/ curl 分片下载校验 / **GPU 疑难杂症七步排查法**（含张量核慢 3× 未解案）
- [[ai-toolchain-notes]] — AI 协作工具链经验：pwsh 传参编码 / 工具无法写盘符根 / 行尾不一致 / Ollama OpenAI 端点丢 tools（**2026-09-21 已更正为不复现**，但部分模型仍不产生工具调用）（规则本体见 [[sop-v1.1]]）
- [[dsh-plugin-internals]] — DSH 插件内部机制与坑：Host/Client 重载差异 / **常驻子代理会唤醒父代理** / 工具过滤方向 / 会话日志是多帧 zstd / 两个静默给错结果的坑
- [[dsh-tool-presentation-modes]] — DSH 工具呈现模式与 PTC 决策：native/ptc/both 的**实测成本曲线**（2.8K–581 KB，PTC 省 1.39–3.53×）/ 恒定输入 token / 任务措辞模板 / 反模式清单
- [[agent-teams]] — DSH Agent Teams 能力与《AI 通用准则》对标：强制力四档 / 反向加压三处（§12 时间传不进 fresh 成员、审查必须用 fresh、隐私落盘面翻倍）/ 机制不管的四件事（writeScope 非锁、owner 不自动释放等）
- [[doubao-image-generation]] — 豆包 Seedream 生图接入 DSH：**两台互不相通的接口面**（用错面报 401，与 key 抄错同码）/ 三条互不干扰的路径（对话工具、`/draw`、面板回环通道）/ 命令名禁中文且失败连坐 / 自检要验「可用」非「存在」/ 用附件入库与否事后判定路径归属

## Concepts — Factors

- [[ep-factor]] — 盈利收益率因子（1/PE），价值投资核心指标
- [[bp-factor]] — 账面价值比因子（1/PB），资产估值指标
- [[roe-ttm]] — 滚动ROE因子，盈利能力质量指标
- [[gpm-factor]] — 毛利率因子，产品竞争力指标
- [[cfo-ni-ttm]] — 经营现金流/净利润因子，盈利质量指标
- [[lev-factor]] — 资产负债率因子，财务杠杆指标
- [[momentum-60d]] — 60日动量因子；原方向已淘汰（#13，试点反向显著），反转方向待检（#12）
- [[turnover-factor]] — 换手率因子，流动性偏好指标
- [[log-mcap]] — 对数市值因子，小盘溢价指标
- [[vol-ratio]] — 量比因子，短期情绪指标
- [[pe-pctl]] — 市盈率历史分位因子（滚动窗口），v2.1 新增，⏳ 待检验
- [[pb-pctl]] — 市净率历史分位因子，v2.1 新增，⏳ 待检验
- [[dy-factor]] — 股息率因子，v2.1 新增，⏳ 待检验
- [[fcf-yield]] — 自由现金流收益率因子，v2.1 新增，⏳ 待检验

## Concepts — Strategies

- [[weighted-scoring]] — 加权评分策略：z-score × 方向 × 权重的合成逻辑
- [[industry-neutralization]] — 行业中性化：消除行业偏差的质量因子处理

## Concepts — Risk Management

- [[factor-decay]] — 因子衰减：因子有效性随时间下降的现象与检测方法
- [[backtest-cost-model]] — 回测成本模型（§7A）：佣金/印花税时变/滑点四档/成本敏感性三档
- [[dual-caliber-adjustment]] — 复权双口径铁律：hfq 统一 + raw 空间执行
- [[overfitting-prevention]] — 防过拟合方法论总览：样本外纪律/交叉验证/正则化/早停/集成/walk-forward/去偏夏普
- [[small-account-minimum-commission]] — 小额账户最低佣金支配效应：**每笔不足5元按5元（ETF 同样适用）** / 频率→年度拖累表（月频 = 白送 6.94% 本金）/ 保本涨幅口径对比 / 三条推论
- [[futures-margin-and-liquidation]] — **期货保证金与强平机制（郑商所实证）**：强平距离与开仓手数无关（可推导）/ 手续费无"最低5元"下限但滑点占全成本 76.9% / 费率"元每手 vs 万分比"单位错误低估 13 倍 / "每笔1%风险"当组合规则用实为组合层 14.7% 风险

## Concepts — Regime

- [[2017-style-shift]] — 2017 风格切换：白马蓝筹行情、小盘溢价终结（回测参考段 2017-2018 依据）
- [[2021-bubble-burst]] — 2021 抱团瓦解：核心资产泡沫破裂（回测核心段 2021-02 起点、观察线结构断点）
- [[2024-microcap-crisis]] — 2024 微盘危机：微盘流动性踩踏与 924 行情（观察线结构断点、动量尾部风险）
- [[market-state-identification]] — 市场状态识别：三结构断点 + 回测分层锚点 + 36m ICIR 调权（唯一量化机制，增量价值未实测，confidence low）

## Comparisons

- [[factor-direction-map]] — 10个因子的方向定义与权重一览
- [[project-review-2026-08]] — 项目复盘诊断：错误清单（S/C/W/M 四层 22 项）+ 证据链 + 改正方向 10 条

## Raw — 原始资料（摄入层）

- [[backtest-engineering-spec-v2-review]] — 回测工程规范 v1/v2 两轮审查报告核心结论（raw/papers，2026-08-22 摄入）
- [[factor-testing-methodology-review]] — 因子检验方法论 v1/v2 两轮审查报告核心结论（raw/papers，2026-08-22 摄入）
- [[quality-factors-v2-review]] — 质量因子组设计方案 v2 审查结论：4 质量因子定稿/每股口径/金融中性化/z-score 加权（raw/papers，2026-08-22 摄入）
- [[regime-weights-review-20260822]] — regime 动态调权设计审查（SOP §3.0 有条件通过）：36m ICIR 相对强弱排序、±50% 上限、增量价值待实测（raw/papers，2026-08-22 摄入）
- [[sharpe-ratio-efficient-frontier-2012]] — PSR 原始论文：非正态收益下夏普阈值概率 + 最小 track record 长度 + SEF（raw/papers，2026-09-11 摄入）
- [[deflated-sharpe-ratio-2014]] — DSR 原始论文：多重检验选择偏差校正、期望最大夏普 SR₀（raw/papers，2026-09-11 摄入）
- [[data-source-testing-2026-08]] — A股数据源实测结论：东财限流模式 / qfq负价实弹 / 腾讯hfq缺陷 / 新浪raw可用（raw/articles，2026-08-22 摄入）
- [[gpm-caliber-verify-2026-08]] — GPM 口径实测：yjbb「销售毛利率」= 报告期累计口径（40/40），横向不可比 → 改 TTM 建议（raw/articles，2026-08-22 摄入）
- [[mom60-caliber-and-test-2026-08]] — MOM_60D 复权口径实测（qfq/hfq 恒等、raw 低估高股息动量）+ v3 检验淘汰：反向显著 signed NW-t −3.63（raw/articles，2026-08-22 摄入）

- [[mom60d-v3-test-20260822]] — MOM_60D v3 全流程检验：signed NW-t=-3.63 反向显著，淘汰（初步样本）

- [[volratio-v3-test-20260822]] — VOL_RATIO v3 全流程检验：不显著，淘汰

- [[value-vs-momentum-fm-20260822]] — 价值×动量 FM 增量检验裁决：MOM 无独立增量，建议砍权重待拍板

## Queries

<!-- 待积累：归档的回测结果和查询分析 -->
- [[s1-pilot-factor-tests-20260822]] — S1 试点因子检验输出：MOM_60D 反向显著淘汰（signed NW-t −3.63）/ VOL_RATIO 淘汰（2026-08-22，样本<60月结论初步）
- [[golden-samples-103-pass-20260822]] — 回测引擎金样本对账输出：103 PASS / 0 FAIL（合成数据，仅验证算术正确性）

- [[因子月度检验报告]] — 由本地AI自动生成（2026-08-22），来源: concepts/因子月度检验报告.md
- [[2026年三季度策略展望]] — 由本地AI自动生成（2026-08-22），来源: concepts/2026年三季度策略展望.md
- [[银行业投资分析]] — 由本地AI自动生成（2026-08-22），来源: concepts/银行业投资分析.md
