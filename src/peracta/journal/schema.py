"""日志的 SQLite schema：两张表的定义只此一处。

改 DDL 就必须抬 `SCHEMA_VERSION`。`ensure_schema` 用 `PRAGMA user_version` 判断磁盘上
的日志是不是本内核读得懂的版本：比本内核新的日志宁可拒绝打开，也不要用旧代码去猜新
格式 —— 猜错的代价是静默读坏历史，而历史是重放的唯一依据。
"""

from __future__ import annotations

import sqlite3

from peracta.core.errors import SchemaError

SCHEMA_VERSION = 1

# `runs` 是每次运行的元数据，`events` 是只追加的事实流。两边的列名都是持久化格式，
# 一旦发布就不得再改（只能抬版本号后迁移）。
_DDL = """
CREATE TABLE IF NOT EXISTS runs (
    run_id      TEXT PRIMARY KEY,
    flow_name   TEXT NOT NULL,
    status      TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    inputs_json TEXT NOT NULL,
    result_json TEXT
);

CREATE TABLE IF NOT EXISTS events (
    seq          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id       TEXT NOT NULL REFERENCES runs(run_id),
    kind         TEXT NOT NULL,
    step_name    TEXT,
    payload_json TEXT NOT NULL,
    created_at   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_events_run ON events(run_id, seq);
"""


def ensure_schema(conn: sqlite3.Connection) -> None:
    """把 `conn` 上的日志库补齐到 `SCHEMA_VERSION`。

    只做加法：`CREATE ... IF NOT EXISTS` 对已建好的库是空操作，所以重复调用是安全的。
    磁盘版本高于本内核时抛 `SchemaError`；低于本版本时（含全新的空库，其
    `user_version` 为 0）建表并把版本号写回文件头部。
    """
    current: int = conn.execute("PRAGMA user_version").fetchone()[0]
    if current > SCHEMA_VERSION:
        raise SchemaError(
            f"journal schema v{current} is newer than the supported v{SCHEMA_VERSION}"
        )
    conn.executescript(_DDL)
    # PRAGMA 不接受参数占位符；SCHEMA_VERSION 是本模块的 int 常量，不存在拼接风险
    conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
