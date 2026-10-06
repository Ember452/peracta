import peracta


def test_version_is_exposed() -> None:
    assert peracta.__version__ == "0.1.0"
