"""runtime.executor：断点续跑的证明 —— 崩溃之后，已完成的工作绝不重做。

**观测面刻意放在进程内的模块级可变状态里**，由 step 回调自己累加，而不是通过
`inputs` 传一个 dict 进来计数。原因：续跑时 `inputs` 是从 `RUN_STARTED` 事件反序列化
出来的**新副本**，flow 改的是副本、断言读的是原件，测试会因为错误的原因通过 ——
那正是本项目一直在抓的"不可能失败的测试"。

同理，"这一次要不要崩"由模块级开关 `CRASH_IN_C` 控制，不能放进 `inputs`：
否则续跑会读到日志里同一份输入，然后原地再崩一次。
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from peracta.core.clock import FixedClock
from peracta.core.errors import ConfigurationError, FlowExecutionError, RunNotFoundError
from peracta.core.events import EventKind
from peracta.journal.replay import STATUS_COMPLETED, STATUS_FAILED
from peracta.journal.sqlite_store import SqliteJournal
from peracta.runtime.context import Context
from peracta.runtime.executor import RunResult, execute
from peracta.runtime.flow import flow

CLOCK = FixedClock(datetime(2026, 1, 1, tzinfo=UTC))
FLOW_NAME = "counting_flow"
OTHER_FLOW_NAME = "other_flow"

# ---- 进程级观测面：只有 step 回调真的被执行，这些值才会增长 ----
STEP_CALLS: dict[str, int] = {}
FLOW_BODY_CALLS = 0
SEEN_INPUTS: dict[str, Any] = {}
CRASH_IN_C = True


def _count(name: str, value: int) -> int:
    """在 step 回调里累加真实执行次数，并返回该步骤的持久化结果。"""
    STEP_CALLS[name] = STEP_CALLS.get(name, 0) + 1
    return value


def _step_c() -> int:
    """半途步骤：先记下自己真的跑过，再（首次运行时）抛错。

    抛错发生在回调内部，因此日志里会留下 `STEP_STARTED` 而没有 `STEP_COMPLETED`，
    正是"崩在中途"的形态 —— 续跑时它必须重新执行。
    """
    STEP_CALLS["c"] = STEP_CALLS.get("c", 0) + 1
    if CRASH_IN_C:
        raise RuntimeError("simulated crash inside step c")
    return 3


@flow(name=FLOW_NAME)
def counting_flow(ctx: Context, token: str = "") -> int:
    """三步流程，返回三个步骤结果之和。计数只在 step 回调里增长。"""
    global FLOW_BODY_CALLS
    FLOW_BODY_CALLS += 1
    SEEN_INPUTS["token"] = token
    a = ctx.step("a", lambda: _count("a", 1))
    b = ctx.step("b", lambda: _count("b", 2))
    c = ctx.step("c", _step_c)
    return a + b + c


@flow(name=OTHER_FLOW_NAME)
def other_flow(ctx: Context) -> int:
    """名字不同的另一个流程：用来证明续跑会拒绝"换一个流程接着跑"。"""
    return 99


@flow(name="body_raises_flow")
def body_raises_flow(ctx: Context) -> int:
    """在流程体里、任何 step 之外抛错：此时失败不归属于任何步骤。"""
    raise ValueError("body failed outside any step")


@pytest.fixture(autouse=True)
def _reset_process_state() -> Iterator[None]:
    """每个测试从干净的进程级观测面开始：模块级状态会跨测试互相污染。"""
    global CRASH_IN_C, FLOW_BODY_CALLS
    STEP_CALLS.clear()
    SEEN_INPUTS.clear()
    CRASH_IN_C = True
    FLOW_BODY_CALLS = 0
    yield


def test_resume_skips_completed_steps(journal_path: Path) -> None:
    """本任务的核心验收：崩在第 3 步之后续跑，前两步的真实执行计数必须仍为 1。"""
    global CRASH_IN_C

    with SqliteJournal(journal_path) as journal:
        # 第一次执行：在 c 的回调内部崩掉，模拟进程中途死亡
        with pytest.raises(FlowExecutionError) as caught:
            execute(counting_flow, journal, CLOCK, inputs={"token": "logged"})

        run_id = journal.list_runs()[0].run_id
        assert run_id == caught.value.run_id
        assert STEP_CALLS == {"a": 1, "b": 1, "c": 1}

        # 只有续跑这一次不崩；开关是模块级的，不经过日志
        CRASH_IN_C = False
        result = execute(counting_flow, journal, CLOCK, run_id=run_id)

    assert result.status == STATUS_COMPLETED
    assert result.result == 6
    assert STEP_CALLS["a"] == 1, "已完成步骤 a 不得重跑"
    assert STEP_CALLS["b"] == 1, "已完成步骤 b 不得重跑"
    assert STEP_CALLS["c"] == 2, "只有 STEP_STARTED 的半途步骤 c 必须重跑"


def test_resume_uses_the_inputs_recorded_in_the_log(journal_path: Path) -> None:
    """续跑的 inputs 一律来自 `RUN_STARTED`：调用方这次传什么都会被忽略。"""
    global CRASH_IN_C

    with SqliteJournal(journal_path) as journal:
        with pytest.raises(FlowExecutionError) as caught:
            execute(counting_flow, journal, CLOCK, inputs={"token": "logged"})
        assert SEEN_INPUTS == {"token": "logged"}

        SEEN_INPUTS.clear()
        CRASH_IN_C = False
        execute(
            counting_flow, journal, CLOCK, inputs={"token": "caller"}, run_id=caught.value.run_id
        )

    assert SEEN_INPUTS == {"token": "logged"}


def test_completed_run_is_returned_without_executing_anything(journal_path: Path) -> None:
    """已完成的 run 再次 execute：不执行任何步骤，直接返回录制结果。"""
    global CRASH_IN_C
    CRASH_IN_C = False

    with SqliteJournal(journal_path) as journal:
        first = execute(counting_flow, journal, CLOCK, inputs={"token": "logged"})
        assert (first.status, first.result) == (STATUS_COMPLETED, 6)
        assert FLOW_BODY_CALLS == 1
        events_before = journal.load_events(first.run_id)

        STEP_CALLS.clear()

        again = execute(counting_flow, journal, CLOCK, run_id=first.run_id)
        events_after = journal.load_events(first.run_id)

    assert again == first
    assert STEP_CALLS == {}, "已完成的 run 不得执行任何步骤"
    assert FLOW_BODY_CALLS == 1, "已完成的 run 连流程体都不应进入"
    assert events_after == events_before, "已完成的 run 不得追加任何事件"


def test_resume_with_a_mismatched_flow_name_is_rejected(journal_path: Path) -> None:
    with SqliteJournal(journal_path) as journal:
        with pytest.raises(FlowExecutionError) as caught:
            execute(counting_flow, journal, CLOCK)
        run_id = caught.value.run_id
        events_before = journal.load_events(run_id)

        with pytest.raises(ConfigurationError):
            execute(other_flow, journal, CLOCK, run_id=run_id)

        # 名字对不上是调用方的配置错误：不得动这个 run 的任何状态
        assert journal.get_run(run_id).status == STATUS_FAILED
        assert journal.load_events(run_id) == events_before


def test_mismatched_flow_name_is_rejected_even_for_a_completed_run(journal_path: Path) -> None:
    global CRASH_IN_C
    CRASH_IN_C = False

    with SqliteJournal(journal_path) as journal:
        first = execute(counting_flow, journal, CLOCK)

        with pytest.raises(ConfigurationError):
            execute(other_flow, journal, CLOCK, run_id=first.run_id)


def test_resume_of_an_unknown_run_is_rejected(journal_path: Path) -> None:
    with SqliteJournal(journal_path) as journal, pytest.raises(RunNotFoundError):
        execute(counting_flow, journal, CLOCK, run_id="run_missing")


def test_new_run_writes_the_record_and_the_started_event(journal_path: Path) -> None:
    global CRASH_IN_C
    CRASH_IN_C = False

    with SqliteJournal(journal_path) as journal:
        result = execute(counting_flow, journal, CLOCK, inputs={"token": "t"})
        record = journal.get_run(result.run_id)
        events = journal.load_events(result.run_id)

    assert result.status == STATUS_COMPLETED
    assert result.result == 6
    assert record is not None
    assert (record.flow_name, record.status) == (FLOW_NAME, STATUS_COMPLETED)
    assert record.inputs == {"token": "t"}
    assert record.result == 6
    assert events[0].kind == EventKind.RUN_STARTED
    assert events[0].payload == {"flow": FLOW_NAME, "inputs": {"token": "t"}}
    assert events[-1].kind == EventKind.RUN_COMPLETED
    assert events[-1].payload == {"result": 6}


def test_new_run_without_inputs_records_an_empty_inputs_mapping(journal_path: Path) -> None:
    global CRASH_IN_C
    CRASH_IN_C = False

    with SqliteJournal(journal_path) as journal:
        result = execute(counting_flow, journal, CLOCK)
        events = journal.load_events(result.run_id)

    # 续跑靠 `RUN_STARTED` 里的 inputs 重建输入，因此空输入也必须带上这个键
    assert events[0].payload["inputs"] == {}


def test_failed_run_records_the_failing_step_name_and_preserves_the_cause(
    journal_path: Path,
) -> None:
    with SqliteJournal(journal_path) as journal:
        with pytest.raises(FlowExecutionError) as caught:
            execute(counting_flow, journal, CLOCK)

        error = caught.value
        record = journal.get_run(error.run_id)
        events = journal.load_events(error.run_id)

    failed = [event for event in events if event.kind == EventKind.RUN_FAILED]
    assert [event.step_name for event in failed] == ["c"]
    assert error.step_name == "c"
    assert isinstance(error.__cause__, RuntimeError)
    assert "simulated crash inside step c" in str(error.__cause__)
    assert record is not None
    assert record.status == STATUS_FAILED
    # 失败绝不是完成：不得写下 RUN_COMPLETED
    assert EventKind.RUN_COMPLETED not in [event.kind for event in events]


def test_failure_outside_any_step_has_no_step_name(journal_path: Path) -> None:
    with SqliteJournal(journal_path) as journal:
        with pytest.raises(FlowExecutionError) as caught:
            execute(body_raises_flow, journal, CLOCK)
        events = journal.load_events(caught.value.run_id)

    failed = [event for event in events if event.kind == EventKind.RUN_FAILED]
    assert [event.step_name for event in failed] == [None]
    assert caught.value.step_name is None


def test_run_result_is_a_frozen_record() -> None:
    result = RunResult(run_id="run_1", status=STATUS_COMPLETED, result=1)

    assert (result.run_id, result.status, result.result) == ("run_1", STATUS_COMPLETED, 1)
    with pytest.raises(FrozenInstanceError):
        result.status = STATUS_FAILED
