---
title: 豆包 Seedream 生图接入 DSH
created: 2026-10-08
updated: 2026-10-08
type: entity
tags: [system, tool]
sources: [G:/deeeseek/doubao-image/README.md, G:/deeeseek/doubao-image/REVIEW.md, G:/deeeseek/ark-verify/REPORT.md]
confidence: 95
---

# 豆包 Seedream 生图接入 DSH

把字节跳动火山方舟（Volcengine Ark）的 Seedream 生图接进 DSH 的常驻 bundle `@local/doubao-image`。
源码在 `G:/deeeseek/doubao-image/`，装入 `C:/Users/asus/.dsh/profiles/web/`。

**本页只记录机制与实测证据；操作步骤与配置项看源目录的 `README.md`，复盘看 `REVIEW.md`。**

## 三条路径的分工（互不干扰）

| 触发 | 图显示在哪 | 影响主对话 | 机制 |
|---|---|---|---|
| 对话里说「画一张…」 | 对话里 | 是（本来就该） | Agent 工具 `doubao_generate_image` |
| `/draw <提示词>` | 不进对话 | **只写一条命令日志，零消息事件** | Host 命令 |
| 🎨 面板生成 | 面板里 | **完全不影响** | 插件专属回环通道 |

「不影响主对话」在三条路径上都有实证，不是设计意图：

- `/draw`：会话日志实测只有 `command/run` + `command/done`，**没有任何消息事件** —— 命令结果按契约是 log-only, never model surface。
- 面板：走的是插件自己的回环 HTTP 路由，生成全在 Host 进程内完成，字节直接 base64 回浏览器渲染。**不写会话日志、不进模型上下文、不触发模型轮次。**

## 坑清单

### 1. ★ 方舟有两台互不相通的接口面，用错面的报错是 401

**这是本次最贵的一个坑。**

| 路径 | 订阅制 key | 走量（按量付费）key |
|---|---|---|
| `/api/plan/v3/images/generations` | ✅ 200 | ❌ 401 `AuthenticationError` |
| `/api/v3/images/generations` | ❌ 401 `AuthenticationError` | ✅ 200（欠费时 403 `AccountOverdueError`） |

| 项 | 内容 |
|---|---|
| 现象 | HTTP 401 `AuthenticationError`：`The API key or AK/SK in the request is missing or invalid` |
| 根因 | key 与接口面不匹配。**报错文案与「key 抄错了」完全一样**，看不到任何「面」的线索 |
| 代价 | 我据此走了一整条错路：怀疑 key 多贴了字符（试了 45/44/47 位三种长度变体）→ 怀疑地域 → 怀疑 key 被撤销 → 准备让用户重新签发。真正要改的**只是一个路径段** |
| 绕行做法 | 两把面都配在代码里，换面只改 `config.baseUrl` 一行；收到 401/403 时顺手探另一台面，若那边通就把结论直接写进错误信息 |
| 证据 | 2026-10-07 实测矩阵（两把 key × 两条路径 × 两个 size 值） |
| 教训 | **同一个错误码可能对应完全不同的成因。先枚举该码的所有可能来源再逐条排除**，不要扎进最像的那个。用户给的一条看起来不像答案的线索（一个 URL）值得先当真去试 |

### 2. 命令名不允许中文，而且失败会连坐

| 项 | 内容 |
|---|---|
| 现象 | 插件整行 `fiberPhase: failed`，外部看到的是「工具压根没出现」 |
| 根因 | 命令名 `画图` 违反 `/^[a-z][a-z0-9_-]*$/u`（`interaction/commands` 的 `normalizeDefinition`） |
| 为何误导 | 报错行指向 `commands.register`，但同一 `apply` 里**前面的** `ctx.tools.register` 早已执行成功 —— **整行 fiber 失败会把已注册的工具一起回滚**，于是现象与根因分居函数首尾 |
| 绕行做法 | 命令名改 ASCII（`/draw`）；中文只留在 UI 标签与 description 里 |
| 证据 | 重启后暴露的真错：`TypeError: command name "画图" must match ...` |
| 教训 | 一个 `apply` 里注册多项能力时，任何一项抛错都会让全部能力消失；**排查要从「哪一项先失败」入手，而不是从「缺了哪一项」入手** |

### 3. `ctx.get(name)` 在未声明 inject 时抛错，不是返回 undefined

| 项 | 内容 |
|---|---|
| 现象 | 插件不激活：`cannot get property "tools" without inject` |
| 根因 | Cordis 反射层对未声明的服务**直接抛**（`vendor/cordis/src/reflect.ts:144`），并非「可选获取」 |
| 绕行做法 | 需要的服务必须在模块级 `export const inject = [...]` 声明；loader 读它（`registry.ts:330` → `Inject.resolve`），依赖缺失时走 `pending` 而非 `failed`（`app-boot/src/index.ts:796`） |
| 备选 | 只有 Web profile 提供的服务（`connection` / `webServer`）用 `ctx.inject([...], cb)` 延迟挂载，避免终端类 profile 整行不挂 |

### 4. Host 半不热重载，`set_plugin` 也不会重新 import 模块

| 项 | 内容 |
|---|---|
| 现象 | 改完 `index.js` 后 disable → enable 插件，报错**一字不变** |
| 根因 | 装好的 bundle 是 `profiles/web/node_modules/@local/…` 下的 junction，落在 `boot/hmr` 的 `ignored: ['**/node_modules', …]` 里；而 `set_plugin` 只改配置、重跑**已加载模块**的 `apply`，不重新 import |
| 判据 | 判断新代码是否生效，唯一可靠依据是**报错行号与当前文件内容的对应关系**。实测：报错指 388 行而文件已 506 行 = 旧代；报错指 609 行而当前文件该处是注释、613 行才是命令名 = 也是旧代 |
| 绕行做法 | Host 侧改动**只能靠重启 DSH**；客户端半由 `client-hmr` 轮询自动重载（约 0.5 秒，不用刷新） |

### 5. 实测推翻假定：产出是 JPEG，不是 PNG

| 项 | 内容 |
|---|---|
| 现象 | 按 PNG 命名落盘、按 `image/png` 入库 —— 会把文件写坏 |
| 根因 | 官方 `output_format` **默认就是 `jpeg`**，我没有读到那段就先写了 |
| 绕行做法 | 按字节 magic number 判定真实格式（`ffd8ff`/`89504e`/`RIFF`…）再决定扩展名与 `mediaType`，并优先采信接口自报的 `output_format` 与 `size` |
| 证据 | 实测 2K 请求回 `output_format: "jpeg"`、`size: "2816x1584"`，字节 `ff d8 ff` |
| 教训 | 外部接口的「输出格式」是必须实测或查文档的事实，**不能按文件名惯例想当然** |

### 6. 自检工具报「已配置」证明不了「能用」

| 项 | 内容 |
|---|---|
| 现象 | 自检报 `已配置（来源 credentials:file）`，紧接着真实出图返回 403 `AccountOverdueError` |
| 根因 | 本地自检只能证明 key 存在，证明不了账户有余额 |
| 绕行做法 | 加 `live_check`：**故意发一个超范围尺寸（`1x1`）**，让接口在参数校验阶段就拒掉，于是鉴权、账户、模型、参数四层全走一遍却**不出图、不计费**；拿到 400 就说明账户与模型都没问题 |
| 教训 | **用最小的代价换取最诚实的结论。** 「存在」与「可用」是两件事，自检要验后者 |

### 7. 同一个 404 有两种完全不同的含义

`ModelNotOpen`（模型没在这个账号下开通）与 `InvalidEndpoint`（模型 ID 不存在）都是 404。
只看 HTTP 状态会把它们混为一谈，**必须解析方舟自己的 `error.code`**。已建立错误码 → 人话映射：

| code | 含义 |
|---|---|
| `AccountOverdueError`（403） | 账户欠费。key 有效、模型也开通过，纯粹余额不足 |
| `ModelNotOpen`（404） | 该模型未在此账号下开通 |
| `InvalidEndpoint`（404） | 模型 ID 不存在 |
| `AuthenticationError`（401） | **先怀疑接口面选错**，再怀疑 key |

### 8. 面板要拿图片字节，两条现成路都是硬堵死的

| 项 | 内容 |
|---|---|
| 需求 | 面板出图显示在面板里，且不影响主对话 |
| 堵死路径 A | 提交到主对话（`inputActions.setDraft + submit`）——会真跑模型、往对话写消息 |
| 堵死路径 B | `/draw` + `session-controller` 读附件 —— 其鉴权 `referencedImage(source.events, id)` 里 `imageInEvent` **只认 `type:'image'` 的内容块，不认纯文本**；命令结果是 `{kind,text}`，必然报 `ATTACHMENT_NOT_REFERENCED`。绕过方式是往会话塞 image block，又违背要求 |
| 可用机制盘点 | `@Remote` 装饰器需要 `@deepseek-ai/dsh-typert`（profile 的 `node_modules` 里没有）；`connection.rpc.handle` 在本版本调用即抛（读自己上下文上没有的 `webServer`） |
| 解法 | **回环 HTTP 路由**（`ctx.inject(['connection','webServer'])` + `webServer.register({kind:'prefix'})`），与 `dsh-reasoning-effort` 在本部署用的同款机制；向 connection 要同一个 `requestRejection` 围栏，所以通道可达性与共享 `/api` 传输一致 |
| 教训 | 「没有现成接口」这个结论要建立在对**所有候选机制的逐一核对**上，而不是第一直觉 |

### 9. 未注册路由的实测表现是 405 + 空响应体，不是 404

打未注册的插件前缀时，请求落到别处被以「方法不允许」拒掉，返回 **405 + 空响应体**。
404 则是路由已接管但端点名不对。**错误码到成因的映射要按实测建立，不能按直觉假设。**

### 10. 别把明文凭据备份进项目目录

「改动前先备份」这条准则要有边界：**备份代码与配置，不要把凭据原件也复制一份**。
项目目录可能被整体打包或分享，`git` 是否跟踪并不是唯一的泄露路径。
（`.credentials.yaml` 本身是**明文**存储，属 DSH 现状。）

## 路径归属的判定方法（含一次方法错误）

`storeAttachment` 决定产物是否进附件库：**对话路径必须入库**（image block 要引用存储对象），
**面板路径必须不入库**（字节直接回 base64）。所以「这次调用走了哪条路」可以用可观测副作用事后判定。

**✅ 正确判据：**

```
对话/命令产物 → 工具结果里给出的 attachmentId 对应的对象存在：
                 C:/Users/asus/.dsh/attachments/v1/objects/<id[0:2]>/<id>
                 且该对象的 sha256 内容哈希 == 该 id（内容寻址自校验）
面板产物     → 该路径不调 saveImage，压根没有 attachmentId
```

**❌ 我一开始用错的判据：「手工算落盘文件的 sha256，去库里找同名对象」。**
两个错：① 落盘的是**接口原始字节**（`result.bytesRaw`），入库的是**归一化后重编码**的图
（实测落盘 470 KB / 1773×2364，附件 501 KB / 归一化到 1134×1512）——**两者本来就不该相等**；
② 正确的对照对象是**工具结果里给的 attachmentId**，而不是「文件名」。

**这条方法仍可复用**：任何「同一功能有多条调用路径」的场景，都能用一个可观测的副作用
（入库/不入库、写日志/不写日志）事后判定某次调用走了哪条路。但**判据必须选对**——
要拿「该路径承诺产出的标识」去核对，而不是拿「看起来相关的另一个数字」。
我这次是先用对了方向（面板产物不在库里）、后来又用错了工具（拿原始字节哈希去比），
后者如果没被独立核对拦下，就会变成一条写进文档的错误结论。

## 相关

- [[ai-toolchain-notes]] —— AI 协作工具链的通用坑（终端编码、Ollama 路由等）
- [[dsh-plugin-internals]] —— DSH 插件内部机制
- [[dsh-tool-presentation-modes]] —— 工具呈现模式
