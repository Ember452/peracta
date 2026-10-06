"""core.ids：run_id 生成。此处非确定性是安全的 —— ID 一经生成即写入日志。"""

from __future__ import annotations

from peracta.core.ids import new_run_id


def test_new_run_id_is_prefixed_and_has_a_body() -> None:
    run_id = new_run_id()

    assert isinstance(run_id, str)
    assert run_id.startswith("run_")
    assert len(run_id) > len("run_")


def test_two_calls_do_not_collide() -> None:
    assert new_run_id() != new_run_id()


def test_many_calls_stay_unique() -> None:
    # 单次比对抓不住"每次返回同一个常量再拼随机数"的错法，这里用样本量压它
    ids = {new_run_id() for _ in range(1000)}

    assert len(ids) == 1000
