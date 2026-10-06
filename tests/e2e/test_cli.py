"""CLI 端到端验收：真起子进程跑 `python -m peracta.cli.main`，验证退出码契约。

退出码：0 成功 / 1 运行失败 / 2 用法错误 —— 这里每条断言都对着这张表。
"""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = REPO_ROOT / "examples" / "counter_flow.py"


def _run(*args: str, db: Path) -> subprocess.CompletedProcess[str]:
    """在仓库根目录起一个 CLI 子进程；`--db` 按命令契约放在子命令之后。"""
    return subprocess.run(
        [sys.executable, "-m", "peracta.cli.main", *args, "--db", str(db)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )


def test_run_then_ps(tmp_path: Path) -> None:
    db = tmp_path / "j.sqlite"
    result = _run("run", str(EXAMPLE), "--input", "n=3", db=db)

    assert result.returncode == 0, result.stderr
    assert "completed" in result.stdout

    listed = _run("ps", db=db)
    assert listed.returncode == 0
    assert "counter_flow" in listed.stdout


def test_missing_file_is_usage_error(tmp_path: Path) -> None:
    result = _run("run", str(tmp_path / "nope.py"), db=tmp_path / "j.sqlite")
    assert result.returncode == 2


def test_unknown_run_returns_failure(tmp_path: Path) -> None:
    result = _run("resume", "run_missing", str(EXAMPLE), db=tmp_path / "j.sqlite")
    assert result.returncode == 1
