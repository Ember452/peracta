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


def test_real_src_has_no_violations() -> None:
    assert check_dependency_direction(SRC_ROOT) == []
