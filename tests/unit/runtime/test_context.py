"""runtime.context：`Context.step` 的记录、重放与失败语义。

本文件是"已完成的工作绝不重做"的最小证据面：重放命中必须既**不调用** `fn`、
也**不写**任何事件，而崩在中途的步骤必须重新执行。
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from peracta.core.clock import FixedClock
from peracta.core.errors import (
    DuplicateStepNameError,
    RunNotFoundError,
    StepResultNotSerializableError,
)
from peracta.core.events import EventKind
from peracta.journal.sqlite_store import SqliteJournal
from peracta.journal.store import RunRecord
from peracta.runtime.context import Context

CLOCK = FixedClock(datetime(2026, 1, 1, tzinfo=UTC))
RUN_ID = "run_1"


def _open(path: Path) -> SqliteJournal:
    """打开日志并写入一条 runs 行：事件受外键约束，没有 run 行就写不进任何事件。"""
    journal = SqliteJournal(path)
    stamp = CLOCK.now().isoformat()
    journal.create_run(
        RunRecord(
            run_id=RUN_ID,
            flow_name="demo",
            status="running",
            created_at=stamp,
            updated_at=stamp,
            inputs={},
        )
    )
    return journal


def _context(journal: SqliteJournal, replay: dict[str, Any] | None = None) -> Context:
    return Context(store=journal, run_id=RUN_ID, clock=CLOCK, replay=replay)


def _explode() -> int:
    """任何被真正执行的步骤都会撞上它 —— 用它证明重放路径没有调用 `fn`。"""
    raise AssertionError("a replayed step must not execute its body")


def test_step_returns_the_value_and_records_started_then_completed(journal_path: Path) -> None:
    with _open(journal_path) as journal:
        context = _context(journal)

        assert context.step("first", lambda: 21 * 2) == 42

        events = journal.load_events(RUN_ID)

    # 顺序、步骤名与载荷都是续跑的证据面，缺一不可
    assert [(event.kind, event.step_name) for event in events] == [
        (EventKind.STEP_STARTED, "first"),
        (EventKind.STEP_COMPLETED, "first"),
    ]
    assert events[1].payload == {"result": 42}
    assert events[0].created_at == CLOCK.now().isoformat()


def test_replayed_step_returns_the_recorded_value_and_writes_nothing(journal_path: Path) -> None:
    with _open(journal_path) as journal:
        context = _context(journal, replay={"first": 42})

        assert context.step("first", _explode) == 42

        # 该 run 一条事件都没有：`load_events` 对空事件流抛 RunNotFoundError。
        # 这条断言是"重放不写日志"的唯一可反驳代理 —— 若重放顺手补写事件，它会红。
        with pytest.raises(RunNotFoundError):
            journal.load_events(RUN_ID)


def test_replayed_step_name_still_counts_as_used(journal_path: Path) -> None:
    # 重放命中的名字同样"已经出现过"：否则续跑里重名步骤会被静默处理两次
    with _open(journal_path) as journal:
        context = _context(journal, replay={"first": 42})

        assert context.step("first", _explode) == 42
        with pytest.raises(DuplicateStepNameError):
            context.step("first", _explode)


def test_duplicate_step_name_in_the_same_context_is_rejected(journal_path: Path) -> None:
    with _open(journal_path) as journal:
        context = _context(journal)
        assert context.step("twice", lambda: 1) == 1

        with pytest.raises(DuplicateStepNameError):
            context.step("twice", lambda: 2)

        # 被拒的第二次调用不得留下任何 STEP_STARTED
        assert [event.step_name for event in journal.load_events(RUN_ID)] == ["twice", "twice"]


def test_non_serializable_result_is_rejected_without_a_completion_event(
    journal_path: Path,
) -> None:
    with _open(journal_path) as journal:
        context = _context(journal)

        with pytest.raises(StepResultNotSerializableError):
            context.step("bad", lambda: object())

        # STEP_STARTED 已经写下了（这次尝试是历史事实），但绝不允许写 STEP_COMPLETED
        assert [event.kind for event in journal.load_events(RUN_ID)] == [EventKind.STEP_STARTED]


def test_current_step_starts_as_none(journal_path: Path) -> None:
    with _open(journal_path) as journal:
        assert _context(journal).current_step is None


def test_current_step_is_visible_inside_the_step_and_restored_on_return(
    journal_path: Path,
) -> None:
    with _open(journal_path) as journal:
        context = _context(journal)
        observed: list[str | None] = []

        def body() -> int:
            observed.append(context.current_step)
            return 1

        context.step("first", body)

    assert observed == ["first"]
    assert context.current_step is None


def test_current_step_keeps_the_failing_step_name(journal_path: Path) -> None:
    # 对原计划的有意修正：抛异常时不恢复 current_step，执行器才能把失败记到具体步骤上
    def boom() -> int:
        raise RuntimeError("boom")

    with _open(journal_path) as journal:
        context = _context(journal)
        assert context.step("first", lambda: 1) == 1

        with pytest.raises(RuntimeError):
            context.step("second", boom)

        assert context.current_step == "second"


def test_run_id_is_read_only(journal_path: Path) -> None:
    with _open(journal_path) as journal:
        context = _context(journal)

        assert context.run_id == RUN_ID
        with pytest.raises(AttributeError):
            context.run_id = "run_2"
