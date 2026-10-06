"""命令行入口：run / resume / ps 三个子命令与退出码契约。

退出码固定为：`0` 成功、`1` 运行失败、`2` 用法错误。终端文本只在这里产生 ——
内核层不 print；任何 `PeractaError` 都在这里被翻译成一行人话与对应退出码，
而不是把堆栈泼给用户。
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path
from typing import Any

from peracta.core.clock import SystemClock
from peracta.core.errors import ConfigurationError, PeractaError
from peracta.journal.replay import STATUS_FAILED, STATUS_RUNNING
from peracta.journal.sqlite_store import SqliteJournal
from peracta.runtime.executor import execute
from peracta.runtime.flow import Flow

DEFAULT_DB = Path(".peracta/journal.sqlite")
EXIT_OK = 0
EXIT_FAILED = 1
EXIT_USAGE = 2


def _load_flow(path: Path) -> Flow:
    """加载用户脚本在模块级定义的**恰好一个** `Flow` 实例。

    不按"变量名叫 `flow`"去找：示例脚本都要 `from peracta import flow`，
    那个名字上绑的是装饰器本身，按名字找永远会撞上它。改为扫描模块命名空间
    里的 `Flow` 实例：一个都没有说明没写流程，多于一个说明没声明哪个是入口，
    两种都按用法错误拒绝。
    """
    if not path.is_file():
        raise ConfigurationError(f"no such flow file: {path}")
    spec = importlib.util.spec_from_file_location("_peracta_user_flow", path)
    if spec is None or spec.loader is None:
        raise ConfigurationError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    flows = [obj for obj in vars(module).values() if isinstance(obj, Flow)]
    if len(flows) != 1:
        raise ConfigurationError(
            f"{path} must define exactly one module-level @flow (found {len(flows)})"
        )
    return flows[0]


def _parse_inputs(pairs: list[str]) -> dict[str, Any]:
    """把 `--input k=v` 重复项解析成 inputs 字典。"""
    inputs: dict[str, Any] = {}
    for pair in pairs:
        key, sep, raw = pair.partition("=")
        if not sep or not key:
            raise ConfigurationError(f"--input expects key=value, got {pair!r}")
        inputs[key] = _coerce(raw)
    return inputs


def _coerce(raw: str) -> Any:
    """把命令行字符串粗略转成 int / bool / str：V0.1 的 inputs 就这三种。"""
    try:
        return int(raw)
    except ValueError:
        pass
    if raw.lower() in {"true", "false"}:
        return raw.lower() == "true"
    return raw


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="peracta", description="Durable execution kernel")
    sub = parser.add_subparsers(dest="command", required=True)

    run_cmd = sub.add_parser("run", help="start a new run")
    run_cmd.add_argument("file", type=Path)
    run_cmd.add_argument("--input", action="append", default=[])
    _add_db(run_cmd)

    resume_cmd = sub.add_parser("resume", help="continue an interrupted run")
    # run_id 是唯一可选的位置参数（计划 Task 6 Step 3 的实测结论）：两个位置参数
    # 都可选时，`resume f.py --last` 会把 `f.py` 误配给 run_id。
    resume_cmd.add_argument("run_id", nargs="?")
    resume_cmd.add_argument("file", type=Path)
    resume_cmd.add_argument(
        "--last", action="store_true", help="resume the most recent unfinished run"
    )
    _add_db(resume_cmd)

    ps_cmd = sub.add_parser("ps", help="list runs")
    ps_cmd.add_argument("--limit", type=int, default=20)
    _add_db(ps_cmd)
    return parser


def _add_db(cmd: argparse.ArgumentParser) -> None:
    """给子命令挂上 `--db`。必须挂在子命令上而不是主解析器：argparse 只接受
    出现在子命令之前的主解析器选项，而调用习惯是 `run <file> --db <path>`。"""
    cmd.add_argument("--db", type=Path, default=DEFAULT_DB, help="journal file path")


def main(argv: list[str] | None = None) -> int:
    """CLI 主入口；返回值就是进程退出码（0 / 1 / 2）。"""
    parser = _build_parser()
    args = parser.parse_args(argv)
    clock = SystemClock()

    try:
        with SqliteJournal(args.db) as journal:
            if args.command == "run":
                flow_obj = _load_flow(args.file)
                result = execute(flow_obj, journal, clock, inputs=_parse_inputs(args.input))
                print(f"{result.run_id} {result.status} result={result.result!r}")
                return EXIT_OK
            if args.command == "resume":
                flow_obj = _load_flow(args.file)
                run_id = args.run_id
                if args.last:
                    # list_runs 按 created_at 倒序（同刻按 rowid 兜底），首个即最近一次
                    pending = [
                        record
                        for record in journal.list_runs(limit=100)
                        if record.status in {STATUS_RUNNING, STATUS_FAILED}
                    ]
                    if not pending:
                        raise ConfigurationError("no unfinished run to resume")
                    run_id = pending[0].run_id
                if not run_id:
                    raise ConfigurationError("resume needs a run id or --last")
                result = execute(flow_obj, journal, clock, run_id=run_id)
                print(f"{result.run_id} {result.status} result={result.result!r}")
                return EXIT_OK
            for record in journal.list_runs(limit=args.limit):
                print(f"{record.run_id}  {record.flow_name}  {record.status}  {record.created_at}")
            return EXIT_OK
    except ConfigurationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USAGE
    except PeractaError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_FAILED


if __name__ == "__main__":
    raise SystemExit(main())
