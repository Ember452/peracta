"""core.errors：全项目唯一的异常出口，层级与上下文必须稳定。"""

from __future__ import annotations

import pytest

from peracta.core.errors import (
    ConfigurationError,
    DuplicateStepNameError,
    FlowExecutionError,
    JournalError,
    PeractaError,
    RunNotFoundError,
    SchemaError,
    StepError,
    StepResultNotSerializableError,
)


def test_journal_errors_share_the_journal_branch() -> None:
    assert issubclass(PeractaError, Exception)
    assert issubclass(JournalError, PeractaError)
    assert issubclass(RunNotFoundError, JournalError)
    assert issubclass(SchemaError, JournalError)


def test_step_errors_share_the_step_branch() -> None:
    assert issubclass(StepError, PeractaError)
    assert issubclass(DuplicateStepNameError, StepError)
    assert issubclass(StepResultNotSerializableError, StepError)
    # 两条分支必须分离：步骤错误冒充日志错误会让调用方的 except 抓错东西
    assert not issubclass(DuplicateStepNameError, JournalError)


def test_configuration_error_is_a_peracta_error() -> None:
    assert issubclass(ConfigurationError, PeractaError)
    assert not issubclass(ConfigurationError, JournalError)


def test_every_error_can_be_caught_as_peracta_error() -> None:
    # issubclass 不足以证明 except 真的能兜住子类，这里真抛真抓
    for error in (RunNotFoundError("run_missing"), DuplicateStepNameError("dup")):
        with pytest.raises(PeractaError):
            raise error


def test_flow_execution_error_keeps_the_original_cause() -> None:
    cause = ValueError("boom")
    error = FlowExecutionError(run_id="run_1", step_name="second", cause=cause)

    assert issubclass(FlowExecutionError, PeractaError)
    assert error.run_id == "run_1"
    assert error.step_name == "second"
    assert error.cause is cause
    assert "run_1" in str(error)


def test_flow_execution_error_without_step_name_still_names_the_run() -> None:
    error = FlowExecutionError(run_id="run_2", step_name=None, cause=RuntimeError("kaboom"))

    assert error.step_name is None
    assert "run_2" in str(error)
