# S3 — SOP 与代码不同步（含 run.bat 违反 -E 铁律）

> 来源：项目复盘 2026-08-22 第 S3 项（Wiki 全文：G:\股市探究\quant-investing\wiki\comparisons\project-review-2026-08.md）
> ✅ 已验收 2026-08-22 AI批处理：SOP结构树更新，run.bat加-E，提示文案修正
> ✅ 已验收 2026-08-22（S3 收尾批）：运行日志实现（code/run_logger.py + multi_factor_value.run_full_pipeline 关键节点日志 + run.py try/except 异常堆栈），logs/run_{时间戳}.log 实测生成（含启动时间/数据源/缓存/入池股数/因子覆盖率/选股输出路径/异常堆栈字段）；SOP §1.2 已补".bat 也必须带 -E"；SOP 版本 v1.5
> 严重度：🟠 重大　|　任务性质：文档修订 + 小代码修复　|　涉及文件：docs/SOP.md、code/run.bat、code/multi_factor_value.py
> 依赖：无（可与 C1/C2 并行）　|　建议优先级：第一批

## 1. 问题现状

SOP 自称"唯一事实源、SOP 优先于执行"，但事实源本身已过期，且有 4 处与代码现实冲突。

## 2. 证据

1. **结构树过时**：`docs/SOP.md` L102-105 把 data_fetcher.py/factors.py/backtest.py/report.py 全部标"(规划)"，但 backtest.py 已实现（605 行，金样本 25/25）；已实现的 sell_signals.py/ic_monitor.py/walk_forward.py/regime_weights.py/test_golden_samples.py 根本不在树里
2. **run.bat 不带 -E**：`code/run.bat` L11 是 `"D:\pyh\python.exe" "G:\股市探究\quant-investing\code\run.py"`，而 SOP §1.2 强制"必须 -E 运行"（本机 PYTHONPATH 被 Hermes venv 污染，不带 -E 会加载错误包）
3. **run.bat 文案错**：末尾打印 "Results saved to output/picks/"——代码实际保存到 `output/`（multi_factor_value.py L396-399），目录名是错的
4. **日志未实现**：SOP §3.4 要求"每次运行写日志 logs/run_{时间戳}.log"——run_full_pipeline 没有任何日志代码，logs/ 目录也不存在

## 3. 为什么是错

"唯一事实源"过期 + 入口脚本违反事实源铁律 = SOP 纪律在执行层失守。新问题会不断产生（先有代码后有文档），文档体系将加速漂移。

## 4. 修改要求

1. 更新 SOP §2 项目结构规范：
   - backtest.py：去掉"(规划)"，注明"已实现（金样本 25/25）"
   - data_fetcher.py：保留"(规划)"或按 S2 进度更新
   - 补充：sell_signals.py、ic_monitor.py、walk_forward.py、regime_weights.py、test_golden_samples.py 五行及一句话职责
2. run.bat L11 改为 `"D:\pyh\python.exe" -E "G:\股市探究\quant-investing\code\run.py"`；末尾提示改为 "Results saved to output/"
3. 在 multi_factor_value.py（或独立 logger 工具）实现运行日志：`logs/run_{时间戳}.log`，内容至少含：启动时间、数据源命中/缓存/降级情况、入池股数、因子覆盖率、选股输出路径、异常堆栈
4. SOP §1.2 终端执行规范补一条：".bat 也必须带 -E"

## 5. 验收标准

- [ ] SOP §2 结构树与 code/ 实际文件一一对应（diff 式核对）
- [ ] run.bat 带 -E；提示文案与实际输出目录一致
- [ ] 运行一次主流程（或干跑），logs/ 下生成含时间戳的日志文件
- [ ] `grep -n '规划' docs/SOP.md` 中已实现模块不再出现"(规划)"字样

## 6. 修改后需同步的文档

- wiki/entities/system/sop-v1.1.md（SOP 版本演进表加 v1.5 记录）
- wiki/log.md（追加 update 记录）
