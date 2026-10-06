"""runtime.flow：`@flow` 装饰器的两种用法与 `Flow` 记录。"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from typing import Any

import pytest

from peracta.core.errors import ConfigurationError
from peracta.runtime.flow import Flow, flow


def test_bare_decorator_uses_the_function_name_as_flow_name() -> None:
    @flow
    def charge_card(ctx: Any) -> int:
        return 1

    assert isinstance(charge_card, Flow)
    assert charge_card.name == "charge_card"


def test_name_argument_overrides_the_function_name() -> None:
    @flow(name="refund_agent")
    def _impl(ctx: Any) -> int:
        return 1

    assert isinstance(_impl, Flow)
    assert _impl.name == "refund_agent"


def test_decorator_keeps_the_original_callable() -> None:
    def body(ctx: Any) -> int:
        return 1

    decorated = flow(body)

    # fn 必须还是同一个函数对象：执行器靠调用它来跑流程
    assert decorated.fn is body


def test_parenthesised_form_without_a_name_also_works() -> None:
    @flow()
    def plain(ctx: Any) -> int:
        return 1

    assert isinstance(plain, Flow)
    assert plain.name == "plain"


def test_decorating_a_non_callable_is_rejected() -> None:
    # 42 不是可调用对象：这是调用方的配置错误，必须响亮失败而不是留个坏 Flow
    with pytest.raises(ConfigurationError):
        flow(42)


def test_flow_is_frozen() -> None:
    decorated = flow(lambda: 1, name="frozen_flow")

    with pytest.raises(FrozenInstanceError):
        decorated.name = "other"
