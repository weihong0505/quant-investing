---
title: A股数据源实测结论（2026-08）：东财限流模式 / qfq负价实弹 / 腾讯hfq缺陷 / 新浪raw可用
source_url: 项目实测记录（docs/SOP.md §1.4 + factor_docs 审查报告 V 表 + factor_docs/_*.py/_*.json 验证产物）
ingested: 2026-08-22
sha256: f650657613448805（SOP.md §1.4 数据源策略，2026-08-20 实测）；验证明细见 factor_docs/_sina_crosscheck.json、_tx_crosscheck.json
tags: [data-source, backtest, decision, market-event]
---

# 摄入：A股数据源实测结论（2026-08）

> 来源：项目 2026-08-20~22 多轮实测（akshare 1.18.x，三源对照 + 复权对账 + 限流压测）。
> 完整验证脚本：`docs/factor_docs/_*.py`；审查报告 V 表见 raw/papers/ 两个摄入页。
> 本页为提炼层；与 SOP §1.4 冲突时以 SOP 为准。

## 一、东财：限流模式（实测）

- `stock_zh_a_spot_em`（全市场快照，70 页分页）：⚠️ 易限流——被限后 `RemoteDisconnected`，冷却 **10+ 分钟**；`stock_zh_a_hist`（个股历史）连续 45+ 请求触发冷却，**20 分钟以上**不恢复。
- **2026-08-21/22 升级为持续封禁**：push2.eastmoney.com 裸 GET 首请求即 `RemoteDisconnected`（baidu 同机直连 200，排除代理/DNS/网络），跨两轮审查 ≥24h 未恢复——属持续性封禁而非短期限流。12 分钟重试仍断。
- 东财 datacenter-web 域（非 push2）**未被封**：`stock_yjbb_em`（业绩报表）回溯 2016Q1、`stock_zcfz_em`（资产负债表）回溯 2019Q1+、`stock_fhps_em(date=)` 批量分红送转表可用。
- **限流应对（已入 SOP §1.4）**：全量数据落 parquet 缓存；调用间 sleep ≥0.5s；失败重试 2s/4s/6s 退避；被限时跳过行情用缓存；"探测—执行"后台模式（每 2 分钟单日小请求探测，恢复后跑批，最多 12 探）。

## 二、qfq：负价实弹（实测，禁用依据）

- **东财与腾讯的 qfq 均出现负价格**：600036（招商银行）qfq 2014-2016 段出现 **−1.67 元**等负价；两源 qfq/hfq 日收益相关均仅 ~0.046（几乎一致——同款逆向锚定算法）。
- 负价收益是垃圾数据，污染一切动量/收益计算 → 全系统**禁用 qfq**（backtest_engineering_spec v2.1 铁律）。
- qfq 另有**历史漂移**定义性缺陷：qfq[t]=raw×F_t/F_now 依赖最新日因子，每次新除权全量改写历史（每股派 1 元 → 历史改写 ~2.3%；一年两次分红 → 4~5%/年），破坏快照 hash 可复现。

## 三、腾讯：hfq 高波动日缺陷（实测，2026-08-22）

- `stock_zh_a_hist_tx` / fqkline hfq 在**极端行情日被系统性压低**：
  - 601318 2024-09-30 涨停日：hfq +7.4% vs 实际 +10.0%；
  - 600000 2024-09-24：hfq +7.1% vs +9.0%；
  - 与新浪 hfq/raw 均不符 → **腾讯 hfq 不得用于收益/动量计算**。
- 腾讯 **raw 与新浪 raw 完全一致**（ret_corr=1.0, maxdiff=0.0）→ 可作 raw 主源。
- 腾讯 fqkline 直连（`web.ifzq.gtimg.cn/appstock/app/fqkline/get`）：纯 JSON 线程安全、~0.3s/请求、8 线程 ~4 req/s；count≤800；连发会被 ConnectionReset → 0.25s 节流+退避。
- **腾讯有退市股历史行情**（600401/000693 到最后交易日 2019-07-08）——新浪无（0 行），东财待确认。退市股行情唯一可得路径。

## 四、新浪：raw 可用（实测，复权抽查源）

- `stock_zh_a_daily`（新浪）复权实现**数学严格正确**：qfq/hfq 日收益 corr 0.99975、最大差 0.17%（纯舍入）→ 可作 hfq 交叉抽查源。
- 新浪 raw 与腾讯 raw 一致（见上）→ raw 兜底源。
- 缺陷：`stock_zh_a_spot()` 无 PE/PB 列（仅价格兜底）；klc_kl.js 已加密混淆（base64 blob 需 py_mini_racer 解码）；akshare `stock_zh_a_daily` **多线程并发会崩解释器**（mini_racer 线程不安全）；getKLineData JSONP 仅 raw 且最多 1023 交易日。

## 五、跨源规则（实测结论）

- **跨源复权因子不可混用**：同股 hfq/raw 累积因子东财 5.47 vs 新浪 6.74——日收益均正确、水平值不可比；跨源只校验不拼接。
- 复权口径裁决：全系统统一 **hfq**（总收益口径，分红再投已对账 ±0.03pp）；市值/价格水平/绝对金额信号一律 **raw**（价格水平横截面 Spearman 实测仅 0.37，收益类 1.0000）。
- 指数基准：新浪 `stock_zh_index_daily` 为价格指数（不含分红，作基准低估 ~1.5~2.5%/年）；全收益代理用 510300/510500 ETF hfq（腾讯/东财可得，新浪 ETF 复权不支持）。

## 六、接口可用性备忘

- ✅ `stock_fhps_detail_em(symbol=)` 分红明细（除权除息日/每股派息）
- ⚠️ `stock_tfp_em` date 参数疑似不生效 → 停牌判定用"交易日历 vs 行情行缺失"推断
- ❌ `stock_ipo_benefit_em` 不存在；baostock 本网络不可用（单股查询 >4min 无响应）

## 相关页面

- [[backtest-engineering-spec-v2-review]] — V 表实测细节
- [[akshare]] — 主数据源实体页
- [[dual-caliber-adjustment]] — hfq/raw 双口径铁律
