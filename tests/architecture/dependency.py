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

PACKAGE = "peracta"


def _layer_of(module: str) -> int | None:
    parts = module.split(".")
    if len(parts) < 2 or parts[0] != PACKAGE:
        return None
    return LAYERS.get(parts[1])


def _own_package(relative: str) -> str:
    """由文件相对路径推出该模块所属的包，例如 core/bad.py -> peracta.core。"""
    directory = relative.split("/")[:-1]
    return ".".join([PACKAGE, *directory])


def _targets_of(node: ast.ImportFrom, package: str) -> list[str]:
    """把 ImportFrom 还原为它可能依赖的绝对模块名，相对导入按 level 结合所在包解析。"""
    if node.level:
        parts = package.split(".")
        drop = node.level - 1
        if drop > len(parts):
            return []
        parts = parts[: len(parts) - drop]
        if node.module:
            parts = [*parts, *node.module.split(".")]
        base = ".".join(parts)
    else:
        base = node.module or ""
    if not base:
        return []
    # 包根或第三方包自身没有层级，真正的目标在别名里：from peracta import cli
    if _layer_of(base) is None:
        return [base, *(f"{base}.{alias.name}" for alias in node.names)]
    return [base]


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
        package = _own_package(relative)
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                targets = _targets_of(node, package)
            elif isinstance(node, ast.Import):
                targets = [alias.name for alias in node.names]
            else:
                continue
            for target in targets:
                layer = _layer_of(target)
                if layer is not None and layer > own_layer:
                    violations.append(f"{relative}:{node.lineno}: imports higher layer '{target}'")
    return violations
