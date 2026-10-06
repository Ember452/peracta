# Peracta 项目结构

> 状态：**结构规范** ｜ 2026-10-05（§2.1 对标评审于 2026-10-06）
> 本文定义**目录与包**的布局、各层职责、依赖方向与命名约定。
> **粒度到包为止 —— 不规定包内具体文件名**，那是实现时的自由。
> 配合 [PROJECT.md](PROJECT.md)（约束）· [FEATURES.md](FEATURES.md)（全景）· [EXTENSIONS.md](EXTENSIONS.md)（扩展）

---

## 1. 五条总原则

| # | 原则 | 理由 |
|---|---|---|
| 1 | **src layout** —— 源码根是 `src/peracta/`，不在仓库根 | 防止"还没安装就 import 到本地目录"；保证测试跑的是真装出来的包 |
| 2 | **分层且依赖单向** —— `cli → verify → runtime → effect → journal → core` | 规则可被测试机械检查，不靠自觉 |
| 3 | **公共 API 只有一个出口** —— 只在包根 `peracta/__init__.py` 导出 | 导出面越小，改内部越自由；未导出即为不承诺 |
| 4 | **标准库优先，运行时依赖为 0** | 装得上、审得过，也是分发卖点 |
| 5 | **抽象与实现分离** —— 每个可变后端先有 Protocol，再有实现 | V0.2 换 Postgres / Redis 时不改内核 |

---

## 2. 目录树（包级）

```text
peracta/
├── .github/
│   ├── workflows/              # CI 矩阵 / 发布 / 安全扫描
│   ├── ISSUE_TEMPLATE/         # bug / feature / config
│   ├── PULL_REQUEST_TEMPLATE.md
│   └── dependabot.yml
│
├── docs/                       # 四份规格文档 + adr/（决策记录，首篇落地时建），清单见 PROJECT.md §7
│
├── examples/                   # 可运行示例；含一个"故意坏掉"的反例
│
├── src/
│   └── peracta/                # 唯一的源码根（src layout）
│       ├── core/               # L0 机制层：时钟、标识、事件模型、异常、结果类型
│       ├── journal/            # L1 持久化层：事件日志、快照、Schema 迁移、重放
│       ├── effect/             # L2 副作用安全层：预占、账本、对账、补偿
│       ├── runtime/            # L3 执行内核层：流程定义、上下文、执行循环、续跑
│       ├── verify/             # L4 正确性验证层：故障定义、注入、检测、报告
│       ├── cli/                # L5 命令行层：入口、子命令、退出码契约
│       ├── observability/      # 横切：结构化日志与指标
│       └── py.typed            # PEP 561 类型标记
│
├── tests/                      # 与 src 分层对应
│   ├── unit/                   # 无 IO、快
│   ├── integration/            # 真 SQLite、真进程、真 kill
│   ├── e2e/                    # CLI 端到端，对应 PROJECT.md 验收 A1–A6
│   ├── architecture/           # 依赖方向与公共 API 面守卫（含零依赖边界断言）
│   ├── adversarial/            # 不变量对抗测试："必须保持未知 / 必须报出"（EXTENSIONS.md §10.1 B6）
│   ├── corpus/                 # 故障注入语料：vulnerable/ + safe/ 成对（服务验收 A3/A4）
│   └── fixtures/               # 事件日志样本、golden 报告、故障注入种子
│
├── benchmarks/                 # 可复现性能基准（写入吞吐、恢复耗时）
├── scripts/                    # 开发辅助（一键门禁、文档一致性检查）
│
├── pyproject.toml              # 唯一配置源（构建 / 工具 / 依赖 / 入口点）
├── .python-version / uv.lock   # uv 标准工件：钉 3.13；lock 是生成物但必须提交
├── LICENSE                     # MIT
├── README.md / README.en.md    # 中英门面（V0.1 跑通后再写）
├── CHANGELOG.md                # Keep a Changelog
├── CONTRIBUTING.md
├── CODE_OF_CONDUCT.md
├── SECURITY.md
└── (根级配置) .editorconfig / .gitattributes / .gitignore / .pre-commit-config.yaml
```

### 2.1 对标检查：离"标准大项目结构"还差什么（2026-10-06 评审）

> 对照对象：成熟大型 Python 项目的通用形态（src layout + 分层包 + 测试镜像 + 单配置源 + CI/社区文件），以及 actenon-scan 的实际布局。

| 检查项 | 状态 |
|---|---|
| src layout（`src/peracta/`，测试跑的是装出来的包） | ✅ 已有 |
| 单一配置源 `pyproject.toml`（build / ruff / pytest / 入口点） | ✅ 已有 |
| uv 标准工件：`.python-version`（钉 3.13）+ `uv.lock`（生成物，必须提交） | ➕ 本次补入 |
| 测试分层镜像 src：unit / integration / e2e / architecture / fixtures | ✅ 已有 |
| 对抗测试层 + 成对故障语料层（对标 actenon-scan `tests/adversarial/` + `tests/corpus/`，服务验收 A3/A4） | ➕ 本次补入 |
| CI 工作流 + 社区文件（Issue/PR 模板、SECURITY、CONTRIBUTING…） | ✅ 已按 §6 时序分阶段 |
| 版本单一来源 + `__version__` 派生 | ➕ 本次补入（§7） |
| 决策记录 `docs/adr/`（轻量 ADR，随代码增长，不占规格文档名额） | ➕ 本次补入（AGENTS.md §4.6 / PROJECT.md §7） |
| 架构守卫测试强制依赖方向 | ✅ 已有（`tests/architecture/`） |
| Makefile / tox / nox | ❌ 有意不要：`uv` 是唯一入口（§8） |
| 文档站 / `.devcontainer` / Docker / 为未来预留的空目录 | ❌ 有意不要（§8） |

**结论**：本结构与成熟大型 Python 项目的标准形态一致，缺的只有 ➕ 三项，已补入对应小节。"适合"比"全"重要 —— 两个 ❌ 是大项目标配里**刻意不抄**的部分，理由见 §8。

---

## 3. 各包职责（为什么它必须独立存在）

| 包 | 层 | 职责 | 为什么不能合并 |
|---|---|---|---|
| `core` | L0 | 时钟、标识生成、事件模型、异常层级、结果类型 | 全部机制层的地基；**可注入时钟是确定性重放的前提**，必须独立可测 |
| `journal` | L1 | 事件日志追加、快照、Schema 版本迁移、从日志重建状态 | 存储是唯一会换实现的部件（SQLite → Postgres → 服务）；隔离后换后端不动内核 |
| `effect` | L2 | 预占状态机、账本、幂等键规范化、未知态对账、补偿 | "恰好一次"的全部性质都在这里；独立成包才能单测穷尽状态机 |
| `runtime` | L3 | 流程定义、执行上下文、执行循环、断点续跑、非确定性录制开关 | 用户唯一接触的 API 面；与存储/验证解耦后才能独立演进 |
| `verify` | L4 | 故障定义、注入器、重复副作用检测、报告生成 | 差异化核心；依赖 runtime 只为驱动流程，**runtime 绝不反向依赖 verify** |
| `cli` | L5 | 命令行入口、子命令、退出码契约 | 唯一的进程边界；把 argparse 与业务逻辑隔开 |
| `observability` | 横切 | 结构化日志、指标 | 只被依赖、不依赖上层；避免日志代码渗进内核 |

---

## 4. 依赖方向（单向，由测试强制）

```
L0 core ──────────┐
                  ├─▶ L1 journal ──▶ L2 effect ──▶ L3 runtime ──▶ L4 verify ──▶ L5 cli
     observability│（横切：只允许被依赖）
```

**规则**：

- 只允许**高编号依赖低编号**（`cli` 可用 `runtime`；`runtime` 绝不能 import `cli`）
- **同层之间禁止横向依赖**
- `observability` 只被依赖，自己不依赖上层
- 违反即测试失败 —— 在 `tests/architecture/` 用 AST 扫描 import 语句实现

---

## 5. 分层的边界（放什么 / 不放什么）

| 包 | 放 | 不放 |
|---|---|---|
| `core` | 与业务无关的机制、纯函数、数据模型 | 任何 IO、任何存储细节、任何 CLI 逻辑 |
| `journal` | 存储协议与实现、Schema、重放逻辑 | 副作用语义、流程语义 |
| `effect` | 预占与账本状态机、键规范化、对账与补偿 | 存储实现、流程调度 |
| `runtime` | 流程与上下文 API、执行循环、续跑 | 直接写 SQL、直接读文件、直接打日志到 stdout |
| `verify` | 故障模型、注入、检测、报告 | 修改被测流程本身 |
| `cli` | 参数解析、终端输出、退出码 | 任何可被库用户复用的业务逻辑 |
| `observability` | 日志与指标封装 | 被任何上层包反向依赖 |

**判断规则**：当一个包想 import 上层包时，说明职责放错了位置 —— 改结构，不要放宽依赖。

---

## 6. 落地时序（"该有的都有" ≠ 一次全建）

| 阶段 | 落地内容 |
|---|---|
| **T1（现在）** | 仓库骨架、`pyproject.toml` 配置、uv 工件（`.python-version` / `uv.lock`）、`src/peracta/` 的包骨架、`tests/architecture/` 的依赖方向守卫、`tests/` 分层骨架、`.gitignore` / `.editorconfig` / `.pre-commit-config.yaml`、CI 工作流、LICENSE |
| **T2–T5（内核）** | `core` → `journal` → `effect` → `runtime` → `verify` → `cli` 逐层填实；`examples/`、`benchmarks/`、`tests/unit|integration|e2e` 同步补齐 |
| **发布前** | README 中英、CHANGELOG、CONTRIBUTING、SECURITY、CODE_OF_CONDUCT、Issue/PR 模板、Dependabot、发布工作流 |
| **有外部贡献者后** | CODEOWNERS、文档站、安全扫描工作流、多语言 README |

**T1 只建第一行。** 一次性把社区文件全建出来，就是"仪式比代码多"的另一种形态。

---

## 7. 命名与约定

| 项 | 约定 |
|---|---|
| 分支 | `main` 受保护；特性分支 `feat/xxx`、`fix/xxx` |
| 提交 | Conventional Commits（英文） |
| 版本 | SemVer；T1–T5 打里程碑 tag `v0.1.0-t1` … `v0.1.0-t5`，V0.1 可用后打 `v0.1.0`。**pyproject.toml 是版本唯一来源**：代码里用 `importlib.metadata.version("peracta")` 派生 `__version__`，禁止双写 |
| 包命名 | 小写、单数、按能力命名。**禁止 `utils` / `helpers` / `common`** |
| 测试命名 | `tests/<层>/.../test_<行为>_<条件>`；与 `src` 同构镜像。对抗测试命名 `test_<X>_remains_unknown`（断言"保持未知"而非"给出正确答案"，见 EXTENSIONS.md §10.1 B6） |
| 公共 API | 只在包根导出；新增导出需在 PR 说明理由 |
| 日志 | 结构化；禁止 `print`（CLI 终端输出除外） |
| 退出码 | `0` 成功 / `1` 发现问题 / `2` 用法或配置错误 |
| 工具链 | `uv` 唯一入口；`ruff` 负责 lint 与 format；pytest 负责测试 |

---

## 8. 明确不要的东西（防过度工程）

- ❌ `utils` / `helpers` / `common` 包 —— 具体能力才是归宿
- ❌ 多套配置源（`setup.cfg` / `tox.ini` / `.flake8`）—— 只留 `pyproject.toml`
- ❌ Makefile / tox / nox —— `uv` 是唯一入口，一键门禁放 `scripts/`
- ❌ 为将来预留的空包（`plugins/`、`market/`）—— 需要时再建
- ❌ 还没有第二个实现就抽接口
- ❌ `.devcontainer` / Docker 全家桶 —— V0.1 是单机标准库方案
- ❌ 文档站 —— 有外部用户后再说
- ❌ 把内部实现包变成"什么都往里塞"的垃圾桶

---

## 9. 变更记录

| 日期 | 变更 |
|---|---|
| 2026-10-05 | 初版：目录树、依赖方向、包职责、时序、命名约定 |
| 2026-10-05 | **粒度下调到包级**：移除所有具体文件名，改为「包职责 + 分层边界」两张表 |
| 2026-10-06 | 对标标准大项目结构评审（§2.1）：补 uv 工件（`.python-version` / `uv.lock`）；`tests/` 增 `adversarial/` + `corpus/` 两层；§7 增版本单一来源与对抗测试命名；§8 显式禁 Makefile / tox / nox |
