"""Peracta —— 面向 AI Agent 的持久化执行内核：已完成之事，不可重做。

包根是**唯一**的公共门面：它把各层的符号转发出来，调用方只需要 `import peracta`。
这里只做转发，不放任何逻辑 —— 逻辑属于它所在的那一层。
"""

from peracta.core.clock import Clock, FixedClock, SystemClock
from peracta.core.errors import PeractaError
from peracta.journal.sqlite_store import SqliteJournal
from peracta.runtime.context import Context
from peracta.runtime.executor import RunResult, execute
from peracta.runtime.flow import Flow, flow

__version__ = "0.1.0"

# 按字典序排列：顺序本身不是语义，但"顺序稳定"能让公共 API 面的 diff 只反映增删
__all__ = [
    "Clock",
    "Context",
    "FixedClock",
    "Flow",
    "PeractaError",
    "RunResult",
    "SqliteJournal",
    "SystemClock",
    "__version__",
    "execute",
    "flow",
]
