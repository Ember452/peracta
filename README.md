# Peracta · 毕录

**给 AI Agent 的持久化执行内核 —— 已完成之事，不可重做。**

中文 ｜ [English](README.en.md)

> 崩溃后从断点续跑，副作用恰好一次，任何一次运行都能逐字节重放。
> 每一步都留下凭据 —— 不是"我们保证"，而是"这是我们观测到的"。

## 目标态一览

**V0.1 · 单机内核（按计划完成后）：**

<video src="docs/assets/v01-target-panel.mp4" controls muted loop autoplay playsinline></video>

*图：V0.1 目标架构。左侧"崩溃演练"依次点亮：kill -9 续跑 0 重跑、effect 重复调用命中缓存、未知态进对账；右侧是 L0–L5 分层内核与 SQLite 事件日志。动画数字为模拟值。*

**V1.0 · 全部扩展完成后：**

<video src="docs/assets/v10-vision-panel.mp4" controls muted loop autoplay playsinline></video>

*图：V1.0 愿景。入口面（Claude Code / Qoder / MCP / CLI / CI）→ 框架适配器 → 零依赖同步内核 → 多存储后端 → 平台件（静态扫描 / 沙箱 / 人工仲裁）。deps=0 与 dups=0 是两张图共同的不变量。*

> 视频打不开？看静态图：[V0.1](docs/assets/v01-target-panel.png) · [V1.0](docs/assets/v10-vision-panel.png)

## 问题：AI Agent 的执行缺口

一个能改数据、发邮件、花钱的 Agent，崩溃重跑时会发生什么？

| 场景 | 后果 |
|---|---|
| 第 3 步被 `kill -9`，从头重跑 | 前两步的副作用再来一次：重复退款、重复发信 |
| effect 已发出、确认未落盘时崩溃 | 状态未知：这笔退款到底发没发，没人说得清 |
| 长跑 Agent 失败重试 | 重烧一遍 token 与钱，且无据可查 |

Temporal / Restate 给你"不会重跑"；**Peracta 给你"证明没有重复产生副作用"** —— 靠故障注入验证器，而且它必须先在故意坏掉的反例上证明自己能发现问题。

## 四条承诺

| # | 承诺 |
|---|---|
| 0 | **只声明观测到的事实** —— 缺失证据显式标注，不编造健康分 |
| 1 | 已完成的步骤不重跑 |
| 2 | 已提交的副作用恰好一次 |
| 3 | 任何一次运行可确定性重放 |

## 设计中的 API（V0.1 锁定，同步优先）

```python
from peracta import flow

@flow
def refund_agent(ctx):
    order = ctx.step("fetch_order")
    with ctx.effect(key=f"refund:{order.id}", reconcile=query_refund):
        gateway.refund(order)   # 崩溃重启后：已提交的不再执行
```

```bash
peracta run examples/refund_agent.py                        # A1 正常跑完
peracta resume <run-id>                                     # A2 崩溃后：已完成步骤不重跑
peracta replay <run-id>                                     # A5 逐字节重放
peracta verify examples/refund_agent.py --fault crash --at every-step --repeat 50
                                                            # A3 重复副作用必须为 0
```

> ⚠️ 以上是 V0.1 锁定的目标接口，**尚未实现** —— 进度见下方状态表。

## 与现有方案的关系

| | Temporal / Restate | LangGraph / crewAI | actenon-scan | Peracta |
|---|---|---|---|---|
| 已完成步骤不重跑 | ✅ | 部分 | — | ✅ |
| 副作用恰好一次 | 需自行实现 | ❌ | — | ✅ |
| 确定性重放整次运行 | 仅 workflow code | ❌ | — | ✅ |
| 故障注入证明"没重复" | ❌ | ❌ | 静态扫描 | ✅ |
| 零运行时依赖 | ❌ | ❌ | ✅ | ✅ |

## 工程约束（硬的）

- **运行时依赖 0 个**：Python 3.13 标准库；存储用标准库 `sqlite3`
- 零依赖是**测试断言**，不是 README 口号（`tests/architecture/` 架构守卫）
- 分层依赖单向（L0–L5），由测试强制；文档与代码同步，决策记录两级制（changelog + ADR）

## 当前状态

**本仓库目前没有可运行的代码 —— 这是有意的：先锁约束，再写内核。**

| 任务卡 | 内容 | 状态 |
|---|---|---|
| T1 | 骨架：pyproject / src / pytest / ruff / CI | ⬜ |
| T2 | SQLite 事件日志（runs / events / claims） | ⬜ |
| T3 | step 录制 + resume 跳过已完成步骤 | ⬜ |
| T4 | effect 幂等（先留凭据）+ reconcile 未知态 | ⬜ |
| T5 | verify 故障注入 + 故意坏掉的反例 | ⬜ |

已完成：V0.1 定义与结构锁定（四份规格文档）、目标态面板图、协作准则。

## 文档

| 文档 | 内容 |
|---|---|
| [PROJECT.md](docs/PROJECT.md) | **约束**：V0.1 做什么、不做什么、怎么验收（A1–A6） |
| [FEATURES.md](docs/FEATURES.md) | **全景**：整体构想，不做取舍 |
| [STRUCTURE.md](docs/STRUCTURE.md) | **结构**：目录、分层、依赖方向 |
| [EXTENSIONS.md](docs/EXTENSIONS.md) | **扩展**：未来方向灵感库（含 actenon-scan / better-harness 借鉴清单） |

## 许可证

MIT。面板动图由 [live-panel skill](https://github.com/ythx-101/live-panel-skill) 生成，配置源与视频在 [docs/assets/](docs/assets/)。
