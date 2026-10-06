"""公共 API 面守卫：包根只导出契约里那 11 个名字，一个不多、一个不少。"""

from __future__ import annotations

import types

import peracta

EXPECTED_ALL = [
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

# 唯一允许出现在包根上的模块属性：导入子模块时 Python 自动绑定的那三个名字。
EXPECTED_SUBMODULES = {"core", "journal", "runtime"}


def test_all_is_the_exact_sorted_contract() -> None:
    # 逐字相等而非"包含"：多导出一个名字同样是公共 API 面的变更
    assert peracta.__all__ == EXPECTED_ALL
    assert peracta.__all__ == sorted(peracta.__all__)


def test_every_exported_name_is_accessible() -> None:
    for name in peracta.__all__:
        assert hasattr(peracta, name), name


def test_every_export_is_the_real_object_from_its_layer() -> None:
    # 门面必须是各层对象的转发，而不是包根上凑出来的同名副本
    from peracta.core.clock import Clock, FixedClock, SystemClock
    from peracta.core.errors import PeractaError
    from peracta.journal.sqlite_store import SqliteJournal
    from peracta.runtime.context import Context
    from peracta.runtime.executor import RunResult, execute
    from peracta.runtime.flow import Flow, flow

    assert peracta.Clock is Clock
    assert peracta.FixedClock is FixedClock
    assert peracta.SystemClock is SystemClock
    assert peracta.PeractaError is PeractaError
    assert peracta.SqliteJournal is SqliteJournal
    assert peracta.Context is Context
    assert peracta.RunResult is RunResult
    assert peracta.execute is execute
    assert peracta.Flow is Flow
    assert peracta.flow is flow


def test_no_accidental_public_names() -> None:
    # 子模块会被导入机制自动绑成父包的同名属性，这是 Python 的固有行为、不是泄漏出来的
    # API，因此只豁免这三个确知的子模块名，且必须真的是模块。豁免名单是字面量而非
    # `isinstance(value, types.ModuleType)` 这类整体放宽：往包根多 import 一个
    # `from peracta.core import clock` 会绑定模块 `clock`，它不在名单里，仍会被抓出来。
    leaked = {
        name
        for name, value in vars(peracta).items()
        if not name.startswith("_")
        and not (name in EXPECTED_SUBMODULES and isinstance(value, types.ModuleType))
    } - set(peracta.__all__)
    assert leaked == set(), f"unexpected public names: {sorted(leaked)}"


def test_version_stays_at_the_contract_value() -> None:
    assert peracta.__version__ == "0.1.0"
