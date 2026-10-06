"""全项目唯一的异常出口：所有 Peracta 异常都从 `PeractaError` 派生。

约定：其它模块只从这里 import 异常，不得就地定义新异常、也不得抛裸 `Exception`，
这样调用方只要兜住 `PeractaError` 就能接住内核抛出的一切。
"""

from __future__ import annotations


class PeractaError(Exception):
    """Peracta 全部异常的基类。"""


class ConfigurationError(PeractaError):
    """调用方给出的配置不可用：路径不存在、流程未注册、开关取值非法等。"""


class JournalError(PeractaError):
    """日志持久化失败的基类。"""


class RunNotFoundError(JournalError):
    """请求的 run_id 在日志中不存在。"""


class SchemaError(JournalError):
    """日志 schema 缺失，或版本高于当前内核支持的版本。"""


class StepError(PeractaError):
    """步骤声明或使用方式有误的基类。"""


class DuplicateStepNameError(StepError):
    """同一次运行中出现了重名的步骤。"""


class StepResultNotSerializableError(StepError):
    """步骤返回值无法序列化为 JSON，因而不可能被持久化。"""


class FlowExecutionError(PeractaError):
    """流程执行期间抛出异常时对外的包装错误，保留原始异常对象。

    构造签名固定为 `(run_id, step_name, cause)`：`step_name` 为 `None` 表示失败
    发生在流程本身而不是某个步骤里；`cause` 保存原异常对象本身（同一性不变），
    便于上层重新抛出或在日志里记录真正的失败原因。
    """

    def __init__(self, run_id: str, step_name: str | None, cause: BaseException) -> None:
        self.run_id: str = run_id
        self.step_name: str | None = step_name
        self.cause: BaseException = cause
        where = f" at step '{step_name}'" if step_name else ""
        super().__init__(f"flow failed in run {run_id}{where}: {cause!r}")
