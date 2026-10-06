"""架构守卫：导入只允许指向同层或更低的层。"""

from __future__ import annotations

import ast
from pathlib import Path

LAYERS: dict[str, int] = {
    "core": 0,
    "observability": 0,
    "journal": 1,
    "effect": 2,
    "runtime": 3,
    "verify": 4,
    "cli": 5,
}


def _layer_of(module: str) -> int | None:
    parts = module.split(".")
    if len(parts) < 2 or parts[0] != "peracta":
        return None
    return LAYERS.get(parts[1])


def check_dependency_direction(src_root: Path) -> list[str]:
    violations: list[str] = []
    for path in sorted(src_root.rglob("*.py")):
        # 违规信息里的路径统一用 / 分隔，避免 Windows 与 POSIX 断言不一致
        relative = path.relative_to(src_root).as_posix()
        # 包根 __init__.py 是公共门面，允许导出各层符号
        if "/" not in relative:
            continue
        own_layer = LAYERS.get(relative.split("/", 1)[0])
        if own_layer is None:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            target: str | None = None
            if isinstance(node, ast.ImportFrom) and node.module:
                target = node.module
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    layer = _layer_of(alias.name)
                    if layer is not None and layer > own_layer:
                        violations.append(f"{relative}: imports higher layer '{alias.name}'")
                continue
            if target is None:
                continue
            layer = _layer_of(target)
            if layer is not None and layer > own_layer:
                violations.append(f"{relative}: imports higher layer '{target}'")
    return violations
