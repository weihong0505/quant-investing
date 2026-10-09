---
title: DSH 插件内部机制与坑
created: 2026-09-19
updated: 2026-09-19
type: entity
tags: [system, tool, dsh]
sources: [G:/deepseek-harness（源码）, G:/deeeseek/btw-side-plugin（实装 @local/btw-side v1.2.0）, G:/deeeseek/knowledge-map/DSH-PLUGIN-AUTHORING.md]
confidence: 85
---

# DSH 插件内部机制与坑

本页记录写 DSH「本体插件」时踩到的**运行机制层面**问题。环境类坑（pwsh 编码、盘符根、行尾）见 [[ai-toolchain-notes]]；本页只写 DSH 自身的机制与证据。

**可复用配方已沉淀为两个 skill**：`dsh-web-ui-plugin`（浏览器半边）、`dsh-host-plugin`（Host 半边与子代理）。

> 标注约定：**实测** = 真实跑过；**源码** = 读源码得到、未跑过。不要把前者当后者用。

## 一、三个半边，三种重载规则（源码）

| 改了什么 | 怎么回来 |
|---|---|
| `client.js` | 约 **0.5 秒自动重载**，不用刷新也不用重启（`client-hmr` 每 500ms 轮询 `clientModules.graph()` 的 `{mtimeMs,size}`，**无 node_modules 过滤**） |
| `index.js` | **什么都不发生，必须重启 DSH**（`boot/hmr` 默认 `ignored: ['**/node_modules', …]`） |
| `cordis.yml` / patch | 有显式配置监听 |

**根因**：安装态 bundle 在 `profiles/<name>/node_modules/@local/<pkg>/`（指向源目录的 junction），Host 半边正好落在被忽略的路径下。

> 我曾据此记过「HMR 忽略 node_modules、改代码要重启」——**只对 Host 成立**。Client 是另一套机制。

## 二、★ 常驻子代理会**唤醒**父代理，一次性不会（实测 + 源码）

**这是本页最重要的一条。**

`subagent/src/continuation-activation.ts:871` 的 `notifySettlement` 会把子代理的**收尾文本包成一条 `role:'user'` 消息**，然后 `sendWaking(parent, msg, parent.status === 'idle' ? 'queue' : 'steer')` —— 父代理空闲时 **queue 即开一轮**。

| 子代理形态 | 收尾时 |
|---|---|
| `startContinuable`（常驻） | ❌ **通知父代理**（进上下文 + 可能开一轮），**无开关** |
| `start`（一次性） | ✅ 什么都不发，答案经 `run.result` 直接交回调用方 |

**实测代价**：一次真实的 `/btw` 提问让主代理白开了第 48 轮，上下文里多了一整段侧代理回答。

**证据**：主会话日志 seq 4748 `agent/inbox/spliced`（`source.kind='subagent-settled'`）→ seq 4753 变成真正的 `user/message` → seq 4749 `turn/start`。
`createSettlementMessage` 全仓**只有一个调用点**，就在常驻激活里——**所以一次性子代理不会有这个副作用**。

**推论**：凡"不想惊动某个 agent"的辅助 agent，一律用一次性。

## 三、工具过滤器要用 `allow`，不要用 `deny`（源码）

`core/tools/src/index.ts:1074`：`allow` = keep only，`deny` = remove，未知名字抛错并列出权威清单。

**方向决定失效模式**：

| | 将来新增一个工具时 |
|---|---|
| `deny` 黑名单 | **静默授予**（fail-open）—— 危险 |
| `allow` 白名单 | **静默缺席**（fail-closed）—— 安全 |

所以"这个 agent 不能做 X"的需求，一律写白名单。另注：**没有通配符**，`allow: ['*']` 会抛错；名字必须是**全局**工具（preset 行里注册的是作用域内工具，写进过滤器会抛 `unknown global tool`）。

## 四、命令生命周期（实测 + 源码）

- **命令在轮次之外执行**：契约原文 *"no turn wraps them"*。实测：主代理正在跑一个 90 秒工具调用时，`/btw` 照常执行、投递、并在同一窗口内拿到回答。
- `command/run` / `command/done` 按契约是 **"log-only (never model surface)"** —— 进日志，**不进模型上下文**。
- `recordInput: false` 让 `command/run` 不再记录 `args`（原句不落日志）。
- ⚠️ **命令的返回文本会记进 `command/done.text`**。若 UI 只能靠命令返回值拿数据，那份数据就会落进会话日志（仍是 log-only，但要知道）。

## 五、会话日志：多帧 zstd（实测）

位置：`$DSH_HOME/sessions/--<cwd-带横线>--/<sessionId>/session.v3.jsonl.zstd`；
子代理会话是**裸 uuid 目录**（无 `session-` 前缀）。

**`zstdDecompressSync()` 与 `createZstdDecompress()` 都只解第一帧** —— 而这些日志是多帧拼接，于是只会得到 1 条 `session` 头记录，让人误判成空文件。**必须按帧魔数 `28 B5 2F FD` 切分逐帧解。**

工具：`G:\deeeseek\tools\read-session-log.mjs`（类型直方图 / `session/end-seed` / 轮次边界 / 带时间戳的尾部）。

日志里几条有用的事实：
- `seq == log.length`，且 `snapshotEvents(from)` **就是** `log.slice(from, seq)`。
- **继承（重放）的事件保留父会话的原始 `time`** —— 所以 `time >= sentAt` 是可靠的"这是新的"判据，偏移量不是。
- `agents.get(id)` 对**不常驻**的子代理返回 `undefined`；此时投递会让它**冷恢复**。每次冷恢复会多一条 `session/end-seed`。

## 六、两个静默给错结果的坑（实测）

1. **`snapshotEvents(-1)` 就是 `slice(-1, seq)`** —— 负数在 slice 里是"从末尾数"，只返回最后一个元素。于是永远扫不到要找的东西，白等到超时（侧代理其实 5 秒就答完了）。**负值合法、不报错、静默给错结果。**
2. **不要拿 `agent.status` 当门** —— 它是实现类的私有相位标志（`core/agent-loop/src/agent.ts:114`）。`agents` 公布的 `Agent` 接口**只有 `id`**；在活 agent 上用的其他字段全是实现表面。

## 七、方法论：判据层级

```
座位注册 active:true  ＜  渲染出来  ＜  能交互  ＜  位置/观感  ＜  用户看到的输出正确
   （我能自查）           （用户能看）   （用户能操作）  （只有用户能判）
```

**不许把低层证据当成高层结论。** 我这次三次把"没验证"说成"已验证"：把"侧代理收到并作答"当成"端到端成功"（收到 ≠ 回读成功，用户随后就撞上超时）；把 Host 的重载规则套到 Client 上；还一度准备把一条误判写进文档。

配套两条硬规矩：
- **先 grep 错误文案的出处，再定根因。** 我追了半天的 `this seat has no session or Remote face`，grep 全源码才发现**是我自己早期版本写的诊断文案**。
- **修一个 bug 后问一句"同类坑还有几处"** —— `-1` 修完回头查了 `commitPrefixEnd`，确认它返回 `i+1` 或 `0`，才敢说那条路安全。

## 相关页面

- [[ai-toolchain-notes]] —— 环境类坑（pwsh 编码 / 盘符根 / 行尾 / Ollama 丢 tools）
- [[sop-v1.1]] —— 规则本体
- 工作区内的详细配方：`G:\deeeseek\knowledge-map\DSH-PLUGIN-AUTHORING.md`（§9 子代理 / §10 Remote 来源 / §11 热重载 / §12 两个坑 / §13 唤醒机制）
- 运行时 API 实测快照：`G:\deeeseek\knowledge-map\DSH-RUNTIME-API.md`
