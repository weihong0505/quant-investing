---
title: AI 协作工具链经验
created: 2026-09-18
updated: 2026-10-08
type: entity
tags: [system, tool]
sources: [docs/SOP.md, docs/review_2026-08/00_README.md, G:/AI-通用准则.md]
confidence: 80
---

# AI 协作工具链经验

本页汇总与 AI 代理（DSH / Claude / Hermes / MImo）协作时反复踩到的**工具链层面**问题与已验证绕行做法。

**规则本体在 [[sop-v1.1]]（SOP §1.2 终端执行规范 / §5 Troubleshooting），本页只描述机制与证据，不复制参数值。**

## 环境事实

| 项 | 值 |
|----|-----|
| DSH 工作目录 | `G:\deeeseek` |
| DSH 源码检出 | `G:\deepseek-harness`（只读参考，与工作目录是两个位置） |
| DSH 用户目录 | `C:\Users\asus\.dsh`（`DSH_HOME`） |
| DSH Web GUI | `http://127.0.0.1:3080` |
| 全局指令 / 提示词 | DSH：`C:\Users\asus\.dsh\AGENTS.md`（自动注入）；Claude：`C:\Users\asus\.claude\CLAUDE.md`（自动加载）；全文：`G:\AI-通用准则.md`（按需读） |
| 本机 Ollama | exe 在 `%LOCALAPPDATA%\Programs\Ollama`，服务 `127.0.0.1:11434`，已装 `qwen3-30b-a3b-cpu`、`qwen3:30b-a3b`、`qwen2.5:7b`、`qwen2.5vl:7b`；**模型库已迁至 `G:\股市探究\quant-investing\ai\models`**（`OLLAMA_MODELS` 已设，但改动后**必须重启 Ollama 服务**才生效——server 启动早于变量设值时会一直用默认 C 盘路径） |

> 说明：`docs/review_2026-08/00_README.md` 记录的「终端是 git-bash」描述的是**量化项目脚本**的执行环境；DSH 工具链的终端是 **PowerShell（pwsh）**，两者坑位不同，不要互相套用。

## 坑清单

### 1. PowerShell 命令行传中文会变 GBK 乱码

| 项 | 内容 |
|---|---|
| 现象 | 用 pwsh 内联写入含中文的内容，文件里全是乱码；用 pwsh 读取 UTF-8 中文文件，输出也是乱码 |
| 触发条件 | 中文出现在 `pwsh -Command` 的命令串里 |
| 根因 | 命令串在到达 pwsh 前按系统 ANSI 代码页（中文 Windows 为 GBK）转换，`.ps1` 源文件与文件内容本身都没问题 |
| 绕行做法 | 中文内容一律走 write/edit 工具（实测输出 UTF-8 无 BOM + LF）；pwsh 只做校验、字节拼接、哈希对账等纯 ASCII 操作 |
| 证据 | 2026-09-18 读 `CLAUDE.md` 显示乱码，同文件 `[Text.Encoding]::UTF8.GetString()` 解码完全正常 |
| 规则落点 | SOP §1.2 |

### 2. write/edit 工具无法写盘符根目录

| 项 | 内容 |
|---|---|
| 现象 | 对 `G:\` 下的文件调用 write/edit，报 `EPERM: operation not permitted, mkdir 'G:\'` |
| 触发条件 | 目标文件位于盘符根目录（如 `G:\AI-通用准则.md`） |
| 根因 | 工具为保证原子写会先创建父目录，对盘符根执行 mkdir 被拒；**不是权限不足，提权无效** |
| 绕行做法 | **两条路**：①（**更简单，已实测**）用 Git Bash 写——`& "C:\Program Files\Git\bin\bash.exe" -c "cat > /g/文件.md <<'EOF' … EOF"`，可直接写盘符根；② write 写工作区临时文件 → 纯 ASCII pwsh 以 `UTF8Encoding($false)` 整体覆盖目标 → `Compare-Object` 逐行 diff + `Get-FileHash` 对账 → 删临时文件 |
| 证据 | 2026-09-18：`write`/`edit` 对 `G:\AI-通用准则.md` 报 `EPERM: mkdir 'G:\'`；Git Bash 写 `/g/_bashprobe.tmp` 返回 `WRITE-OK`。旁证：另一 Agent 在 `G:\mimo-review\REVIEW.md` 也记录了同一现象（"Write 工具对 G:\ 跨盘报 EPERM → 改用 Bash heredoc"），**独立复现** |
| 注意 | PATH 里的 `bash` 是 **WSL 空壳**（`C:\WINDOWS\system32\bash.exe`，未装发行版会报 `execvpe(/bin/bash) failed`）——必须用 Git 自带的 `C:\Program Files\Git\bin\bash.exe` |
| 规则落点 | SOP §1.2 |

### 3. 编码不一致：规范 LF，wiki 页面 CRLF

| 项 | 内容 |
|---|---|
| 现象 | 同一库内不同文件换行风格不同，统一按 LF 写回会整文件改行尾 |
| 触发条件 | 用「读全文—改—整体写回」方式编辑 |
| 根因 | 实测 `SCHEMA.md` / `FILE-MANAGEMENT-STANDARD.md` / `index.md` / `log.md` 为 UTF-8 无 BOM + **LF**；`entities/system/local-ai.md` 等 wiki 页面为无 BOM + **CRLF**（与 `docs/review_2026-08/00_README.md:49` 记录的 BOM+CRLF 陷阱同源） |
| 绕行做法 | 动手前先按文件实测编码分类；写回时显式指定 `UTF8Encoding($false)` 并保持原换行风格；改完做哈希/行数对账 |
| 证据 | 2026-09-18 按类实测：规范类 LF=326~407、CRLF=0；wiki 页面 CRLF=84、纯 LF=0 |
| 规则落点 | SOP §5 |

### 4. 多层级指令会重复注入

| 项 | 内容 |
|---|---|
| 现象 | 全局与工作目录两层 `AGENTS.md` 内容在上下文里出现两次 |
| 触发条件 | 全局 `$DSH_HOME/AGENTS.md` 与项目 `AGENTS.md` 同时命中 |
| 根因 | 注入通道本身（system prompt 的 workspace-instructions 块 + 变更后的 system-reminder 块），非两份不同文件 |
| 绕行做法 | 不必处理；不要误判为内容冲突 |
| 证据 | 2026-09-18 独立 agent 只读核验 |
| 规则落点 | 本页 |

### 5. ~~Ollama 的 OpenAI 兼容端点会静默丢弃 tools~~ → **已不复现（2026-09-21 更正）**

> ⚠️ **本条结论已作废**，保留原观测以便追溯。2026-09-21 用**原测法**复测，未复现。

| 项 | 内容 |
|---|---|
| 原结论（2026-09-18） | 走 `/v1/chat/completions` 请求工具调用，返回 HTTP 200、`finish_reason: stop`、`tool_calls` 为空，模型只回文本——**看起来像正常回答，实际工具根本没被执行**。但同一端点的**图片输入是正常的**（与 tools 的表现相反，勿一概而论） |
| 原根因判断 | Ollama 0.34.2 的 `/v1/chat/completions` 未把 `tools` 透传给模型；原生 `/api/chat` 正常工作 |
| **复测结论（2026-09-21）** | **问题不复现**。同一模型（`qwen2.5:7b`）、同一问题、同一工具定义，三种条件**全部正常返回 tool_calls**（见下证据）。推测该缺陷已在当前 Ollama 版本修复，或因当时配置差异所致；**中间版本时间线未追溯，故只断言"当前不复现"** |
| 复测证据（2026-09-21，Ollama 0.34.2） | A) `/v1/chat/completions` 仅带 `tools` → `finish_reason=tool_calls`，`get_time({"city":"Beijing"})` ✅　B) 同端点 + **`tool_choice: "required"`**（即原测法）→ **`tool_calls=1`**（原记录为「0 个」）✅　C) 原生 `/api/chat` → `tool_calls=1` ✅ |
| **但模型侧确有限制（新增，勿过度乐观）** | `qwen3:30b-a3b` 实测**不产生工具调用**：带 tools 请求时无 `tool_calls`，只在正文里念叨「有个 get_weather 工具」 |
| 现行做法 | 本地 Ollama 路由**可以**带 tools 调用；但仍建议以**无工具任务**为主（文本：分类/摘要/改写/格式化/草稿；视觉：描述/OCR 辅助），因为**是否可调用取决于具体模型**。需可靠工具调用的 agent 任务仍走云端模型 |
| 规则落点 | 本页 |

**相关（同批实测，2026-09-21）**：`qwen3:30b-a3b` 另有一坑——直接引用原模型会被 Ollama 自动 offload 到 8 GB 显存 → CUDA OOM → **`/v1/chat/completions` 返回 HTTP 500**。须用固化 `num_gpu 0` 的变体（本机为 `qwen3-30b-a3b-cpu`），纯 CPU 实测 19.5 tok/s、模型内存足迹约 18.7 GB。

### 6. 本地视觉模型的准确率不足以承担关键识别

| 项 | 内容 |
|---|---|
| 现象 | `qwen2.5vl:7b` 抄录图片文字基本正确，但**会编造文字与图形之间的映射关系**、并漏抄其中一行 |
| 触发条件 | 提示词里出现类似编号/代号的字符串（如 `SEQUENCE: A7 - K2 - M9`）时，模型会把它当成图形标签，自行编出「A7=红方块 / K2=绿圆 / M9=蓝方块」这种原文中**并不存在**的对应 |
| 根因 | 小参数视觉模型在图像上进行常识性补全，倾向把零散字符串解释成有语义的结构 |
| 绕行做法 | ① 关键识别（个人数据、票据、需要准确性）用云端强模型；② 本地模型只做粗描述与初筛，且必须让模型**逐字抄录**而非「描述含义」；③ 结果须与真值或人工对账后才可用（防过拟合同源的纪律：别只看「像不像」） |
| 证据 | 2026-09-18 用 800×600 合成图（真值：红方块/绿圆/蓝方块 + 4 行文字）实测：本地模型两轮均编出 `A7: Red square` 等映射并漏抄 `three blocks: ...` 一行；云端模型 4 行文字逐字正确、图形顺序全对 |
| 规则落点 | 本页 |

### 7. DSH 的 read 工具不吃图，必须用 read_image

| 项 | 内容 |
|---|---|
| 现象 | 用 `read` 读 PNG，返回 `Error: cannot read "...": binary file`，拿不到任何像素 |
| 触发条件 | 对图片文件调用文本读取器 `read` |
| 根因 | `read` 是文本读取器，二进制文件直接拒绝；图像要走专用工具 `read_image` |
| 绕行做法 | 让 agent 看图时必须点名 `read_image`；对子代理下指令要写清工具名，否则它会（正确地）拒绝猜测 |
| 证据 | 2026-09-18 两次子代理对照：指示用 `read` → `binary file` 报错且如实报告「未收到图像内容」；指示用 `read_image` → 收到图像并逐字读对全部内容 |
| 规则落点 | 本页 |

### 8. git 的 core.autocrlf 会静默改写行尾

| 项 | 内容 |
|---|---|
| 现象 | 对本库 `git add` 时刷屏警告 `LF will be replaced by CRLF the next time Git touches it`——即 git 检出时会把 LF 改成 CRLF，**等于每次碰文件都在改文件字节** |
| 触发条件 | 本机 **system 级** git 配置 `core.autocrlf=true`（Windows Git 安装器默认；`--global` 反而是空的，所以只查 global 会误判为"没问题"） |
| 根因 | autocrlf=true 时 git 认为工作区行尾应随平台，于是入库规范化、检出还原为 CRLF |
| 绕行做法 | ① `git config core.autocrlf false`（本仓库级）；② 加 `.gitattributes` 写 `* -text`（对所有克隆方生效）；③ 改完抽查 `git cat-file -s` 与磁盘字节数是否一致 |
| 证据 | 2026-09-18 给 `G:\股市探究\quant-investing` 上 git：排查发现 `system=true / global=空`；关闭后警告消失，抽查 5 个文件入库字节与磁盘**完全一致**（如 `wiki/index.md` 7686B 对 7686B） |
| 规则落点 | 本页 |

### 9. pwsh 校验脚本的四个高频自伤动作

**背景**：本会话（2026-09-18）在同一个会话里因 pwsh 语法/语义问题失败 4 次，其中一次**造成了真实副作用**（把 `index.md` 的行尾从 LF 改成 CRLF）。这些坑的共同点是：**失败得很安静或很吵，但都可能已经改坏了文件**。

| 项 | 内容 |
|---|---|
| 现象 | ① `-like '*- [[local-ai]]*'` 抛 `WildcardPatternException`（`[[...]]` 在通配符里是**字符类**）；② `-match 'investingi'` 检查数组时返回 False，导致把**确实存在**的字符串判为不存在；③ `[System.IO.File]::ReadAllText('相对路径')` 抛 `DirectoryNotFoundException`（.NET 不认 pwsh 的当前位置，pwsh 只在**传给外部程序**时解析相对路径） |
| 触发条件 | 用 `-like` / `-match` 校验含方括号或反斜杠的文本；用 .NET API 读相对路径 |
| 根因 | pwsh 的 `-like` 是通配符（`[` 有语义）；`-match` 在数组上返回**过滤后的元素**而非布尔；`[System.IO.*]` 是纯 .NET，不经过 PowerShell 的 Provider 路径解析 |
| 绕行做法 | ① 文本包含判断一律用 `.Contains('…')`，不用 `-like` / `-match`；② 判断数组是否含某项用 `-contains`，或对**单个字符串**用 `-match`；③ .NET 文件 API 一律传**绝对路径**；④ **风险脚本先跑"只读校验"版本再跑写入版本** |
| 证据 | ① 给 `index.md` 插条目时异常→插入未执行，但那一次的 `ReadAllText`/`WriteAllText` 已把 7500B 文件的 LF 全转成 CRLF（LF=109/CRLF=109）；用纯 LF 写回后修正为 7686B；② 校验 SOP §697 笔误时 `-match` 对数组返回 False，误判"不存在"，改用逐行 `.Contains()` 后确认笔误确实存在 |
| 纪律 | **写入型脚本必须"先 diff / 后写入"**：先输出将改动哪些行、前缀后缀哈希，确认无误再执行第 2 步。一次做完"检查+写入"的脚本，出问题时已经改完了 |
| 规则落点 | 本页 |

### 10. Ollama 模型打包：`show --modelfile` 的输出无法回灌

**背景**：2026-10-08 打包本地 `tongnai-nsfw` 分享给他人时实测。要用 Ollama 迁移/分享模型（尤其 LoRA 合并后自量化的本地 GGUF，registry 上没有），看起来最自然的路是 `ollama show --modelfile` 导出再 `ollama create` 导入——**这条路走不通**。

| 项 | 内容 |
|---|---|
| 现象 | 把 `ollama show --modelfile <模型>` 的输出存成文件喂给 `ollama create`，报 `Error: (line N): command must be one of "from", "license", "template", "system", "adapter", "draft", "renderer", "parser", "parameter", "message", "requires"`。该输出头部还自带误导性注释「To build a new Modelfile based on this…」 |
| 触发条件 | Ollama 0.35.0，`--modelfile` 输出含多行 `SYSTEM` 或多行 `TEMPLATE` 时 |
| 根因（两条，均为实测） | ① **`SYSTEM` 的三引号必须与 `SYSTEM` 同行**：`SYSTEM """第一行` 合法；`SYSTEM` 与 `"""` 分两行非法。② **`TEMPLATE` 必须是单行**，多行模板被当作后续非法指令。`show --modelfile` 两条都违反 |
| 绕行做法 | ① `SYSTEM """` 与首行内容同行，结尾用单独一行 `"""`；② 模板里的换行**转义成字面 `\n`** 压成一行——Ollama 模板引擎渲染时会正确还原（2026-10-08 用 `/api/chat` 实测：无 `<|im_start|>` 标签泄漏、无 `\n` 字面残留）；③ 提示词与模板**从 blob 原样读取**（`OLLAMA_MODELS/blobs/sha256-*`），不要经 shell 复制粘贴 |
| **API 也有坑** | Ollama 0.35 的 REST `/api/create` 对**本地 GGUF 路径**一律返回 `{"error":"invalid model name"}`（模型名换 `x` / `x:latest` 均照报）；而 `"from":"qwen2.5:7b"`（registry 模型）同端点正常。结论：**导入本地 GGUF 只能走 CLI**，别在 API 上耗时间 |
| 旁证（别误判） | 中文/空格目录名会让 CLI 报**完全相同的** `invalid model name`。2026-10-08 在含中文的目录下成功导入，证明中文路径本身可用——报这个错先查 Modelfile 语法，再查路径 |
| **硬链接安全（已实测）** | 为省磁盘用 `fsutil hardlink`/`New-Item -ItemType HardLink` 把 GGUF 挂进分享包后，**`ollama create` 不会写透硬链接**：Ollama 先算文件 sha256，命中已有 blob 就 `using existing layer sha256:…` 直接复用，源文件链接数保持 2、hash 与 mtime 均未变。（若走复制则不会有此顾虑，但会多占一份空间） |
| 导出侧的另一个缺陷 | 若原始模型的 template 层是裸透传 `TEMPLATE {{ .Prompt }}`，导出后 `ollama create` 出来的模型**多轮对话会退化成纯文本续写**（没有 `<|im_start|>` 角色标记）。修复方式是补上基座官方 chat template（Qwen2.5 的模板可从 `qwen2.5:7b` manifest 里的 template blob 取） |
| 规则落点 | 本页 |

### 11. 分享大文件：`http.server` 不支持 Range；cloudflared 在代理环境下要走 http2

**背景**：同一次打包任务（2026-10-08）要把 5 GB 权重发给别人，用 Python 起分发服务 + Cloudflare 快速隧道。

| 项 | 内容 |
|---|---|
| 现象 A | `curl -r 0-1023` 打 `python -m http.server`，返回的是**整个 5 GB**（HTTP 200）而不是 1 KB（HTTP 206）——**断点续传静默失效**，5 GB 传到一半断线只能重来 |
| 根因 A | `SimpleHTTPRequestHandler` **完全不处理 `Range` 头**，也不发 `Accept-Ranges`。这一点很容易想当然认为「标准库肯定支持」 |
| 绕行做法 A | 覆盖 `send_head()` 自己实现 206：正确解析 `bytes=S-E`、`bytes=S-`、`bytes=-N` 三种形式（非法区间回 416 + `Content-Range: bytes */<size>`）；**用包装对象限制 `read()` 返回字节数**，否则 206 仍会把整个文件吐出去；统计流量时别按 `Content-Length` 计数（会把 1 KB 的 206 记成 5 GB），应在 `copyfile()` 里按实际写出的字节累加 |
| 现象 B | `cloudflared tunnel --url http://127.0.0.1:PORT`（默认 QUIC）报 `failed to dial to edge with quic: timeout: no recent network activity`，`Registered tunnel connection` 始终不出现 |
| 根因 B | 本机走 Mihomo 代理（TUN 模式，fake-IP 段 `198.18.0.0/16`）：`region*.v2.argotunnel.com` 被解析到 `198.18.0.x`，QUIC 需要的 **UDP 7844 出不去**；而 fake-IP 只代理 TCP，所以 **TCP 通、UDP 不通** |
| 绕行做法 B | 加 **`--protocol http2`** 强制走 TCP：`cloudflared tunnel --url http://127.0.0.1:8000 --protocol http2 --no-autoupdate`。cloudflared 自己的连通性预检也会给出 `suggested_protocol=http2`，日志里 UDP 两项 FAIL、TCP 两项 PASS |
| 验证纪律 | 这条链路值得**端到端验证而不是只 ping 首页**：完整下载 5 GB → 比对 SHA256；再从**公网域名**拉前 1 MB → 与本地文件逐字节比对。2026-10-08 两项均通过（本地 219 MB/s，公网走 HKG 节点 206 正常） |
| 另注 | winget 搜索结果里 `sakurai-youhei.qrrun` 带 `cloudflared` 标签，但它是**脚本运行器、与二维码无关**（本次已装完即卸）。要生成二维码直接用 Python `qrcode` 库 |
| **附带：给别人的 .ps1 必须带 UTF-8 BOM** | 交付的 `import.ps1` 初版是 UTF-8 无 BOM，**实际运行时被按 GBK 解码** → 中文变乱码 → 引号失配 → ParserError、整个脚本不可执行。Windows PowerShell 5.1 判定 .ps1 编码时**不看 BOM 就会回退到 ANSI**，故含中文的 .ps1 一律存 `UTF8Encoding($true)`（PS 7 同样兼容）。**校验陷阱**：`Parser::ParseFile` 自身也按 ANSI 解码文件，用它检查含中文的 .ps1 会给出误导性报错（本次先误判为「解析器对全角标点的误报」，实为编码问题）；可靠做法是自读字节 + `Encoding.UTF8.GetString()` 再 `Parser::ParseInput` |
| **附带：`$ErrorActionPreference="Stop"` 会吞掉原生命令的 stderr** | `ollama create` 把进度条写到 stderr，在 `Stop` 模式下 PowerShell 把 stderr 首行当作**终止性错误**直接中断脚本——表现为「导入到一半突然失败」，但模型其实能建成。解法：调用处临时降为 `SilentlyContinue`，只以 `$LASTEXITCODE` 判定成败 |
| 规则落点 | 本页 |

### 12. 公网穿透：Cloudflare 隧道边缘可被网络阻断；免费隧道按「真实流量」踢空闲连接

**背景**：同一次打包任务（2026-10-08）当晚，Cloudflare Quick Tunnel 链接**突然 530**，排查后换 localhost.run，又**被服务端踢掉**。两个故障都不是配置问题。

| 项 | 内容 |
|---|---|
| 现象 A | 隧道进程还活着、本地服务 200，但公网域名返回 **530**，cloudflared 日志反复 `DialContext error: dial tcp 198.18.0.x:7844: i/o timeout`，重试永不成功 |
| 根因 A（实测定位） | **该网络对 Cloudflare 隧道边缘网段做了阻断**：`region1/2.v2.argotunnel.com` 的 **443 与 7844 全部超时**、边缘段 `198.41.192.0/24` 不可达；而 `api.cloudflare.com` **200**、`www.cloudflare.com` **200**。**关键：443 的 TCP 本身就不通，所以换 `--protocol http2` 无用**（该参数只解决 UDP/QUIC 被封，解决不了 TCP 被封）。本机无 IPv6（有 AAAA 记录但无可用 v6 地址），无法绕行 |
| 诊断要点 | 判「能不能用 Cloudflare 隧道」要**分别测 api.cloudflare.com 与 region*.v2.argotunnel.com**——前者通不代表后者通。早先能连是走 Mihomo 的 fake-IP 转发绕过去的，DNS 一改回真实 IP 直连即死 |
| 现象 B | localhost.run 隧道跑十几分钟后进程退出，报 `Received disconnect: tunnel activity timeout` |
| 根因 B | 免费隧道按**真实 HTTP 流量**判空闲。**SSH 层 keepalive（`ServerAliveInterval`、`TCPKeepAlive=yes`）不算隧道活动**——设了也照踢 |
| 绕行做法 B | 写守护脚本：每 45 秒对隧道公网域名打一次真实 GET（保活）+ 断线自动重连（指数退避）。实测连续 13 分钟以上不掉线。注意**重连会换新域名**，需把当前域名落盘供读取 |
| **但要先验证速度** | 保活只解决「断不断」，**不解决「快不快」**。本次实测：本机出口上行 ≥1 MB/s（直连），经 SSH 隧道只有 **14–26 KB/s**——**慢约 50 倍**，5 GB 要传 70 小时以上，方案实际不成立。瓶颈是「SSH 隧道 = TCP over TCP + 跨境高延迟」（到边缘 RTT ≈ 205 ms），**不是本机带宽**。教训：**建隧道后必须实测吞吐，别只验证「能打开」** |
| 备选通道实测（同一网络） | `ssh.localhost.run:443` ✅ 可连（但慢）；`a.pinggy.io:443` 可连但**要公钥**；`eu.tunnel.pyjam.as:443` 可连但**要公钥且需网页注册**；`serveo.net` **DNS 被污染**；`github.com` / `google.com` 直连不通（须走代理）。**免费且免注册的隧道基本都慢或要密钥**，这是客观约束 |
| 规则落点 | 本页 |

## 视觉链路验证记录（2026-09-18）

用 800×600 合成图（真值：红方块 / 绿圆 / 蓝方块 + 4 行文字）实测三条路径：

| 路径 | 结果 | 文字准确率 | 耗时 |
|---|---|---|---|
| 云端强模型直接读图 | 图形顺序、4 行文字、右下黑点与横线**全对** | 逐字正确 | — |
| 本地原生 `/api/chat` + qwen2.5vl:7b | 看到图，但**编造** `A7=红方块` 映射、漏抄 1 行 | 部分 | 26.7s |
| 本地 OpenAI 兼容端点 + qwen2.5vl:7b | 同上（同样编造） | 部分 | 8.8s |
| **DSH 路由（`read_image` → ollama）** | 图形顺序、4 行文字、右下黑点与横线**全对** | 逐字正确 | — |

**结论**：
1. DSH 的 Ollama 视觉链路可用——`read_image` → agent loop → `ollama` 路由 → `qwen2.5vl:7b` 端到端跑通。
2. 该路由**无需配置 API key**：`OLLAMA_API_KEY` 不存在时仍正常服务（实测连续两次成功）。Ollama 服务端对空 `Authorization` 与任意 Bearer 均返回 200。
3. 但坑 6 的准确率问题是真的——**同一张图，本地模型会编造，云端不会**。故"看图"要不要下沉到本地，取决于识别错误的代价，不是取决于链路通不通。

## 相关页面

- [[local-ai]] — 本地 AI（Ollama + Qwen2.5）配置与云端分工表
- [[mimo-review]] — 独立 AI 审查流程（跨 AI 纠错）
- [[file-organizer]] — 文件整理代理（含 GBK 控制台注意点）
- [[sop-v1.1]] — 环境与踩坑规则的唯一事实源

## 变更历史

| 日期 | 变更 | 原因 |
|------|------|------|
| 2026-09-18 | 初始化 | 沉淀 AI 协作工具链经验（DSH 全局准则落点 + 实测坑清单） |
| 2026-09-18 | 补充 | 坑 5 修正（OpenAI 兼容端点图片可过、仅 tools 被丢）+ 新增坑 6（本地视觉模型编造）/ 坑 7（read 不吃图）+ 视觉链路验证记录 |
| 2026-09-18 | 补充 | 新增坑 8（git core.autocrlf 静默改写行尾，system 级默认 true）+ 坑 9（pwsh 校验脚本四个高频自伤动作）；主库已上 git（见 [[sop-v1.1]] 之外的 log.md 2026-09-18 条目） |
| 2026-09-21 | 更正 | 坑 5 作废：用原测法复测，OpenAI 兼容端点带 `tool_choice: required` 现返回 `tool_calls=1`（原记 0 个），该问题在 Ollama 0.34.2 上不复现；保留原观测并标注。新增模型侧限制：`qwen3:30b-a3b` 实测不产生工具调用。同批补充：该模型必须用 `num_gpu 0` 变体（否则自动 offload 到 8 GB 显存致 CUDA OOM / HTTP 500），纯 CPU 实测 19.5 tok/s；模型库迁至 G 盘 |
| 2026-10-08 | 新增 | 坑 10（Ollama 打包：`show --modelfile` 输出无法回灌的两条语法约束；`/api/create` 不吃本地 GGUF 路径；硬链接不会被写透已实测）+ 坑 11（`http.server` 不支持 Range 需自实现 206；cloudflared 在 Mihomo fake-IP 下必须 `--protocol http2`）。来源：打包 `tongnai-nsfw` 分享给他人 |
| 2026-10-08 | 新增 | 坑 12（当晚链接两次失效的根因：**该网络阻断 Cloudflare 隧道边缘网段**，`region*.v2.argotunnel.com` 的 443/7844 全超时而 `api.cloudflare.com` 正常，故 `--protocol http2` 无用；免费隧道按真实 HTTP 流量踢空闲连接，**SSH keepalive 不算活动**）。并记一条方法教训：**建隧道后必须实测吞吐**——本次保活成功了，但 SSH 隧道只有 14–26 KB/s（本机上行 ≥1 MB/s），5 GB 要传 70 小时，方案实际不成立 |
