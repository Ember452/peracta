# CLAUDE.md

本项目**完整的协作准则、权限红线与质量约束在 [AGENTS.md](AGENTS.md)**。
本文只是入口指针 + Claude Code 相关补充。**权威来源是 AGENTS.md，冲突以它为准。**

@AGENTS.md

---

## 红线兜底

> 本节**只保留三条不可协商项**，仅当上方 `@AGENTS.md` 导入未生效时才需要看这里。
> 其余一切规则**不在本文复述**（避免双源漂移）—— AGENTS.md 是唯一权威来源。
> 本节只在 AGENTS.md 的红线本身变化时才动。

1. **未经用户明确指令，绝不 commit / push / 打 tag / 发布 PyPI。**"改好了" **不等于**许可。
2. **运行时依赖 0 个**；新增依赖必须先获批准。
3. **禁止跳过 pre-commit hook**；禁止 `git add -A` / `--force` / `git reset --hard` / 改写历史。

---

## Claude Code 相关补充

- 探索环境用 `uv run python -c "..."`，**不要 `pip install`**，不要手写 venv 路径
- **不要修改 `.venv/`**；不要手改 `uv.lock`（用 `uv add` / `uv lock`）
- pre-commit hook 失败**必须修根因**，禁止 `--no-verify`
- 多步任务先给计划（步骤 + 每步验证命令），再动手
- 涉及 `kill -9`、进程注入、临时目录写入的集成测试，注意 Windows 与 POSIX 的差异
  （本项目需跨平台：Windows / macOS / Linux）
- 长会话中若怀疑上下文过期，**重新读文件再改**，不要凭记忆编辑
