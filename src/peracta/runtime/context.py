"""面向流程的执行面：流程里一切需要记住的事情都必须经过 `Context.step`。

本层只做一件事 —— 把"这一步真的做过了"变成日志里的事实，从而让重放能跳过它。
它不碰副作用层、不做重试、不承诺幂等：步骤级语义是**至少一次**，恰好一次是后续
副作用层的职责，这里不假装承担。
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from peracta.core.clock import Clock
from peracta.core.errors import DuplicateStepNameError, StepResultNotSerializableError
from peracta.core.events import EventKind
from peracta.journal.store import JournalStore


class Context:
    """交给流程的执行上下文：记录事实、重放结果、管住步骤名。

    `replay` 是"上一个进程已经完成"的步骤名到结果的映射，只应来自日志重建
    （`build_run_state().completed_steps`）。它只含真正完成过的步骤：崩在中途、
    只有 `STEP_STARTED` 的步骤不在其中，因此会被重新执行。

    `current_step` 是给执行器读的"失败归属"指针：它只在步骤**正常返回**时恢复
    （见 `step`），因此一个抛错后被流程体自己吞掉的步骤会把它留在原地；此后流程体里
    再发生的失败就会被误记到那个早已结束的步骤名下。这是"恢复只在正常返回时发生"
    这条规则的已知代价，写在这里而不是留成暗坑。
    """

    def __init__(
        self,
        store: JournalStore,
        run_id: str,
        clock: Clock,
        replay: dict[str, Any] | None = None,
    ) -> None:
        self._store = store
        self._run_id = run_id
        self._clock = clock
        # 拷贝一份：调用方手里的是日志重建的结果，本对象的余生不应被外部改动影响
        self._replay: dict[str, Any] = dict(replay) if replay is not None else {}
        self._seen: set[str] = set()
        # 只在步骤正常返回时恢复；回调抛错且被流程体吞掉时它会保持陈旧，
        # 后续流程体里的失败会被误归到这一步。语义与理由见类 docstring。
        self.current_step: str | None = None

    @property
    def run_id(self) -> str:
        """本次运行的 id。只读：一个 `Context` 只服务一次运行。"""
        return self._run_id

    def step[T](self, name: str, fn: Callable[[], T]) -> T:
        """执行并记录一步 `name`；返回 `fn()` 的结果或重放里录制的结果。

        四条路径，语义各不相同：

        - 已经出现过这个名字 → `DuplicateStepNameError`（循环里请自行参数化名字）；
        - 名字在 `replay` 里 → 直接返回录制值，**不调用 `fn`、不写任何事件**；
        - 首次执行 → 先写 `STEP_STARTED` 再调用 `fn`，正常返回后写 `STEP_COMPLETED`；
        - `fn` 或序列化失败 → 只留下 `STEP_STARTED`，该步骤下次会被重新执行。

        只有序列化的结果才写得进日志，因此结果不能是任意对象；这条约束在 V0.1 是
        刻意的，它让"重放得到的东西"与"当初返回的东西"在结构上一致。
        """
        if name in self._seen:
            raise DuplicateStepNameError(
                f"step '{name}' used twice in run {self._run_id}; "
                "declare a unique name per call (parameterise it inside loops)"
            )
        # 先登记再判断重放：重放命中的名字同样算作"这次运行里已经用过"
        self._seen.add(name)

        previous = self.current_step
        self.current_step = name

        if name in self._replay:
            self.current_step = previous
            return self._replay[name]

        self._store.append_event(self._run_id, EventKind.STEP_STARTED, name, {}, self._stamp())
        value = fn()
        payload = {"result": _encode(value, name)}
        self._store.append_event(
            self._run_id, EventKind.STEP_COMPLETED, name, payload, self._stamp()
        )
        # 只有正常返回才恢复 current_step；抛异常时保留失败步骤名，
        # 执行器才能把它写进 RUN_FAILED，这是对原计划 finally 版本的有意修正。
        self.current_step = previous
        return value

    def _stamp(self) -> str:
        """取当前时间戳。日志里的时间一律是 ISO 8601 字符串。"""
        return self._clock.now().isoformat()


def _encode(value: Any, step_name: str) -> Any:
    """校验步骤结果可 JSON 序列化，是则原样返回。

    写 `STEP_STARTED` 之后再校验是刻意的：这次尝试已经发生，就该留下痕迹；而
    `STEP_COMPLETED` 绝不能在结果无法持久化时写下 —— 否则重放会拿一个假结果去
    跳过本该重新执行的步骤。
    """
    try:
        json.dumps(value)
    except (TypeError, ValueError) as exc:
        raise StepResultNotSerializableError(
            f"step '{step_name}' returned {type(value).__name__}, which cannot be persisted; "
            "return JSON-serialisable data"
        ) from exc
    return value
