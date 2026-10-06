"""可注入时钟：内核里所有时间都从这里取，测试因此永不依赖真实时间。

约定：任何 `Clock` 实现返回的时间都必须带时区且为 UTC —— 日志里的 `created_at`
要跨机器比较与排序，本地时间或裸 naive 时间都会让重放结果不可复现。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Protocol


class Clock(Protocol):
    """取当前时间的协议。实现只读，不得依赖或修改进程内的可变全局状态。"""

    def now(self) -> datetime:
        """返回当前时间，必须带时区且为 UTC。"""
        ...


class SystemClock:
    """真实时钟：返回系统当前的 UTC 时间。"""

    def now(self) -> datetime:
        """返回当前 UTC 时间。"""
        return datetime.now(UTC)


class FixedClock:
    """测试时钟：时间只在被显式推进时才走，因而重放与断言都可复现。"""

    def __init__(self, start: datetime) -> None:
        """以 `start` 为起点。

        `start` 必须是带时区的时间；naive 时间无从判断它代表哪个时区，
        写进日志就会产生无法比较的时间戳，因此直接抛 `ValueError` 拒绝。
        带时区但非 UTC 的入参按同一时刻换算为 UTC，以维持 `Clock` 的 UTC 约定。
        """
        if start.tzinfo is None:
            raise ValueError("FixedClock requires a timezone-aware start")
        self._now = start.astimezone(UTC)

    def now(self) -> datetime:
        """返回当前固定时间。"""
        return self._now

    def advance(self, seconds: float) -> None:
        """把当前时间向前推进 `seconds` 秒（接受小数；负数表示回拨）。"""
        self._now += timedelta(seconds=seconds)
