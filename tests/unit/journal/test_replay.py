"""journal.replay：从事件日志重建运行状态 —— 纯函数、无 IO、结果可复现。"""

from __future__ import annotations

from typing import Any

import pytest

from peracta.core.events import Event, EventKind
from peracta.journal.replay import (
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_RUNNING,
    RunState,
    build_run_state,
)

STAMP = "2026-01-01T00:00:00+00:00"


def _event(
    seq: int,
    kind: EventKind,
    step_name: str | None = None,
    payload: dict[str, Any] | None = None,
) -> Event:
    """构造一条测试事件；`seq` 由调用方显式给出，不依赖列表里的隐式位置。"""
    return Event(
        seq=seq,
        run_id="run_1",
        kind=kind,
        step_name=step_name,
        payload={} if payload is None else payload,
        created_at=STAMP,
    )


def _started(inputs: dict[str, Any]) -> Event:
    """带 inputs 的 RUN_STARTED，这是重建输入的唯一样本。"""
    return _event(1, EventKind.RUN_STARTED, payload={"flow": "demo", "inputs": inputs})


def test_status_constants_are_wire_stable() -> None:
    # 三个状态串会被写进 runs.status，属于持久化格式的一部分
    assert STATUS_RUNNING == "running"
    assert STATUS_COMPLETED == "completed"
    assert STATUS_FAILED == "failed"


def test_completed_run_rebuilds_inputs_steps_and_running_status() -> None:
    events = [
        _started({"n": 3}),
        _event(2, EventKind.STEP_STARTED, "first"),
        _event(3, EventKind.STEP_COMPLETED, "first", {"result": 10}),
    ]

    state = build_run_state(events)

    assert state.inputs == {"n": 3}
    assert state.completed_steps == {"first": 10}
    # 还没有 RUN_COMPLETED，因此仍在运行中
    assert state.status == STATUS_RUNNING


def test_run_started_without_inputs_key_rebuilds_empty_inputs() -> None:
    state = build_run_state([_event(1, EventKind.RUN_STARTED, payload={"flow": "demo"})])

    assert state.inputs == {}


def test_step_started_without_completion_is_not_replayable() -> None:
    # 崩在中途的步骤必须重跑：只有 STEP_STARTED 不得进入 completed_steps
    events = [_started({}), _event(2, EventKind.STEP_STARTED, "half")]

    state = build_run_state(events)

    assert state.completed_steps == {}


def test_run_completed_event_sets_completed_status() -> None:
    events = [
        _started({}),
        _event(2, EventKind.STEP_COMPLETED, "first", {"result": 1}),
        _event(3, EventKind.RUN_COMPLETED, payload={"result": 1}),
    ]

    assert build_run_state(events).status == STATUS_COMPLETED


def test_run_failed_event_sets_failed_status() -> None:
    events = [
        _started({}),
        _event(2, EventKind.STEP_COMPLETED, "first", {"result": 1}),
        _event(3, EventKind.RUN_FAILED, "second", {"error": "boom"}),
    ]

    assert build_run_state(events).status == STATUS_FAILED


def test_empty_event_list_is_rejected() -> None:
    # 没有事件就没有 run_id，也没有任何事实可重建；这是调用方错误，不是空状态
    with pytest.raises(ValueError):
        build_run_state([])


def test_rebuilt_state_carries_the_run_id_of_the_events() -> None:
    assert build_run_state([_started({})]).run_id == "run_1"


def test_step_completed_without_a_step_name_is_ignored() -> None:
    # completed_steps 的键类型是 str：step_name 为 None 的事件不是合法的步骤完成
    events = [_started({}), _event(2, EventKind.STEP_COMPLETED, payload={"result": 1})]

    assert build_run_state(events).completed_steps == {}


def test_run_state_is_frozen() -> None:
    state = build_run_state([_started({})])

    assert isinstance(state, RunState)
    with pytest.raises(AttributeError):
        state.status = STATUS_COMPLETED
