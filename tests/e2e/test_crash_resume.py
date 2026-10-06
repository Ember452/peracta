"""PROJECT.md 验收 A2 的可复现证据：真 `kill -9` 之后断点续跑，已完成步骤不重跑。

不做 mock 崩溃：子进程真跑 `slow_flow`，跑到中途被 `TerminateProcess`/SIGKILL
硬杀（不给清理机会），然后 `resume --last` 必须从断点接着跑，且进度文件里
每个步骤恰好留下一行执行痕迹。
"""

import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = REPO_ROOT / "examples" / "slow_flow.py"


def test_resume_after_hard_kill(tmp_path: Path) -> None:
    db = tmp_path / "j.sqlite"
    progress = tmp_path / "progress.txt"
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "peracta.cli.main",
            "run",
            str(EXAMPLE),
            "--db",
            str(db),
            "--input",
            f"progress={progress}",
        ],
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    time.sleep(1.2)  # 让它跑完前几步（每步约 0.4s，含解释器启动）
    process.kill()  # 硬杀：Windows 是 TerminateProcess，POSIX 是 SIGKILL
    process.wait(timeout=10)

    executed_before = progress.read_text(encoding="utf-8").splitlines()
    assert 0 < len(executed_before) < 5, "need a genuine mid-run kill"

    resume = subprocess.run(
        [
            sys.executable,
            "-m",
            "peracta.cli.main",
            "resume",
            str(EXAMPLE),
            "--db",
            str(db),
            "--last",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert resume.returncode == 0, resume.stderr

    executed_after = progress.read_text(encoding="utf-8").splitlines()
    # 核心验收：已完成的步骤绝不重跑 —— 前缀不变，五行恰好各出现一次
    assert executed_after[: len(executed_before)] == executed_before
    assert len(executed_after) == 5, "all five steps must have run exactly once"
    assert sorted(executed_after) == [f"ran:{i}" for i in range(1, 6)]
