"""`SqliteJournal` 集成测试：全部跑在 `tmp_path` 下的真实文件上，不使用任何替身。

本文件是 Task 4「崩溃后续跑」的地基：写进日志的东西必须能被另一个进程逐字读回来。
因此这里宁可另外开一个 `sqlite3` 连接去核对落盘内容，也不放松任何断言。
"""

from __future__ import annotations

import inspect
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from peracta.core.errors import RunNotFoundError, SchemaError
from peracta.core.events import EventKind
from peracta.journal.schema import SCHEMA_VERSION
from peracta.journal.sqlite_store import SqliteJournal
from peracta.journal.store import JournalStore, RunRecord

STAMP = datetime(2026, 1, 1, tzinfo=UTC).isoformat()
LATER = datetime(2026, 1, 2, tzinfo=UTC).isoformat()

_METHODS = ("create_run", "append_event", "load_events", "get_run", "set_run_status", "list_runs")


def _record(run_id: str = "run_1", created_at: str = STAMP) -> RunRecord:
    """最小可用的运行记录；inputs 刻意嵌套，用来验证 JSON 往返而非只比浅层。"""
    return RunRecord(
        run_id=run_id,
        flow_name="demo",
        status="running",
        created_at=created_at,
        updated_at=created_at,
        inputs={"n": 3, "nested": {"tags": ["a", "b"]}},
    )


def _raw(journal_path: Path, sql: str) -> list[tuple]:
    """用一条独立连接读原始行 —— 绕开被测代码，核对真正落盘的内容。"""
    conn = sqlite3.connect(journal_path)
    try:
        return conn.execute(sql).fetchall()
    finally:
        conn.close()


def test_appends_and_reads_events_in_seq_order(journal_path: Path) -> None:
    with SqliteJournal(journal_path) as journal:
        journal.create_run(_record())
        first = journal.append_event("run_1", EventKind.RUN_STARTED, None, {"flow": "demo"}, "t1")
        second = journal.append_event("run_1", EventKind.STEP_STARTED, "first", {}, "t2")

        events = journal.load_events("run_1")

    assert [event.seq for event in events] == [first.seq, second.seq]
    assert first.seq < second.seq
    # append_event 的返回值就是刚持久化的那条事件，字段逐字一致
    assert events[0] == first
    assert events[1] == second
    assert [event.kind for event in events] == [EventKind.RUN_STARTED, EventKind.STEP_STARTED]
    assert [event.step_name for event in events] == [None, "first"]
    assert events[0].payload == {"flow": "demo"}
    assert events[0].created_at == "t1"


def test_run_and_events_survive_reopening_the_file(journal_path: Path) -> None:
    with SqliteJournal(journal_path) as journal:
        journal.create_run(_record())
        journal.append_event("run_1", EventKind.RUN_STARTED, None, {"flow": "demo"}, STAMP)
        assert journal_path.exists()

    # 真的关掉再打开：这条断言测的是文件里的内容，不是进程内的缓存
    with SqliteJournal(journal_path) as reopened:
        run = reopened.get_run("run_1")
        events = reopened.load_events("run_1")

    assert run is not None
    assert run.flow_name == "demo"
    assert run.status == "running"
    assert run.created_at == STAMP
    assert run.updated_at == STAMP
    assert run.inputs == {"n": 3, "nested": {"tags": ["a", "b"]}}
    assert run.result is None
    assert len(events) == 1
    assert events[0].kind is EventKind.RUN_STARTED
    assert events[0].payload == {"flow": "demo"}


def test_load_events_rejects_an_unknown_run(journal_path: Path) -> None:
    with SqliteJournal(journal_path) as journal, pytest.raises(RunNotFoundError):
        journal.load_events("run_missing")


def test_load_events_rejects_a_run_without_any_event(journal_path: Path) -> None:
    # run 存在但一条事件都没写（例如 Task 4 的重放路径）：同样按"查无此事"处理，
    # 否则续跑会拿到空事件列表，进而被 build_run_state 以 ValueError 拒绝
    with SqliteJournal(journal_path) as journal:
        journal.create_run(_record())

        with pytest.raises(RunNotFoundError):
            journal.load_events("run_1")


def test_set_run_status_persists_the_result_across_reopen(journal_path: Path) -> None:
    with SqliteJournal(journal_path) as journal:
        journal.create_run(_record())
        journal.set_run_status("run_1", "completed", result={"answer": 42})
        assert journal.get_run("run_1") is not None

    with SqliteJournal(journal_path) as reopened:
        run = reopened.get_run("run_1")

    assert run is not None
    assert run.status == "completed"
    assert run.result == {"answer": 42}


def test_set_run_status_without_a_result_clears_the_column(journal_path: Path) -> None:
    with SqliteJournal(journal_path) as journal:
        journal.create_run(_record())
        journal.set_run_status("run_1", "failed")
        run = journal.get_run("run_1")

    assert run is not None
    assert run.status == "failed"
    assert run.result is None


def test_set_run_status_rejects_an_unknown_run(journal_path: Path) -> None:
    with SqliteJournal(journal_path) as journal:
        with pytest.raises(RunNotFoundError):
            journal.set_run_status("run_missing", "completed", result=1)

        assert journal.list_runs() == []


def test_get_run_returns_none_for_an_unknown_run(journal_path: Path) -> None:
    with SqliteJournal(journal_path) as journal:
        assert journal.get_run("run_missing") is None


def test_list_runs_is_newest_first_and_honours_the_limit(journal_path: Path) -> None:
    with SqliteJournal(journal_path) as journal:
        journal.create_run(_record("run_old", created_at=STAMP))
        journal.create_run(_record("run_new", created_at=LATER))

        assert [run.run_id for run in journal.list_runs()] == ["run_new", "run_old"]
        assert [run.run_id for run in journal.list_runs(limit=1)] == ["run_new"]


def test_list_runs_breaks_created_at_ties_towards_the_newest_insert(journal_path: Path) -> None:
    # 同一时刻创建的多个 run（真实时钟的精度内、或用 FixedClock 的测试）也必须让
    # 最新那一次排在最前，否则 CLI 的 --last 会挑错要继续的那一次运行
    with SqliteJournal(journal_path) as journal:
        journal.create_run(_record("run_a"))
        journal.create_run(_record("run_b"))

        assert [run.run_id for run in journal.list_runs()] == ["run_b", "run_a"]


def test_event_kind_is_persisted_as_the_wire_value(journal_path: Path) -> None:
    with SqliteJournal(journal_path) as journal:
        journal.create_run(_record())
        journal.append_event("run_1", EventKind.STEP_COMPLETED, "first", {"result": 10}, STAMP)

    rows = _raw(journal_path, "SELECT kind, payload_json FROM events")

    assert len(rows) == 1
    assert rows[0][0] == "step_completed"
    assert json.loads(rows[0][1]) == {"result": 10}


def test_each_write_is_committed_before_close(journal_path: Path) -> None:
    # isolation_level=None（逐条 autocommit）的可观测证据：日志还开着的时候，
    # 另一条连接就能读到已写入的事件 —— 这样 kill -9 才不会带走已确认的写入
    with SqliteJournal(journal_path) as journal:
        journal.create_run(_record())
        journal.append_event("run_1", EventKind.RUN_STARTED, None, {}, STAMP)

        assert _raw(journal_path, "SELECT COUNT(*) FROM events")[0][0] == 1


def test_file_is_left_in_wal_mode(journal_path: Path) -> None:
    with SqliteJournal(journal_path) as journal:
        journal.create_run(_record())

    assert _raw(journal_path, "PRAGMA journal_mode")[0][0] == "wal"


def test_schema_version_and_both_tables_are_recorded_in_the_file(journal_path: Path) -> None:
    with SqliteJournal(journal_path) as journal:
        journal.create_run(_record())

    assert _raw(journal_path, "PRAGMA user_version")[0][0] == SCHEMA_VERSION
    tables = {
        row[0] for row in _raw(journal_path, "SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    assert {"runs", "events"} <= tables


def test_event_for_an_unknown_run_is_rejected_by_the_foreign_key(journal_path: Path) -> None:
    # events.run_id REFERENCES runs(run_id) 加上 PRAGMA foreign_keys = ON：
    # 没建 run 就写事件必须被数据库拒绝，而不是留下一条无主事件
    with SqliteJournal(journal_path) as journal, pytest.raises(sqlite3.IntegrityError):
        journal.append_event("run_missing", EventKind.RUN_STARTED, None, {}, STAMP)


def test_constructor_creates_missing_parent_directories(tmp_path: Path) -> None:
    nested = tmp_path / "nested" / "deeper" / "journal.sqlite"

    with SqliteJournal(nested) as journal:
        journal.create_run(_record())

    assert nested.exists()


def test_schema_newer_than_this_build_is_rejected(journal_path: Path) -> None:
    conn = sqlite3.connect(journal_path)
    try:
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION + 1}")
    finally:
        conn.close()

    with pytest.raises(SchemaError):
        SqliteJournal(journal_path)


def test_journal_store_protocol_declares_exactly_the_six_methods() -> None:
    declared = {
        name
        for name, value in vars(JournalStore).items()
        if not name.startswith("_") and callable(value)
    }

    assert declared == set(_METHODS)


def test_sqlite_journal_signatures_match_the_protocol() -> None:
    for name in _METHODS:
        assert inspect.signature(getattr(SqliteJournal, name)) == inspect.signature(
            getattr(JournalStore, name)
        ), f"{name} drifted from JournalStore"
