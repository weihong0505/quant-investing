# 价值投资转型 P2+P2.5 验收报告

> 日期：2026-08-25
> 执行：AI 子代理（deleg_7abcd825）+ 父级复核
> 定稿依据：value_investing_transition_v2.1.md §5/§7

## 交付物

### 1. `code/value_investing.py`（新建，44KB，约900行）
价值投资主策略全链路（函数式）：
- `filter_universe(spot_df)` — 可交易性过滤（市值≥30亿/换手0.1%~20%/非ST/上市≥5年）
- `quality_gate(spot_df, financials_df)` — 质量门槛一票否决（ROE/GPM/CFO/LEV/EPS；周期8行业豁免；金融股豁免规则）
- `build_valuation_factors(...)` — 6因子构建（PE_PCTL/PB_PCTL滚动窗口分位+EP_z/BP_z申万行业内+DY/FCF_YIELD）
- `safety_margin_score(factor_df)` — 安全边际分（0.30/0.30/0.15/0.15/0.05/0.05，主观先验W-编号）
- `build_portfolio(scored_df, top_n=12, ...)` — 组合构建（等权/行业≤30%/个股≤10%）
- `generate_signals(portfolio, prev_positions, sell_codes, ...)` — 信号生成（**完整持仓快照语义**：卖出行含全部持仓，未动股权重保留；调仓日合并单行）
- `run_value_pipeline(top_n=12, experimental=False)` — 主入口（fail-closed生产开关）

### 2. `code/multi_factor_value.py` 权重归零（P2-B）
- MOM_60D 已从 WEIGHTS/DIRECTION 删除（docstring 注明 #13/#17 淘汰原因）
- 8因子重归一化：EP 0.235/BP 0.235/ROE_TTM 0.141/GPM 0.071/CFO_NI_TTM 0.059/LEV 0.024/TURNOVER 0.176/LOG_MCAP 0.059（**和=1.000**）
- 动态共线性闸门冻结声明（对照基线权重快照固定，P2-A）

### 3. `code/run.py` 生产开关（P2.5）
- 默认 mode=VALUE experimental=False → **拒绝运行**并提示 --experimental
- `--experimental` 允许运行且强制标注"实验性权重，未经统计检验，禁止实盘"
- `--legacy` 保留旧系统入口

## 验收结果（55/55 PASS）

| # | 验收项 | 结果 |
|---|--------|------|
| 1 | value_investing 全函数 import | ✅ |
| 2 | 合成数据管线全链路（过滤→门槛→因子→打分→组合） | ✅ 含空池守卫 |
| 3 | experimental=False fail-closed 拒绝 | ✅ |
| 4 | 事件驱动卖出行=完整持仓快照（3只卖1只，余2只保留原权重） | ✅ |
| 5 | MOM_60D归零后 8因子权重和=1.000 | ✅ 实测1.000000 |
| 6 | 旧接口不破坏（run_full_pipeline import+签名不变） | ✅ |

## 父级复核补充验证
- 卖出快照语义实测：`generate_signals(portfolio, prev_positions={'600000':0.4,'600519':0.3,'000001':0.3}, sell_codes=['600000'])` → 输出行含全部3只（600000=0，其余保留）✅
- 8因子权重和 = 1.0 ✅
- 全量 import 9模块 ✅

## 顺带修复（P1发现的既有缺陷）
- `data_fetcher.get_delisted_stocks()`：akshare 新版 `stock_info_sh_delist/sz_delist` 参数 `indicator=` → `symbol=`，已修复并实测：沪159 + 深208 = **367家退市股**（清旧缓存后验证）

## 遗留
- P4 统计检验（4新因子，依赖真实数据恢复）
- P5 真实回测（新旧对照，依赖P4）
- registry #18-21 状态待P4回填
