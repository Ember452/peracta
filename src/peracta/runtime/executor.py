"""执行循环：驱动流程、记录事实、在进程重启之后接着跑。

本层是"已完成的工作绝不重做"的落点。一个 run 的进度**只**从日志重建 —— 日志里
没有对应 `STEP_COMPLETED` 的步骤就是没做完的步骤。它不猜、不缓存，也不相信调用方
手里的输入：续跑时输入一律取自 `RUN_STARTED` 事件，那才是这次运行真正开始时的输入。

失败语义是"至少一次"：失败会留下 `RUN_FAILED` 并向上抛 `FlowExecutionError`，
下次续跑从失败的步骤重新开始；恰好一次由后续的副作用层负责，这里不假装做到。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from peracta.core.clock import Clock
from peracta.core.errors import ConfigurationError, FlowExecutionError, RunNotFoundError
from peracta.core.events import EventKind
from peracta.core.ids import new_run_id
from peracta.journal.replay import (
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_RUNNING,
    build_run_state,
)
from peracta.journal.store import JournalStore, RunRecord
from peracta.runtime.context import Context
from peracta.runtime.flow import Flow


@dataclass(frozen=True)
class RunResult:
    """一次 `execute` 的结局：哪次运行、什么状态、结果是什么。"""

    run_id: str
    status: str
    result: Any = None


def execute(
    flow: Flow,
    store: JournalStore,
    clock: Clock,
    *,
    inputs: dict[str, Any] | None = None,
    run_id: str | None = None,
) -> RunResult:
    """执行 `flow`：`run_id` 为空时开一次新运行，否则接着那个 run 往下跑。

    调用方**在任何情况下都必须提供 `flow` 对象**，续跑也一样：内核不注册、也不
    查找流程，它只把日志里的进度套回调用方给的这个流程上，并校验名字一致。
    `inputs` 只在开新运行时有效 —— 续跑一律用日志里记录的那份输入。
    """
    if run_id is None:
        return _start_new(flow, store, clock, dict(inputs) if inputs is not None else {})
    return _resume(flow, store, clock, run_id)


def _start_new(flow: Flow, store: JournalStore, clock: Clock, inputs: dict[str, Any]) -> RunResult:
    """开一次新运行：建记录、写 `RUN_STARTED`，然后以空重放驱动流程。"""
    run_id = new_run_id()
    stamp = clock.now().isoformat()
    store.create_run(
        RunRecord(
            run_id=run_id,
            flow_name=flow.name,
            status=STATUS_RUNNING,
            created_at=stamp,
            updated_at=stamp,
            inputs=inputs,
        )
    )
    # `inputs` 键必须写上：`build_run_state` 缺这个键时抛 KeyError（Task 3 的裁定），
    # 而续跑的输入完全从这里重建。
    store.append_event(
        run_id, EventKind.RUN_STARTED, None, {"flow": flow.name, "inputs": inputs}, stamp
    )
    return _drive(flow, store, clock, run_id, inputs, replay={})


def _resume(flow: Flow, store: JournalStore, clock: Clock, run_id: str) -> RunResult:
    """接着一个已有 run 跑：校验身份、重建状态，然后按日志里的进度驱动。"""
    run = store.get_run(run_id)
    if run is None:
        raise RunNotFoundError(f"unknown run {run_id}")
    # 名字校验先于"已完成"短路：拿错流程对象是配置错误，不该被一个完成态掩盖
    if run.flow_name != flow.name:
        raise ConfigurationError(
            f"run {run_id} belongs to flow '{run.flow_name}', not '{flow.name}'"
        )

    state = build_run_state(store.load_events(run_id))
    if state.status == STATUS_COMPLETED:
        # 已经完成：不进入流程体，也不写任何事件，直接返回**日志里**录制的结果。
        # `runs` 行与日志是两条独立的 autocommit 语句写下的，进程可能死在两者之间；
        # 此时日志是权威，行只是派生物 —— 顺手按日志修回来，否则它会永远停在 running。
        if run.status != state.status:
            store.set_run_status(run_id, state.status, result=state.result)
        return RunResult(run_id=run_id, status=STATUS_COMPLETED, result=state.result)
    return _drive(flow, store, clock, run_id, state.inputs, replay=state.completed_steps)


def _drive(
    flow: Flow,
    store: JournalStore,
    clock: Clock,
    run_id: str,
    inputs: dict[str, Any],
    replay: dict[str, Any],
) -> RunResult:
    """调用流程并翻译结局：成功写 `RUN_COMPLETED`，失败写 `RUN_FAILED` 后抛出。"""
    context = Context(store=store, run_id=run_id, clock=clock, replay=replay)
    try:
        result = flow.fn(context, **inputs)
    except Exception as exc:
        # step_name 取 `context.current_step`：它只在步骤正常返回时才恢复，
        # 因此这里拿到的是真正失败的那个步骤名（失败在流程体里时为 None）
        store.append_event(
            run_id,
            EventKind.RUN_FAILED,
            context.current_step,
            {"error": repr(exc)},
            clock.now().isoformat(),
        )
        store.set_run_status(run_id, STATUS_FAILED)
        raise FlowExecutionError(run_id, context.current_step, exc) from exc

    store.append_event(
        run_id,
        EventKind.RUN_COMPLETED,
        None,
        {"result": result},
        clock.now().isoformat(),
    )
    store.set_run_status(run_id, STATUS_COMPLETED, result=result)
    return RunResult(run_id=run_id, status=STATUS_COMPLETED, result=result)
