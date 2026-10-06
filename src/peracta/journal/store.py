"""存储契约：内核只依赖这里的 Protocol，永不依赖 SQLite 具体类。

`RunRecord` 是 `runs` 表的一行在内存中的形态。契约里的时间一律是 ISO 8601 字符串
而不是 `datetime`：它是要跨越进程与机器边界的线上表示，比较与排序都发生在本层之外。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from peracta.core.events import Event, EventKind


@dataclass(frozen=True, slots=True)
class RunRecord:
    """一次运行的元数据；`inputs` 与 `result` 必须是可 JSON 序列化的值。

    `updated_at` 在本版本里只由 `create_run` 写入初始值，语义留待 Task 4 定义 ——
    这一层不自动维护它。
    """

    run_id: str
    flow_name: str
    status: str
    created_at: str
    updated_at: str
    inputs: dict[str, Any]
    result: Any = None


class JournalStore(Protocol):
    """日志存储的六个动作；方法集合与签名是跨任务契约，不得增删、改名或漂移。"""

    def create_run(self, record: RunRecord) -> None:
        """写入一条新的运行记录。"""
        ...

    def append_event(
        self,
        run_id: str,
        kind: EventKind,
        step_name: str | None,
        payload: dict[str, Any],
        created_at: str,
    ) -> Event:
        """追加一条事件，返回带 `seq` 的已持久化事件。"""
        ...

    def load_events(self, run_id: str) -> list[Event]:
        """按 `seq` 升序返回该 run 的全部事件；没有事件时抛 `RunNotFoundError`。"""
        ...

    def get_run(self, run_id: str) -> RunRecord | None:
        """返回运行记录；未知 `run_id` 返回 `None`。"""
        ...

    def set_run_status(self, run_id: str, status: str, result: Any = None) -> None:
        """更新运行状态与结果；未知 `run_id` 抛 `RunNotFoundError`。"""
        ...

    def list_runs(self, limit: int = 50) -> list[RunRecord]:
        """按 `created_at` 倒序返回最近的运行，最多 `limit` 条。"""
        ...
