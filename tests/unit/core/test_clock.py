"""core.clock：可注入时钟，测试永不依赖真实时间。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest

from peracta.core.clock import Clock, FixedClock, SystemClock


def _read(clock: Clock) -> datetime:
    """只通过协议读取时间，证明显式标注 `Clock` 的调用点对两种实现都成立。"""
    return clock.now()


def test_fixed_clock_returns_start_and_advances() -> None:
    start = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    clock = FixedClock(start)

    assert clock.now() == start

    clock.advance(90)
    assert clock.now() == start + timedelta(seconds=90)

    # 再走一次：advance 是累加，不是把时间重置到某个新起点
    clock.advance(0.5)
    assert clock.now() == start + timedelta(seconds=90.5)


def test_fixed_clock_rejects_naive_start() -> None:
    naive = datetime(2026, 1, 1, 12, 0)

    with pytest.raises(ValueError):
        FixedClock(naive)


def test_fixed_clock_normalizes_aware_start_to_utc() -> None:
    start = datetime(2026, 1, 1, 8, 0, tzinfo=timezone(timedelta(hours=8)))
    clock = FixedClock(start)

    assert clock.now() == start
    assert clock.now().utcoffset() == timedelta(0)


def test_system_clock_now_is_timezone_aware_utc() -> None:
    now = _read(SystemClock())

    assert now.tzinfo is not None
    assert now.utcoffset() == timedelta(0)


def test_fixed_clock_is_usable_through_the_clock_protocol() -> None:
    start = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)

    assert _read(FixedClock(start)) == start
