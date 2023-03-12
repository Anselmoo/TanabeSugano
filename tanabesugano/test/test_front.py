from typing import Any

from tanabesugano import cmd as frontapp


def test_frontapp():
    return frontapp.CMDmain(
        Dq=4000.0, B=400.0, C=3600.0, nroots=100, d_count=5
    ).calculation()


def test_cmd(script_runner: Any) -> None:
    ret = script_runner.run("tanabesugano", "--help")
    assert ret.success
