# 因子零检验（S1）数据就绪后完整执行说明 — FACTOR TEST RUNBOOK

> 配套脚本：`code/factor_test_suite.py`（v3 全文流水线）+ `code/pilot_mom60d.py`（试点样例）
> 方法论：`docs/factor_docs/factor_testing_methodology_v3.md`（定稿）
> 状态：基础设施 ✅ 就绪（2026-08-22 自检通过）；10 因子完整检验 ⏳ 待数据层（S2）就绪后执行

---

## 1. 前置登记核对（registry ⓪ 步，已锁定）

### 1.1 预期符号核对（registry L23-32 vs 主策略 code/multi_factor_value.py DIRECTION）

| # | 因子 | 类型 | registry 预期符号 | 主策略 DIRECTION | 一致？ |
|---|------|------|------------------|------------------|--------|
| 1 | EP | 价值 | + | +1 | ✅ |
| 2 | BP | 价值 | + | +1 | ✅ |
| 3 | ROE_TTM | 质量 | + | +1 | ✅ |
| 4 | GPM | 质量 | + | +1 | ✅ |
| 5 | CFO_NI_TTM | 质量 | + | +1 | ✅ |
| 6 | LEV | 质量 | − | −1 | ✅ |
| 7 | MOM_60D | 动量 | + | +1 | ✅ |
| 8 | TURNOVER | 流动性 | − | −1 | ✅ |
| 9 | LOG_MCAP | 规模 | − | −1 | ✅ |
| 10 | VOL_RATIO | 情绪 | + | ⚠️ 已不在 WEIGHTS | ⚠️ 需裁决 |

**⚠️ VOL_RATIO 偏离**：`multi_factor_value.py` L59 注明"VOL_RATIO 已弃用（东财 spot 盘中快照不可复现），权重并入 TURNOVER"，但 registry 仍登记为"⏳ 待检验"。**执行批次前必须先裁决**：a) 若弃用 → registry 状态改为"❌ 弃用（未检验）"，不纳入 N'，批次数 = 9；b) 若恢复 → 以新登记时间戳重新前置登记，纳入 N'。两种路径 N'≤37，显著性线均为 3.0（见 1.2），不影响判定线本身。

### 1.2 N' 口径与 Bonf 阈值（v3 §9 单一规则）

- 公式：`signed NW-t ≥ max(3.0, Bonferroni(N', 单侧 α=0.05))`
- N' 定义：**本自然季度同期受检新因子数**，季度重置；不含已过检存量、不含历史失败者。
  - 10 因子从未受检 → 本季度启动即计入 N'。全部同期开检：**N'=10**；若分批（跨季度）则按各季度实际受检数（如 Q3 检 4 个 → N'=4，Q4 检 6 个 → N'=6）。
- 阈值计算（已与 `ic_monitor.bonf_threshold` 数值核对）：
  - N'=10：norm.ppf(1−0.05/10) = **2.5758** → max(3.0, ·) = **3.0**
  - N'=37 处 z≈3.0009 恰衔接；**N'≤37 阈值恒 3.0**，N'≥38 自动收紧（v3 §9 无缝衔接设计）
- **结论：10 因子批次（无论 N'=9 或 10）显著性线 = 3.0（signed）**。suite 默认 `--n-star 10`，分批时按实际数传入。
- 必须 signed（预登记方向）：|t| 会放行反向强因子（v3 §9 明令禁止）。

### 1.3 防改口三件套（v3 §9，执行中强制）

1. 检验后符号与登记不符 → 该次检验作废，反转方向以新因子号重新登记并计入 N'
2. 检验后调参 → 重新走 ⓪ 步，原记录保留
3. 未前置登记的因子检验结果无效

### 1.4 检验前登记字段（registry 表头 9 列，执行时填写）

登记时间戳、预期符号（已锁定）、样本期（2017-01~检验月末）、数据版本 hash（suite 自动计算 sha256）、检验脚本（`code/factor_test_suite.py`）、调参标记（无）。

---

## 2. 所需数据（S2 数据层输出，全部落 `code/data_cache/`）

| # | 数据 | 格式 | 起点 | 用途 | 状态（2026-08-22） |
|---|------|------|------|------|---------------------|
| 1 | 全 A 日线 **hfq**（收盘/开盘/最高/最低/成交量/成交额） | 每只 parquet 或按月拼接 | **2015-01-01**（2017-01 主判定需 60 日 MOM 窗口 + 120 交易日次新剔除 + T+1 停牌/一字板判定缓冲） | MOM_60D/VOL_RATIO/TURNOVER 因子、月度收益、T+1 可交易性 | ❌ 未拉全（新浪 akshare 可用，试点已实测单只 0.6~6s；腾讯 hfq 兜底） |
| 2 | 全 A 日线 **raw**（收盘价） | 同上 | 2015-01-01 | 总市值 = raw 收盘 × 总股本；EP/BP/LOG_MCAP 用 raw 口径（双复权铁律） | ❌ 未拉全 |
| 3 | 总股本/流通股本序列（或可推算列） | 每期快照 | 2015-01 | 市值、换手率（volume/流通股本） | 可用 volume/turnover 推算流通股本（试点已验证）；总股本需另源或公告股本表 |
| 4 | 逐期 **PIT 财务**：yjbb（业绩报表）+ zcfz（资产负债表），含**公告日期** | 长表，每季一期 | **2016Q4 起**（2017-01 月末需最新已公告值） | EP/BP/ROE_TTM/GPM/CFO_NI_TTM/LEV 逐期 PIT 对齐；行业（新浪行业非申万，FM 回归时注明） | ✅ 接口实测可用（东财 yjbb 2016~2026 各期 OK，已有 2024Q3~2026Q2 缓存）；PIT 逐期拉取未完成 |
| 5 | ETF 基准 510300/510500 hfq 日线 | parquet | 2015-01 | v3 §5-5 vs 基准超额（报告项） | ❌ 未拉（腾讯/新浪均可） |
| 6 | 沪深300/中证500 成分（历史月度） | parquet | 2017-01 | v3 §8 池子稳健性（硬门槛：至少两池成立） | ❌ 未拉（可选，缺失时报告注明跳过） |
| 7 | 退市股名单（sh/sz delist）+ 腾讯源退市股行情 | parquet | — | 幸存者偏差修正（v3 §3-3；akshare 仅现存股，全 A 检验必须纳入退市股） | ❌ 未拉 |
| 8 | ST/*ST 历史标记 | 月度掩码 | 2017-01 | 池过滤（v3 §3-3） | ❌ 需构建（可用日线名称序列推断，或按公告名单） |
| 9 | 交易日历 | parquet | 2015-01 | 停牌/一字板/月末对齐 | ✅ 可由日线并集生成 |

**数据量估算**：~5500 只 × 2（hfq/raw）× ~2750 交易日 ≈ 3000 万行级；parquet 压缩后约 3-6 GB。

---

## 3. 因子构建口径（与主策略一致 + v3 双复权铁律）

| 因子 | 口径 | 复权 | 数据源 |
|------|------|------|--------|
| EP | EPS_TTM / raw 价（或 净利TTM / raw 总市值，二选一固定，registry 备注） | **raw** | 财务 PIT + 日线 |
| BP | 净资产 / raw 总市值（1/PB） | **raw** | 财务 PIT + 日线 |
| ROE_TTM | EPS_TTM / BPS（BPS>0） | — | yjbb PIT（负利润符号保护同主策略） |
| GPM | 销售毛利率 | — | yjbb PIT |
| CFO_NI_TTM | CFPS_TTM / EPS_TTM（EPS>0） | — | yjbb PIT |
| LEV | 资产负债率（取低） | — | zcfz PIT |
| MOM_60D | hfq 收盘 T / 60 交易日前 − 1 | **hfq** | 日线 |
| TURNOVER | 换手率 = 成交量/流通股本（取低） | — | 日线推算 |
| LOG_MCAP | ln(raw 总市值)（取小） | **raw** | 日线×股本 |
| VOL_RATIO | 量比 = T 日成交量/前 5 日均量（若裁决恢复） | — | 日线 |

- 因子暴露 = T 月末最后一个交易日（v3 §2）；财务因子 = 公告日 ≤ T 的最新值（PIT）
- 中性化版本：行业（新浪行业）+ ln_mcap 回归残差（suite 已实现 `neutralized_variant`；正式检验建议换申万一级）
- 池过滤（每月重算）：剔 ST/*ST、上市<120 交易日、T 期停牌、T+1 月停牌≥5 日或一字板≥5 日（suite 支持 tradable/st 掩码输入）

---

## 4. 执行命令

### 4.1 数据层（S2 负责，此处仅列规格）

```bash
# 全 A 日线（新浪首选，腾讯兜底；并发 4~8 线程，请求间隔 ≥0.3s）
# 输出: data_cache/daily/{code}_{hfq|raw}.parquet 或按月 parquet
# 财务 PIT（东财 yjbb/zcfz 每季，含公告日期）
# 输出: data_cache/fin_pit/yjbb_{YYYYMMDD}.parquet, zcfz_{YYYYMMDD}.parquet
# 月度宽表（对齐月末、池过滤、winsorize 由 suite 内部做）
# 输出: data_cache/monthly/factor_{NAME}.parquet, ret.parquet, mcap.parquet,
#       tradable.parquet, st.parquet
```

### 4.2 单因子检验（suite CLI）

```bash
cd /g/quant-investing/code
D:/pyh/python.exe -E factor_test_suite.py run \
  --factor data_cache/monthly/factor_MOM_60D.parquet \
  --ret    data_cache/monthly/ret.parquet \
  --mcap   data_cache/monthly/mcap.parquet \
  --fin    data_cache/fin_pit/merged_pit.parquet \
  --name   MOM_60D --sign 1 --n-star 10 \
  --start  2017-01-31 --oos-months 24 \
  --factor-type 动量 --registry-no 7 --registered-ts 2026-08-22 \
  --out    ../docs/factor_docs
# 产出:
#   docs/factor_docs/test_MOM_60D_{日期}.md   （v3 §13 全 12 节报告）
#   docs/factor_docs/backfill_MOM_60D_{日期}.md （registry 追加式回填行）
```

### 4.3 批次（10 因子）

```bash
# 每因子一条 4.2 命令（sign 按 registry：EP/BP/ROE_TTM/GPM/CFO_NI_TTM/MOM_60D/VOL_RATIO=1，
# LEV/TURNOVER/LOG_MCAP=-1）；n-star 用本季度实际受检数。
# 存量因子同窗 ICIR（内部基准 v3 §4-3）：先跑完 10 个取中位数，再补跑
# --benchmark-icirs 参数重出报告（或手动在报告标注）。
```

---

## 5. 预计耗时

| 阶段 | 耗时估算 | 说明 |
|------|----------|------|
| 全 A 日线 hfq+raw | 单线程 12~24 h；4~8 线程并发 **2~5 h** | 新浪单只 0.6~6s（试点实测）；腾讯 0.3s/640 行分页 |
| 财务 PIT 40 期 | ~1 h | 东财 yjbb/zcfz 各 ~25-50s/期（S2 实测） |
| 退市股 + ETF + 指数成分 | ~1 h | — |
| 月度宽表构建 | ~0.5 h | 5500 只 × 2800 日 pivot |
| 因子检验（10 因子） | **< 1 h** | 每因子 ~2-5 min（PT MR R=9999 主导，suite 已向量化） |
| 报告+回填+审批 | 0.5~1 天（人工） | MImo 审批流程 |

**合计：数据 4~8 h（并发）+ 检验 1 h + 审批，一个工作日可完成 10 因子全检。**

---

## 6. 检验输出与回填流程

1. 每因子一份 `test_{因子}_{日期}.md`（v3 §13：定义/数据/IC/分层/自相关/共线性/FM/稳健性/OOS/多重检验/经济闸门/判定/可复现材料）
2. `backfill_{因子}_{日期}.md` 回填行 → **追加**到 `docs/factor_docs/factor_registry.md` 登记表末尾（**原行不动**，防改口三件套）
3. 结论三档处置（S1 §4-4）：过线→保留；观察线→降权/观察；不过线→移出主策略（更新 `multi_factor_value.py` WEIGHTS/DIRECTION + 权重重归一化 + weight-change 日志 + Wiki factor-direction-map）
4. 每因子报告提交 MImo 审批（v3 §12 ⑩）
5. wiki/log.md 追加 update 记录

---

## 7. 已知限制与降级条款（执行时如实声明）

- 样本 <60 月 → 结论自动降级"初步"，不得据此入主策略（v3 §1）——2017-01 起约 116 月，满足正式样本
- 东财被封时降级新浪/腾讯源（跨源只校验不拼接）；财务接口（东财 yjbb/zcfz）实测可用不受影响
- 新浪源无退市股 → 必须用腾讯源退市股补齐，否则幸存者偏差声明生效
- 规模中性大市值层每格 <50 只 → 该层结论降级（suite 自动告警）
- PT MR 噪声场景（10 分组/行业分组 σ_idio≥1%/月）功效不足 → 不作硬门槛，改用倒挂计数 + FM β（v3 §5-4）

---

## 8. 试点验证记录（2026-08-22）

- `code/factor_test_suite.py` 合成数据自检：VALID→保留 / NOISE→淘汰 / REVERSE→淘汰（全部断言通过）
- 真实数据试点：`code/pilot_mom60d.py` 对 MOM_60D / VOL_RATIO 执行（新浪 hfq+raw，120 只，2023-02~2026-07，结论"初步"）
  - 报告：`docs/factor_docs/test_MOM_60D_20260822.md`、`test_VOL_RATIO_20260822.md`
  - 回填行：`docs/factor_docs/backfill_*_20260822.md`
