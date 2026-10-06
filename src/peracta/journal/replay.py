"""状态重建：把一段事件日志折叠成一次运行的当前状态。

这是纯函数层：不碰数据库、不取当前时间、不读环境变量 —— 同样的输入永远折叠出
同样的 `RunState`。Task 4 的续跑完全建立在这里的语义之上：一个步骤是否"已完成"，
只能由日志里存在对应的 `STEP_COMPLETED` 来断定。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from peracta.core.events import Event, EventKind

STATUS_RUNNING = "running"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"


@dataclass(frozen=True, slots=True)
class RunState:
    """从日志重建出的一次运行状态。

    `completed_steps` 只含真正完成过的步骤（键为步骤名，值为该步骤的结果），
    `inputs` 取自 `RUN_STARTED` 的 payload。两者都是重建结果，不是日志本身。
    """

    run_id: str
    status: str
    completed_steps: dict[str, Any]
    inputs: dict[str, Any]


def build_run_state(events: list[Event]) -> RunState:
    """按传入顺序折叠事件列表，返回该次运行的当前状态。

    空列表抛 `ValueError`：没有事件就没有 `run_id`，这是调用方拿错了数据源，
    而不是"一次空运行"。调用方需按 `seq` 升序传入（`JournalStore.load_events`
    的返回即满足）；本函数不排序、不去重，以免掩盖日志本身的问题。

    `STEP_STARTED` 只表示"尝试开始过"，绝不进入 `completed_steps` —— 崩在中途
    的步骤必须重跑，这是"已完成的工作绝不重做"的另一面。
    """
    if not events:
        raise ValueError("cannot rebuild run state from an empty event list")

    inputs: dict[str, Any] = {}
    completed_steps: dict[str, Any] = {}
    status = STATUS_RUNNING

    for event in events:
        if event.kind is EventKind.RUN_STARTED:
            inputs = dict(event.payload.get("inputs", {}))
        elif event.kind is EventKind.STEP_COMPLETED and event.step_name is not None:
            completed_steps[event.step_name] = event.payload["result"]
        elif event.kind is EventKind.RUN_COMPLETED:
            status = STATUS_COMPLETED
        elif event.kind is EventKind.RUN_FAILED:
            status = STATUS_FAILED

    return RunState(
        run_id=events[0].run_id,
        status=status,
        completed_steps=completed_steps,
        inputs=inputs,
    )
