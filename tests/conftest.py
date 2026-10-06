"""所有测试层共享的 fixture。"""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def journal_path(tmp_path: Path) -> Path:
    """每个测试独立的临时目录中的全新 SQLite 日志路径。"""
    return tmp_path / "journal.sqlite"
