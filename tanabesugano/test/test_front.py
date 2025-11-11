"""Tests for frontend interface."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tanabesugano import cmd as frontapp


if TYPE_CHECKING:
    from pytest_console_scripts import ScriptRunner


def test_frontapp():
    return frontapp.CMDmain(
        Dq=4000.0,
        B=400.0,
        C=3600.0,
        nroots=100,
        d_count=5,
    ).calculation()


def test_cmd(script_runner: ScriptRunner) -> None:
    ret = script_runner.run("tanabesugano", "--help")
    assert ret.success
