"""最小示例：被端到端测试与 README 引用的 1..n 求和流程。"""

from peracta import flow


@flow
def counter_flow(ctx, n: int = 1) -> int:
    """把 1..n 逐项求和，每一项都是一个持久化步骤。"""
    total = 0
    for index in range(1, n + 1):
        total += ctx.step(f"term:{index}", lambda index=index: index)
    return total
