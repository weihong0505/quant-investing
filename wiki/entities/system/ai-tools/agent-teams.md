---
title: Agent Teams 能力与《AI 通用准则》对标
created: 2026-09-19
updated: 2026-09-19
type: entity
tags: [system, tool]
sources: [G:/AI-通用准则.md, G:/deeeseek/agent-teams-vs-准则/AGENT-TEAMS-对标-通用准则v1.3.md, G:/deepseek-harness/docs/subsystems/agent-team.zh.md]
confidence: 85
---

# Agent Teams 能力与《AI 通用准则》对标

DSH 的 Agent Teams 是**本机 `web` profile 当前唯一的模型委派路径**（旧 `tool-subagent*` 四个控件已被 `agent-team-profile` 补丁禁用），因此「准则里哪些纪律能靠机制兜住」这件事必须先看清它的能力边界。**准则条款本体以 [[sop-v1.1]] 与 `G:/AI-通用准则.md` v1.3 为唯一事实源，本页只做映射、不复制条款文字。**完整版见工作区 `G:\deeeseek\agent-teams-vs-准则\AGENT-TEAMS-对标-通用准则v1.3.md`。

## 是什么（一手核实）

| 项 | 事实 | 依据 |
|---|---|---|
| 形态 | Root 会话即隐式 Team 的 Lead，可建具名 teammate；**九个工具**：`spawn_teammate` / `send_message` / `list_agents` / `wait_agent` / `interrupt_agent` / `team_task_*`（5 个） | 子系统页 + 包 README |
| 持久化 | 单一真源是 Lead 会话日志（`team/member`、`team/task`、`team/message/queued|delivered`）；这些事件**不进模型历史** | Agent Note「持久性模型」 |
| 投递 | `send_message` 恒为 Steer：running 在步骤边界接收 / idle 起一轮 / inactive 冷恢复；`accepted` 与 `queued` 都表示已安全落盘，**禁止重发** | agent-team README |
| 任务板 | 完整快照 + 单调 `revision` 的 CAS；`blocked_by` 未完成不能 claim；`writeScopes` **仅告警、不是锁** | 同上 |
| 本机参数 | `maxMembers: 8`、`maxTasks: 256`、每成员待发 64 条、单条 64 KB、清理 5 s | `agent-team-profile/cordis.patch.yml` |
| 启用条件 | 固定策略：**只有用户明确要求 Agent Teams / teammate 才建队** | tool-agent-team README |

## 对标结论：强制力四档

| 档位 | 准则条目 | 说明 |
|---|---|---|
| 工具层强制 | §1 并行、§6a 独立上下文、§6b 依赖排序、§7 开工前钉死 | 违反即报错/拒绝/返回特定状态 |
| 结构性支持 | §2 落点、§5 复盘、§10 留痕 | 结构在位，仍需主动使用 |
| 完全不覆盖 | §3 成本分流、§4 知识入库、§9 防过拟合、§11 维护 | 与机制无关，照旧人工 |
| 反向加压 | §7、§8 隐私、§12 时间 | 不主动补就直接踩坑 |

## 反向加压的三处（本页最有价值的部分）

1. **§12 时间校准在团队内失效**：fresh teammate 不继承 Lead 对话历史 → 开场校准的时间传不过去；**必须把当前时间写进每个成员的初始任务**，否则成员会按错误日期判断时效。
2. **§12/§6 的上下文选择是硬开关**：审查方必须 `context: fresh`（fork 会把 Lead 的推理一起继承，正好违反 §6「不复用同一段推理」）；反之需要 Lead 上下文的任务才用 fork。
3. **§8 隐私落盘面翻倍**：peer 消息进 target 历史、任务板快照进 Lead 日志 → **个人数据不进消息正文、不进任务板**；成员沙箱与权限和 Lead 相同（会话级 `danger-full-access`，无 per-member 分层），收窄只能靠少写。

## 机制不管、必须人工守的四件事

- `writeScopes` 不是锁：Bash / formatter / codegen / 外部写入**绕过**文件陈旧版本校验。
- **owner 永不自动释放**：idle、被 interrupt、进程退出、工作失败，owner 都还在。
- 成员是**各自的完整上下文**：省的是 Lead 上下文，不是总 token（Team 成本是乘法）。
- 最终 diff 检查与测试**是 Lead 不可外包的集成边界**。

## 操作坑（实测/文档核实）

- `wait_agent` 在无成员 running/provisioning 时**立即返回 `noProgress`** → 正确顺序是先 `send_message` 唤醒，再 `wait_agent`。
- `wait_agent` **不回放更早的边** → 唤醒或超时后必须 `list_agents` + `team_task_list` 重读权威状态。
- 具名 roster 扁平且不可变：**名字永久保留、失败也占坑、不复用**（上限 8）→ 建队前先想清职责边界，目标/验收标准不稳时**先单人不建队**。
- `interrupt_agent` 只取消当前轮次，**保留 inbox 与任务归属**。

## 与另外两种并行机制的分工

| 维度 | 一次性 subagent（本机已禁用） | Workflow 脚本 | Agent Teams |
|---|---|---|---|
| 身份/存活 | 匿名、一次性 | 脚本内匿名 | 持久具名，跨崩溃与冷恢复 |
| 成员互通 | 否 | 否 | **是** |
| 共享任务板 | 无 | 脚本内 phase | **有**（owner/revision/依赖） |
| 准则归属 | §1 轻量并行 | §1 大规模 fan-out | §1 需协调与留痕的并行 |

**口径：只要结论 → subagent/workflow；需要成员互相说话、需要留痕与可审计的对抗审查 → Agent Teams。**

## 关联

- [[ai-toolchain-notes]] — DSH 工具链坑清单与规则落点（SOP §1.2 等）
- [[dsh-plugin-internals]] — 常驻子代理唤醒父代理、工具过滤方向、会话日志多帧 zstd
- [[dsh-tool-presentation-modes]] — 委派时的成本曲线与任务措辞模板
- [[sop-v1.1]] — 准则与本页引用的规则事实源
