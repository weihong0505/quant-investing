# C3 — px_hfq 零使用：hfq 收益层铁律未落地，净值全按 raw 价计算
> ✅ 已验收 2026-08-22 操作者: AI-C3

> 来源：项目复盘 2026-08-22 第 C3 项（Wiki 全文：G:\quant-investing\wiki\comparisons\project-review-2026-08.md）
> 严重度：🔴 阻断　|　任务性质：代码修复（核心口径）　|　涉及文件：code/backtest.py、docs/factor_docs/backtest_engineering_spec_v2.1.md、wiki/entities/system/backtest-engine.md
> 依赖：无（但需与 C4 一起改，避免二次冲突）　|　建议优先级：第四批

## 1. 问题现状

回测引擎 docstring 与 Wiki 都宣称实现了"双口径铁律：信号/收益层 hfq（含分红再投），执行/估值/成本层 raw"。实际上 **hfq 数据从未参与任何计算**：净值 = raw 收盘价 × 股数 + 现金，月收益 = raw 净值 pct_change。

## 2. 证据

- `grep -n 'px_hfq\|prices_hfq\|hfq' code/backtest.py` 实锤：`px_hfq` 只出现在 docstring（L9）、参数文档（L213）、构造函数（L222/236）、`_validate`（L247）——**run() 主循环零使用**
- `run()` 估值：`nav_records[m_end] = cash + self._positions_value(m_end, positions)`；`_positions_value` 用 `self.px_close.at[date, code]`（raw 收盘价）
- `monthly = nav.pct_change()`——收益直接来自 raw 净值差分
- 规范依据 `backtest_engineering_spec_v2.1.md` L114："信号/收益层：hfq；执行/估值/成本层：raw"
- `wiki/entities/system/backtest-engine.md`："双口径铁律 - 信号/收益层：hfq（总收益口径，含分红再投）"——标注为已实现能力

## 3. 为什么是错

1. **分红收益丢失**：不传 cash_div 时，除息日股价跳水直接打进 raw 净值——月收益序列被除息日污染，长期净值系统性低估（A 股平均股息率 ~2%/年）
2. **口径不统一**：传了 cash_div 则红利以现金形式趴账（0 收益），也不是 hfq 的红利再投口径——和规范要求的口径对不上，两种行为都不符合 v2.1
3. 引擎自己的 docstring 承认"不提供则分红缺失，报告声明"——规范要求的收益层在实现中被静默替换成了 raw 层，且没有在运行时给出任何声明
4. Wiki 把未实现的能力标注为"已实现"——错误知识在库里传播（W2）

## 4. 修改要求（方案二选一，禁止文档代码两张皮）

**方案 A（推荐，符合 v2.1 原文）——真正实现 hfq 收益层：**
- 组合月收益不用 raw 净值差分，改为**持仓权重 × hfq 日收益**合成（关键实现细节，易做错）：
  - ⚠️ **hfq 价格水平跨股不可比**（复权因子是单股常数，各股不同）——绝不能直接 `Σ shares × hfq_price` 算组合净值；必须用**日收益加权合成**：`ret_t = Σ w_{i,t-1} × (hfq_{i,t}/hfq_{i,t-1} − 1)`，w 用 t-1 日持仓市值权重
  - 现金按 0 收益计入权重；买入/卖出日按执行价对应的 raw→hfq 换算调整
- 执行层（成交价、股数、整手、税费、涨跌停判定）保持 raw 空间不变
- Performance 的年化/波动/夏普/回撤全部基于合成的 hfq 总收益序列；raw 净值仅作交易对账用
- 新增金样本用例：合成一只除息股票（除息日 raw 跌 2%、hfq 平），验证组合月收益不因除息产生跳变

**方案 B——改口径声明（不推荐，除非用户明确选择）：**
- 若坚持"raw 价 + 现金分红入账"的会计口径：必须在 v2.1 规范与 Wiki backtest-engine 页同步改写"收益层"条款，注明与 hfq 红利再投口径的偏差量级（红利现金拖累 ~0-2%/年×现金占比），并在每份回测报告显著位置声明

## 5. 验收标准

- [x] 金样本 25/25 全部保持 PASS（改后重跑 `test_golden_samples.py`）
- [x] 新增除息日分红再投对账用例（合成数据手算）通过
- [x] 月收益序列中除息日无异常跳变（合成测试验证）
- [x] `grep px_hfq` 显示该数据在收益计算路径中被实际使用（方案 A）
- [x] 规范 v2.1 与 Wiki backtest-engine 页与实际实现口径完全一致（方案 A：无需改文档；方案 B：文档已同步改写+偏差声明）

## 6. 修改后需同步的文档

- docs/factor_docs/backtest_engineering_spec_v2.1.md（仅方案 B 需要）
- wiki/entities/system/backtest-engine.md（按最终口径改写"双口径铁律"一节）
- wiki/concepts/risk-management/dual-caliber-adjustment.md（同步）
