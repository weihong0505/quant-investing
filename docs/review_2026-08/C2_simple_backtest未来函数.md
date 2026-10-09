# C2 — simple_backtest：未来函数 + qfq 违规 + 无成本无基准，且是管线里唯一的"回测"

> 来源：项目复盘 2026-08-22 第 C2 项（Wiki 全文：G:\quant-investing\wiki\comparisons\project-review-2026-08.md）
> ✅ 已验收 2026-08-22 AI批处理：simple_backtest/with_backtest/backtest_days全部删除，grep零残留，run_full_pipeline返回二元组
> ✅ 实跑验收 2026-08-22（AI 验收子任务）：grep 三词仅存 L389 注释；run.py 实跑输出仅选股表、无"回测结果"字样；import 回归通过 — **通过**
> 严重度：🔴 阻断　|　任务性质：代码修复（删除）　|　涉及文件：code/multi_factor_value.py、code/run.py、wiki/entities/system/multi-factor-v2.md
> 依赖：无　|　建议优先级：第一批

## 1. 问题现状

`multi_factor_value.py` 中的 `simple_backtest()` 函数（L354-377）用**今天**选出的股票池统计它们**过去 60 天**的涨跌幅，打印为"回测结果"。它是 `run_full_pipeline(with_backtest=True)` 的默认行为，是用户目前唯一能看到的"回测"。Wiki multi-factor-v2 页声称 backtest.py 已"替代旧 simple_backtest() 玩具版"——与事实相反。

## 2. 证据

- `code/multi_factor_value.py` L363：`ak.stock_zh_a_hist(symbol=c, period='daily', start_date=sd, adjust='qfq')` —— 使用 **qfq**
- 项目定稿规范 `backtest_engineering_spec_v2.1.md`：全系统统一 hfq、**禁用 qfq**（东财 qfq 有负价格实弹，招商银行 2014-2016 段出现 −1.67 元负价；qfq 历史随每次新除权全量改写）
- 逻辑结构：`selected` = 今天打分选出的股票（用了今天的价格+今天的财务数据）→ 对每只拉取"过去 60 天"行情 → `收盘[-1]/收盘[0]-1` 报平均收益
- 无成本（佣金/印花税/滑点全无）、无基准、无 T+1、无仓位管理
- `code/multi_factor_value.py` L402-403：`if with_backtest: simple_backtest(...)` —— 默认开启
- `wiki/entities/system/multi-factor-v2.md`："backtest.py — 真实成本回测引擎（替代旧 simple_backtest() 玩具版）"

## 3. 为什么是错

1. **未来函数（教科书级）**：选股用了今天的全部信息，"回测"的却是这些股票过去 60 天的表现——测的是"今天的高分股过去 60 天涨了多少"，不是策略能力。数值毫无策略含义，且必然系统性高估（今天的入选条件含近 60 天动量因子 MOM_60D，相当于用"最近涨得好"筛股票再统计"最近涨了多少"——自我循环）
2. **复权口径违规**：qfq 违背项目自己定稿并实测验证过的 hfq 铁律；且用东财 `stock_zh_a_hist`（限流最重的接口之一）逐股 20 次请求
3. **误导用户**：输出打印"回测结果"，用户会把它当策略验证——比没有回测更糟
4. **Wiki 撒谎**："已替代"是假的，玩具版还活着且是管线里唯一在跑的回测

## 4. 修改要求

1. **删除** `simple_backtest()` 函数（L354-377 整块）
2. `run_full_pipeline` 签名移除 `with_backtest` 参数，移除 L402-403 调用块
3. `run.py` 调用处同步清理（`backtest_days` 参数一并移除或保留为废弃警告——建议直接移除，保持接口干净）
4. 在引擎（backtest.py）接上真实数据（S2/C10）之前，**管线内不允许存在任何名为"回测"的输出**；选股输出仅 pick_*.csv
5. 同步修正 `wiki/entities/system/multi-factor-v2.md`：删除"替代玩具版"表述，如实写"真实成本回测引擎已实现金样本验证，尚未接入真实数据（见 review 任务 S2）"

## 5. 验收标准

- [ ] `grep -n 'simple_backtest\|with_backtest\|backtest_days' code/multi_factor_value.py code/run.py` 无残留（或仅注释说明已删除）
- [ ] `D:/pyh/python.exe -E run.py` 执行后输出仅选股表，无"回测结果"字样（数据拉取失败属 C10 范畴）
- [ ] Wiki multi-factor-v2.md 表述与实际一致
- [ ] 回归：multi_factor_value.py 其他函数不受影响（import 测试通过）

## 6. 修改后需同步的文档

- wiki/entities/system/multi-factor-v2.md（按第 5 点）
- wiki/log.md（追加 update 记录）
