"""标识符生成。

`run_id` 一经生成就写进日志，恢复时从日志读回，因此这里的不确定性是安全的：
重新打开一个 run 只会复用它已有的 ID，不会重新生成。
"""

from __future__ import annotations

from uuid import uuid4


def new_run_id() -> str:
    """生成一个新的 run ID，形如 `run_<16 位十六进制>`。

    取 `uuid4()` 的前 16 位而不是整串：run ID 会出现在 CLI 输出与人工排查里，
    短一些更好念；64 位随机数在单机日志的规模下碰撞概率可忽略。
    """
    return f"run_{uuid4().hex[:16]}"
