# 价值投资转型 P1 数据层交付报告

> 日期：2026-08-25
> 模块：data_fetcher.py 新增 4 接口 + 口径验证
> 关联设计：value_investing_transition_v2.1.md §4 数据需求 / §5 代码改造
> 验证脚本：`_p1_verify.py` / `_p1_verify2.py`（本目录）

## 1. 交付接口（全部追加，未改动既有接口）

| 接口 | 数据源 | 返回列 | 缓存文件 | 关键行为 |
|------|--------|--------|----------|----------|
| `get_valuation_history(code, start=None, end=None)` | 东财 datacenter `RPT_VALUEANALYSIS_DET`（push2 被封不影响） | `date, pe_ttm, pe_lar, pb_mrq, total_mcap, close, total_shares` | `data_cache/valhist_{code}.parquet`（全量，断点复用） | 日期过滤在缓存后；退市股/无数据返回空 DataFrame 不抛错 |
| `get_fcf(code, quarters=None)` | 东财 datacenter `RPT_DMSK_FN_CASHFLOW` | `report_date, notice_date, netcash_operate, construct_long_asset, fcf` | `data_cache/fcf_{code}.parquet`（全量） | 按 REPORT_DATE 升序；`fcf = netcash_operate - construct_long_asset`；quarters=N 取最近 N 期 |
| `get_dividends(code)` | ak.stock_fhps_detail_em | `report_date, ex_date, cash_div_per10, progress` | `data_cache/div_{code}.parquet` | 仅保留方案进度="实施分配"；cash_div_per10=每10股含税（元） |
| `get_industry_map(source='eastmoney')` | spot 缓存→实时 spot_em→yjbb 缓存兜底 | Dict[行业名, 申万一级名]（未映射为 None） | — | 硬编码映射表 `_EM_TO_SW1`（东财）＋`_SW2_TO_SW1`（申万二级兜底）；打印覆盖率 |

## 2. 实测结果（600000 浦发银行 为主样本）

### 2.1 get_valuation_history('600000') ✅
- 行数 **2097**（≥2000 ✓），最早日期 **2018-01-02**（验收 ±1月 ✓），最晚 2026-08-24
- pe_ttm 非空 **2097/2097**（100%）；pb_mrq 非空 2097/2097
- 单位核对：total_mcap=3.734e11 元 = close 12.72元 × total_shares 2.935e10 股 ✓（元/股/元 口径一致，不复权）
- 日期过滤实测：start=2024-01-01, end=2024-12-31 → 242 行，范围 2024-01-02~2024-12-31 ✓

### 2.2 get_valuation_history 退市股（300104 乐视网）✅
- 返回空 DataFrame（0 行，7 列齐全），无异常抛出 ✓（接口返回"返回数据为空"，已捕获）

### 2.3 get_fcf('600000') ✅
- 行数 **101**（≥90 ✓），范围 1998-12-31 ~ 2026-03-31，fcf 非空 101/101
- 按 report_date 严格升序 ✓；quarters=8 → 返回 2024-06-30~2026-03-31 共 8 期 ✓
- fcf 计算核对：fcf = netcash_operate − construct_long_asset（首行 10.228亿 − 2.787亿 = 7.441亿 ✓）
- notice_date 末 3 期：2025-10-31 / 2026-03-31 / 2026-04-30（季度报披露日，口径为修订日）

### 2.4 get_dividends('600000') ✅
- 行数 **26**（≥20 ✓），范围 1999-12-31 ~ 2025-12-31，progress 唯一值 = ["实施分配"] ✓
- ex_date（除权除息日）非空 26/26，末 3 期：2024-07-18 / 2025-07-16 / 2026-07-16
- cash_div_per10 示例：1.5 / 2.0 / 1.0（每10股含税元）

### 2.5 get_industry_map() ✅ 覆盖率 100%
- ⚠️ 数据源说明：`spot_20260822.parquet` 为**新浪降级源**缓存（无"所处行业"列）；实时 spot_em 当日被东财限流（RemoteDisconnected，两次重试均失败）→ 函数按设计降级到 **yjbb 缓存**（最新报告期 20260630，其"所处行业"为申万二级口径）
- 行业数 124，映射 124，**覆盖率 100.0%**（≥95% ✓），未映射 0；映射到 31 个申万一级全覆盖（sw1_distinct=31）
- 映射表在函数内硬编码并标注口径：`_EM_TO_SW1`（东财行业 ~100 键）＋`_SW2_TO_SW1`（申万 2021 二级 ~120 键）
- **遗留**：东财 spot 解封后需用真实东财行业列表复核覆盖率（数据源优先级已实现：spot 缓存 → 实时 → yjbb 兜底）

### 2.6 yjbb「最新公告日期」= 首次披露日（非修订日）✅ —— 决定 FCF_YIELD PIT 对齐方案

| 股票 | 报告期 | yjbb 最新公告日期 | fhps 业绩披露日期 | fhps 最新公告日期 | 判定 |
|------|--------|------------------|------------------|------------------|------|
| 600000 浦发银行 | 2025-12-31 | 2026-03-31 | 2026-03-31 | 2026-07-10（分红实施公告） | yjbb=首告日 ✓ |
| 000001 平安银行 | 2025-12-31 | 2026-03-21 | 2026-03-21 | 2026-06-05（分红实施公告） | yjbb=首告日 ✓ |
| 600519 贵州茅台 | 2025-12-31 | 2026-04-17 | 2026-04-17 | 2026-06-22 | yjbb=首告日 ✓ |
| 000333 美的集团 | 2025-12-31 | 2026-03-31 | 2026-03-31 | 2026-06-23 | yjbb=首告日 ✓ |
| 000002 万科A | 2025-12-31 | 2026-04-01 | （fhps 无该期：无分红） | — | 年报季合理 ✓ |

- 一季报佐证：5 只股票 2026-03-31 期 yjbb 最新公告日期全部落在 4 月（600000/000333/000002=04-30、000001/600519=04-25），符合一季报 4 月底前法定期限 ✓
- **结论**：yjbb「最新公告日期」= 实际财报披露日（首告日），**不是修订日**。yjbb 系因子 PIT 判定安全，无需 fhps 业绩披露日历校准。
- **对 FCF_YIELD 的影响**：FCF_YIELD 数据源为 `get_fcf`（RPT_DMSK_FN_CASHFLOW），其 `NOTICE_DATE` 为**修订日**（定稿 §4 已确立）→ FCF_YIELD 的 PIT 对齐仍需按定稿要求用 fhps 业绩披露日历校准（首次公告快照固化），yjbb 结论不改变该方案。

## 3. 验收清单

| # | 验收项 | 结果 |
|---|--------|------|
| 1 | 4 接口 import ok（验收命令原样执行） | ✅ 输出 ok |
| 2 | data_fetcher.py 全量 import（10 接口：6 既有 + 4 新增） | ✅ 全部通过 |
| 3 | valhist 600000 ≥2000 行 / pe_ttm 非空 / 最早 2018-01-02±1月 | ✅ 2097 / 100% / 2018-01-02 |
| 4 | valhist 300104 退市股空返回不抛错 | ✅ |
| 5 | fcf ≥90 行 / fcf 有值 / 升序 | ✅ 101 / 101 / 严格升序 |
| 6 | dividends ≥20 行 / 仅"实施分配" | ✅ 26 / 唯一值 |
| 7 | industry_map 覆盖率 ≥95% | ✅ 100%（yjbb 兜底源；东财源待解封复核） |
| 8 | yjbb 公告日结论写入 | ✅ = 首告日，见 §2.6 |
| 9 | data_caliber_audit.md 追加 6 字段行 | ✅ 2026-08-25 |

## 4. 遗留与注意事项

- 东财 spot_em 限流中：行业映射东财口径覆盖率、以及与 spot 总市值并排核对，待解封后补验（函数已实现优先级降级链，无需改代码）
- get_valuation_history 东财 TTM PE 对亏损股的处理未深验（浦发样本全为正）
- 分红为含税名义口径，DY 因子计算时注意红利税与送转股本联动
- 新增缓存文件：`data_cache/valhist_600000.parquet`、`valhist_300104.parquet`（空表未落盘）、`fcf_600000.parquet`、`div_600000.parquet`
- **既有接口回归（2026-08-25 冒烟）**：get_spot_data（新浪降级 5548 只）/get_history（15 行）/get_benchmark（15 行）/get_financials（2 期）/get_full_stock_pool（5548 只）全部正常。
- **⚠️ 既有缺陷（非本次引入）**：`get_delisted_stocks()` 现报 `stock_info_sh_delist() got an unexpected keyword argument 'indicator'`（akshare 新版本移除该参数），返回空表；`get_full_stock_pool` 因此仅含在市股（退市股纳入失效）。按"不动现有接口"约束未修改，建议 P2 修复（改调 `ak.stock_info_sh_delist()` 无参形式）。
