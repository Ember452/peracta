"""core.events：日志的线上契约，成员取值、字段与不可变性都不得漂移。"""

from __future__ import annotations

from enum import StrEnum

import pytest

from peracta.core.events import Event, EventKind


def _event() -> Event:
    return Event(
        seq=1,
        run_id="run_1",
        kind=EventKind.RUN_STARTED,
        step_name=None,
        payload={"flow": "demo"},
        created_at="2026-01-01T00:00:00+00:00",
    )


def test_event_kind_values_are_wire_stable() -> None:
    assert EventKind.RUN_STARTED == "run_started"
    assert EventKind.STEP_STARTED == "step_started"
    assert EventKind.STEP_COMPLETED == "step_completed"
    assert EventKind.RUN_COMPLETED == "run_completed"
    assert EventKind.RUN_FAILED == "run_failed"


def test_event_kind_is_a_str_enum() -> None:
    assert issubclass(EventKind, StrEnum)
    assert isinstance(EventKind.STEP_COMPLETED, str)
    # 普通 (str, Enum) 的 str() 会带上类名，只有 StrEnum 才等同于它的值
    assert str(EventKind.STEP_COMPLETED) == "step_completed"


def test_event_kind_members_are_exactly_the_wire_values() -> None:
    assert {kind.value for kind in EventKind} == {
        "run_started",
        "step_started",
        "step_completed",
        "run_completed",
        "run_failed",
    }


def test_event_keeps_every_field() -> None:
    event = Event(
        seq=7,
        run_id="run_1",
        kind=EventKind.STEP_COMPLETED,
        step_name="second",
        payload={"value": 42},
        created_at="2026-01-01T00:00:00+00:00",
    )

    assert event.seq == 7
    assert event.run_id == "run_1"
    assert event.kind is EventKind.STEP_COMPLETED
    assert event.step_name == "second"
    assert event.payload == {"value": 42}
    assert event.created_at == "2026-01-01T00:00:00+00:00"


def test_event_payload_default_is_fresh_per_instance() -> None:
    first = Event(seq=1, run_id="run_1", kind=EventKind.RUN_STARTED, step_name=None)
    second = Event(seq=2, run_id="run_1", kind=EventKind.RUN_STARTED, step_name=None)

    assert first.payload == {}

    # payload 本身可变（事件是不可变对象，不是不可变字典）；
    # 改动一个实例不得泄漏到另一个实例，否则默认值是被共享的同一个 dict
    first.payload["leak"] = True
    assert second.payload == {}


def test_event_can_be_built_without_payload_or_created_at() -> None:
    event = Event(seq=1, run_id="run_1", kind=EventKind.RUN_STARTED, step_name=None)

    assert event.payload == {}
    assert event.created_at == ""


def test_event_cannot_be_mutated() -> None:
    event = _event()

    with pytest.raises(AttributeError):
        event.seq = 2


def test_event_has_no_instance_dict() -> None:
    # dataclass(slots=True) 的直接证据：没有 __dict__，多写一个字段也写不进去
    event = _event()

    assert not hasattr(event, "__dict__")
