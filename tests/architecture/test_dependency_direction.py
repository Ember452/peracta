from pathlib import Path

from tests.architecture.dependency import check_dependency_direction

SRC_ROOT = Path(__file__).resolve().parents[2] / "src" / "peracta"


def test_detects_upward_import(tmp_path: Path) -> None:
    pkg = tmp_path / "peracta"
    (pkg / "core").mkdir(parents=True)
    (pkg / "cli").mkdir(parents=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "core" / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "cli" / "__init__.py").write_text("", encoding="utf-8")
    # core (L0) 导入 cli (L5) —— 必须被抓出来
    (pkg / "core" / "bad.py").write_text("from peracta.cli import main\n", encoding="utf-8")

    violations = check_dependency_direction(pkg)

    assert len(violations) == 1
    assert "core/bad.py" in violations[0]
    assert "cli" in violations[0]


def _build_package(tmp_path: Path, filename: str, source: str) -> Path:
    """构造一个最小 peracta 包：core（L0）与 cli（L5）都在，目标文件由调用方给出。"""
    pkg = tmp_path / "peracta"
    (pkg / "core").mkdir(parents=True)
    (pkg / "cli").mkdir(parents=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "core" / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "cli" / "__init__.py").write_text("", encoding="utf-8")
    (pkg / filename).write_text(source, encoding="utf-8")
    return pkg


def test_detects_relative_module_from_import(tmp_path: Path) -> None:
    # 绕过形式一：from ..cli import main —— ast.ImportFrom.module == "cli"、level == 2
    pkg = _build_package(tmp_path, "core/bad.py", "from ..cli import main\n")

    violations = check_dependency_direction(pkg)

    assert len(violations) == 1
    assert "core/bad.py" in violations[0]
    assert "peracta.cli" in violations[0]


def test_detects_relative_name_from_import(tmp_path: Path) -> None:
    # 绕过形式二：from .. import cli —— node.module is None，老的 `and node.module` 守卫直接跳过
    pkg = _build_package(tmp_path, "core/bad.py", "from .. import cli\n")

    violations = check_dependency_direction(pkg)

    assert len(violations) == 1
    assert "core/bad.py" in violations[0]
    assert "peracta.cli" in violations[0]


def test_detects_package_root_alias_from_import(tmp_path: Path) -> None:
    # 绕过形式三：from peracta import cli —— 目标 "peracta" 自身无层，需要逐个别名解析
    pkg = _build_package(tmp_path, "core/bad.py", "from peracta import cli\n")

    violations = check_dependency_direction(pkg)

    assert len(violations) == 1
    assert "core/bad.py" in violations[0]
    assert "peracta.cli" in violations[0]


def test_detects_plain_import(tmp_path: Path) -> None:
    # ast.Import 分支：import peracta.cli
    pkg = _build_package(tmp_path, "core/bad.py", "x = 1\nimport peracta.cli\n")

    violations = check_dependency_direction(pkg)

    assert len(violations) == 1
    assert violations[0] == "core/bad.py:2: imports higher layer 'peracta.cli'"


def test_violation_reports_source_position(tmp_path: Path) -> None:
    pkg = _build_package(tmp_path, "core/bad.py", "x = 1\ny = 2\nfrom peracta.cli import main\n")

    violations = check_dependency_direction(pkg)

    assert len(violations) == 1
    assert violations[0] == "core/bad.py:3: imports higher layer 'peracta.cli'"


def test_real_src_has_no_violations() -> None:
    assert check_dependency_direction(SRC_ROOT) == []
