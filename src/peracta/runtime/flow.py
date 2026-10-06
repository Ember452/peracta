"""流程定义：`@flow` 把一个普通函数变成有名字的持久化工作单元。

`Flow.name` 是流程的**身份**，而不是标签：日志里记的是它，续跑时校验的也是它。
因此装饰器一旦套上，名字就归属于这个 `Flow`，重命名等同于换了一个流程 ——
已经写进日志的旧名字不会被自动迁移。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from peracta.core.errors import ConfigurationError


@dataclass(frozen=True)
class Flow:
    """一个可被持久化执行的流程：`name` 是身份，`fn` 是真正的函数体。

    不可变是刻意的：`name` 会被写进 `runs.flow_name` 与 `RUN_STARTED` 事件，
    跑起来之后再改名字会让"这次运行属于哪个流程"变成无法回答的问题。

    调用约定固定为 `fn(ctx, **inputs)`：第一个位置参数是 `Context`，
    其余全部来自这次运行的 `inputs`（续跑时来自 `RUN_STARTED` 事件里记录的那份）。
    """

    name: str
    fn: Callable[..., Any]


def flow[F: Callable[..., Any]](fn: F | None = None, *, name: str | None = None) -> Any:
    """把被装饰的函数登记为一个 `Flow`，同时支持 `@flow` 与 `@flow(name="...")`。

    不带参数直接装饰时用函数名作为流程名；显式给出 `name` 时以 `name` 为准。
    传入不可调用的对象抛 `ConfigurationError`：这是调用方写错了，而不是一次
    可以用默认值兜住的输入。
    """

    def wrap(target: Any) -> Flow:
        if not callable(target):
            raise ConfigurationError(f"@flow expects a callable, got {type(target).__name__}")
        return Flow(name=name or target.__name__, fn=target)

    if fn is None:
        # @flow(name="...") 或 @flow()：返回装饰器，等真正的函数传进来
        return wrap
    return wrap(fn)
