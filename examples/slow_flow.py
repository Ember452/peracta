"""每步写一行进度、再睡一小会儿 —— 这样测试才能把它杀在运行中途。"""

import time
from pathlib import Path

from peracta import flow


@flow
def slow_flow(ctx, progress: str = "progress.txt") -> int:
    """跑五个持久化步骤；每步真的执行时往 `progress` 文件追加一行。

    进度行写在步骤函数**内部**而不是流程体里：续跑时流程体会从头走一遍，
    但重放的步骤不会调用步骤函数 —— 因此这行痕迹恰好证明"这一步真的执行
    了一次"，重放不会产生新行。`time.sleep` 留在流程体里，只拖慢首次执行。
    """
    path = Path(progress)
    total = 0
    for index in range(1, 6):

        def term(index=index):
            with path.open("a", encoding="utf-8") as handle:
                handle.write(f"ran:{index}\n")
            return index

        total += ctx.step(f"term:{index}", term)
        time.sleep(0.4)
    return total
