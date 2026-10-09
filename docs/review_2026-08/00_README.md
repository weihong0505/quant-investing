# 项目复盘 2026-08-22 — 分项问题任务包（供其他 AI 修改用）

> 每个文件 = 一个独立问题，自包含（现状+证据+为什么错+修改要求+验收标准），**可直接整文件复制交给其他 AI**。
> 完整复盘与全部思考过程：`G:\股市探究\quant-investing\wiki\comparisons\project-review-2026-08.md`（Wiki 页）。
> 本目录位置：`G:\股市探究\quant-investing\docs\review_2026-08\`。

---

## 任务清单（22 项）

| 编号 | 文件 | 严重度 | 任务性质 | 主要涉及文件 |
|------|------|--------|----------|--------------|
| S1 | `S1_因子零检验.md` | 🔴 | 检验任务+叙事修正 | factor_registry.md、factor_docs/ |
| S2 | `S2_无端到端管线.md` | 🔴 | 代码修复（新建） | code/（新建 data_fetcher.py） |
| S3 | `S3_SOP与代码不同步.md` | 🟠 | 文档修订 | docs/SOP.md、code/run.bat |
| C1 | `C1_run_py入口崩溃.md` | 🔴 | 代码修复 | code/run.py |
| C2 | `C2_simple_backtest未来函数.md` | 🔴 | 代码修复（删除） | code/multi_factor_value.py |
| C3 | `C3_px_hfq零使用.md` | 🔴 | 代码修复 | code/backtest.py |
| C4 | `C4_引擎与规范缺口7项.md` | 🟠 | 代码修复 | code/backtest.py |
| C5 | `C5_sell_signals三处逻辑问题.md` | 🟠 | 代码修复 | code/sell_signals.py |
| C6 | `C6_ic_monitor缺主判定线.md` | 🟠 | 代码修复 | code/ic_monitor.py |
| C7 | `C7_walk_forward名不副实.md` | 🟠 | 代码修复/改名 | code/walk_forward.py |
| C8 | `C8_regime_weights半成品.md` | 🟠 | 代码修复+审批 | code/regime_weights.py |
| C9 | `C9_选股层因子口径6项.md` | 🟡 | 代码修复（6 子项） | code/multi_factor_value.py |
| C10 | `C10_数据断供无降级.md` | 🟠 | 代码修复 | code/multi_factor_value.py |
| W1 | `W1_Wiki空知识库.md` | 🟡 | Wiki 建设 | wiki/raw/ 等 |
| W2 | `W2_Wiki错误声明.md` | 🟠 | Wiki 修订 | wiki/entities/system/ |
| W3 | `W3_文档三轨漂移.md` | 🟡 | 文档修订 | SOP/factor_docs/wiki |
| M1 | `M1_审查偷换为有效.md` | 🔴 | 文档修订（全面叙事冻结） | 多文件清单内 |
| M2 | `M2_检验与策略脱节.md` | 🟠 | 检验任务 | 依赖 S1 完成后 |
| M3 | `M3_先集成后检验.md` | 🟠 | 流程修订 | docs/SOP.md §3.0 |
| M4 | `M4_金样本虚假安全感.md` | 🟠 | 认知纠偏+Wiki 修订 | wiki/entities/system/backtest-engine.md |
| M5 | `M5_先验当结论.md` | 🟠 | 检验任务 | registry、因子检验 |
| M6 | `M6_复权口径审计缺失.md` | 🟡 | 文档新建 | docs/factor_docs/ |

## 建议修改顺序（依赖关系）

1. **第一批（打通入口）**：C1 → C2 → S3（改完即可运行）
2. **第二批（数据地基）**：C10 → S2（没有历史数据，S1/M5/M2 无法执行）
3. **第三批（因子检验）**：S1 → M5 → M2（检验结果决定权重去留）
4. **第四批（引擎补齐）**：C3 → C4 → C5（依赖金样本回归 25/25）
5. **第五批（工具链）**：C6、C7、C8
6. **随时可做（文档类）**：M1、M3、M4、M6、W1、W2、W3、C9（C9 的⑥子项依赖 C9 其他项结论）

## ⚠️ 给修改 AI 的通用环境须知（必读，否则会踩坑浪费时间）

1. **运行命令**：本机必须 `D:/pyh/python.exe -E script.py`（`-E` 防 PYTHONPATH 被 Hermes venv 污染；不用系统 python）
2. **终端是 git-bash**：POSIX 语法；中文 print 会乱码但不影响数据，**测试断言输出用英文**
3. **编码陷阱**：多数项目文件是 **UTF-8 BOM + CRLF**。`read_file` 可能误判 binary；**patch 式编辑在 CRLF 文件上会整文件打乱**（本会话实测 log.md 被打乱过）。安全做法：用 Python `open(f, encoding='utf-8-sig').read()` 读取 → 修改 → `open(f, 'w', encoding='utf-8', newline='\n').write()` 整体写回（去掉 BOM、统一 LF，Python 代码完全兼容）
4. **代理三件套**：脚本头部必须先于 `import requests` 设置 `NO_PROXY=*` 并清除全部 proxy 环境变量 + monkey-patch `requests.Session.request`（模板见 docs/SOP.md §1.3）。否则国内接口全挂
5. **东财限流**：push2.eastmoney.com 当前处于跨日封禁状态（ReadTimeout）。**不要对东财做高频实测**；单测一律用合成数据或本地 parquet 缓存；网络验证用 `_netdiag.py`
6. **回归红线**：任何 backtest.py 改动后必须重跑 `test_golden_samples.py`，保持 25/25 PASS；新增行为必须**新增金样本用例**
7. **纪律**：先审批后写码、先检验后集成（SOP §3.0）；改完代码必须同步更新本目录任务文件对应的"验收标准"勾选状态和 Wiki 对应页面
8. **规范依据**（修改前先读）：
   - `G:\股市探究\quant-investing\docs\factor_docs\factor_testing_methodology_v3.md`（因子检验定稿）
   - `G:\股市探究\quant-investing\docs\factor_docs\backtest_engineering_spec_v2.1.md`（回测工程定稿）
   - `G:\股市探究\quant-investing\docs\SOP.md`（唯一事实源，v1.4）

## 验收总则

- 每个任务文件自带验收标准；验收通过 = 标准全部满足 + 回归测试通过 + 相关文档已同步
- 验收结果回填本目录对应文件（在标题下加一行 `> ✅ 已验收 YYYY-MM-DD 操作者`）+ Wiki log.md 追加记录
