# CLAUDE.md

本项目**完整的协作准则、权限红线与质量约束在 [AGENTS.md](AGENTS.md)**。
本文只是入口指针 + Claude Code 相关补充。**权威来源是 AGENTS.md，冲突以它为准。**

@AGENTS.md

---

## 硬规则速查

> 下面这段是 AGENTS.md §2–§4 的最小复述，**故意保留**：万一上面的导入未生效，
> 这几条也必须能被读到。改动时请与 AGENTS.md 同步（只改一处）。

1. **未经用户明确指令，绝不 commit、绝不 push、绝不打 tag、绝不发布 PyPI。**
   执行前先展示 `git status` + `git diff --stat`，等用户确认。
   "改好了" **不等于**许可。
2. **commit message 一律英文**（Conventional Commits：`feat:` / `fix:` / `test:` / `docs:` / `refactor:` / `chore:`）。
   禁止 `git add -A`、`--force`、`--no-verify`、`git reset --hard`、改写历史。
3. 环境：**Python 3.13** + **uv** 管理 + **ruff**（lint/format）+ pytest。
   命令一律 `uv run ...`。
4. **运行时依赖 0 个**；新增依赖必须先说明理由并获得批准。
5. 四条门禁全绿才算完成：`ruff check` · `ruff format --check` · `pytest` · 架构守卫测试。
6. 只改必须改的；**每一行改动都要能追溯到用户的请求**。

---

## Claude Code 相关补充

- 探索环境用 `uv run python -c "..."`，**不要 `pip install`**，不要手写 venv 路径
- **不要修改 `.venv/`**；不要手改 `uv.lock`（用 `uv add` / `uv lock`）
- pre-commit hook 失败**必须修根因**，禁止 `--no-verify`
- 多步任务先给计划（步骤 + 每步验证命令），再动手
- 涉及 `kill -9`、进程注入、临时目录写入的集成测试，注意 Windows 与 POSIX 的差异
  （本项目需跨平台：Windows / macOS / Linux）
- 长会话中若怀疑上下文过期，**重新读文件再改**，不要凭记忆编辑
