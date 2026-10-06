"""日志的线上契约：改动这个文件就等于改动日志格式。

`EventKind` 的字符串值与 `Event` 的字段定义都是持久化格式的一部分：
已经写进日志的事件，必须永远能按这里的定义读回来。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class EventKind(StrEnum):
    """日志事件的种类。成员名与字符串值都是持久化格式，不得改写。"""

    RUN_STARTED = "run_started"
    STEP_STARTED = "step_started"
    STEP_COMPLETED = "step_completed"
    RUN_COMPLETED = "run_completed"
    RUN_FAILED = "run_failed"


@dataclass(frozen=True, slots=True)
class Event:
    """一条已落盘的事件。

    不可变是刻意的：事件一旦写进日志就是历史事实，不允许被就地改写。
    `payload` 用 `default_factory` 而不是字面量默认值，避免所有实例共享同一个
    可变 dict；`created_at` 是 ISO 8601 字符串而非 `datetime`，因为它是日志的
    线上表示，序列化与比较都在这一层之外决定。
    """

    seq: int
    run_id: str
    kind: EventKind
    step_name: str | None
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
