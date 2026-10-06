"""`SqliteJournal`：把 `JournalStore` 契约落到单个 SQLite 文件上。

两条硬要求决定了这里的写法：

- `isolation_level = None`：每条语句自己提交，进程随时被 `kill -9` 也不会把已经执行完
  的写入回滚掉；配合 WAL 与 `PRAGMA synchronous = FULL`，已确认的写入是真落盘的。
- `PRAGMA foreign_keys = ON`：没有 `runs` 行就不允许写 `events` 行，杜绝孤儿事件。
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from peracta.core.errors import RunNotFoundError, SchemaError
from peracta.core.events import Event, EventKind
from peracta.journal.schema import ensure_schema
from peracta.journal.store import RunRecord

_RUN_COLUMNS = "run_id, flow_name, status, created_at, updated_at, inputs_json, result_json"

_INSERT_RUN = f"INSERT INTO runs ({_RUN_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?)"
_INSERT_EVENT = (
    "INSERT INTO events (run_id, kind, step_name, payload_json, created_at) VALUES (?, ?, ?, ?, ?)"
)
_SELECT_EVENTS = (
    "SELECT seq, run_id, kind, step_name, payload_json, created_at "
    "FROM events WHERE run_id = ? ORDER BY seq"
)
_SELECT_RUN = f"SELECT {_RUN_COLUMNS} FROM runs WHERE run_id = ?"
# 同一 created_at 时用 rowid 倒序兜底：SQLite 的 rowid 就是插入顺序，这让"最近一次
# 运行"始终是最新插入的那一条，不会因时间戳精度（或测试里的 FixedClock）而漂移。
_SELECT_RUNS = f"SELECT {_RUN_COLUMNS} FROM runs ORDER BY created_at DESC, rowid DESC LIMIT ?"
_UPDATE_STATUS = "UPDATE runs SET status = ?, result_json = ? WHERE run_id = ?"


def _dump(value: Any) -> str | None:
    """把值编码成 JSON 文本；`None` 直接落成 SQL NULL（读回来仍是 `None`）。"""
    return None if value is None else json.dumps(value)


def _load(text: str | None) -> Any:
    """解码由 `_dump` 写出的文本，是它的逆运算。"""
    return None if text is None else json.loads(text)


def _row_to_record(row: sqlite3.Row) -> RunRecord:
    """把 `runs` 表的一行还原为 `RunRecord`。"""
    return RunRecord(
        run_id=row["run_id"],
        flow_name=row["flow_name"],
        status=row["status"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        inputs=json.loads(row["inputs_json"]),
        result=_load(row["result_json"]),
    )


class SqliteJournal:
    """由单个 SQLite 文件支撑的 `JournalStore`。

    构造即建库、建表；用 `with` 或显式 `close()` 收尾。同一个实例不要在多个线程间共享。
    """

    def __init__(self, path: Path | str) -> None:
        """打开（必要时创建）`path` 上的日志库。

        父目录不存在会先建出来；库文件的 schema 版本比本内核新时抛 `SchemaError`，
        并且不会留下一个半开的连接。
        """
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._path, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode = WAL")
        self._conn.execute("PRAGMA synchronous = FULL")
        self._conn.execute("PRAGMA foreign_keys = ON")
        try:
            ensure_schema(self._conn)
        except SchemaError:
            self._conn.close()
            raise

    def close(self) -> None:
        """关闭底层连接。已提交的写入不受影响；之后再调用任何方法都会失败。"""
        self._conn.close()

    def __enter__(self) -> SqliteJournal:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def create_run(self, record: RunRecord) -> None:
        """写入运行记录；`inputs` 与 `result` 以 JSON 文本落盘。"""
        self._conn.execute(
            _INSERT_RUN,
            (
                record.run_id,
                record.flow_name,
                record.status,
                record.created_at,
                record.updated_at,
                json.dumps(record.inputs),
                _dump(record.result),
            ),
        )

    def append_event(
        self,
        run_id: str,
        kind: EventKind,
        step_name: str | None,
        payload: dict[str, Any],
        created_at: str,
    ) -> Event:
        """追加一条事件并返回它。

        `seq` 由数据库分配，因此返回值里的序号就是权威序号，调用方不必自己编号；
        `kind` 按枚举的线上取值（如 `step_completed`）落盘。
        """
        cursor = self._conn.execute(
            _INSERT_EVENT, (run_id, str(kind), step_name, json.dumps(payload), created_at)
        )
        # AUTOINCREMENT 从 1 开始，INSERT 之后 lastrowid 必然存在；`or 0` 只为收敛类型
        seq = int(cursor.lastrowid or 0)
        return Event(
            seq=seq,
            run_id=run_id,
            kind=kind,
            step_name=step_name,
            payload=payload,
            created_at=created_at,
        )

    def load_events(self, run_id: str) -> list[Event]:
        """按 `seq` 升序返回该 run 的全部事件。

        该 run 一条事件都没有时抛 `RunNotFoundError`（`runs` 里有记录也算）：空事件流
        无法重建出任何状态，把它当"零个事件"返回只会把错误推到更晚、更难查的地方。
        """
        rows = self._conn.execute(_SELECT_EVENTS, (run_id,)).fetchall()
        if not rows:
            raise RunNotFoundError(f"no events recorded for run {run_id}")
        return [
            Event(
                seq=row["seq"],
                run_id=row["run_id"],
                kind=EventKind(row["kind"]),
                step_name=row["step_name"],
                payload=json.loads(row["payload_json"]),
                created_at=row["created_at"],
            )
            for row in rows
        ]

    def get_run(self, run_id: str) -> RunRecord | None:
        """返回运行记录；未知 `run_id` 返回 `None` —— "查无此 run"不是错误。"""
        row = self._conn.execute(_SELECT_RUN, (run_id,)).fetchone()
        return None if row is None else _row_to_record(row)

    def set_run_status(self, run_id: str, status: str, result: Any = None) -> None:
        """更新运行状态与结果；未知 `run_id` 抛 `RunNotFoundError`。

        `result` 默认为 `None`，此时 `result_json` 落成 SQL NULL（未产出结果）。
        """
        if self.get_run(run_id) is None:
            raise RunNotFoundError(f"unknown run {run_id}")
        self._conn.execute(_UPDATE_STATUS, (status, _dump(result), run_id))

    def list_runs(self, limit: int = 50) -> list[RunRecord]:
        """按 `created_at` 倒序返回最近的运行，最多 `limit` 条。"""
        rows = self._conn.execute(_SELECT_RUNS, (limit,)).fetchall()
        return [_row_to_record(row) for row in rows]
