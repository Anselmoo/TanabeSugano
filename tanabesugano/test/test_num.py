"""Tests for numerical calculations."""

from __future__ import annotations

import numpy as np

from tanabesugano import matrices


def state_check(x: int) -> int | None:
    state_functions = {
        2: matrices.d2,
        3: matrices.d3,
        4: matrices.d4,
        5: matrices.d5,
        6: matrices.d6,
        7: matrices.d7,
        8: matrices.d8,
    }

    if x not in state_functions:
        return None

    for i in np.linspace(0, 1500, 30):
        states = state_functions[x](Dq=i).solver()
        return len(states)

    return None


def test_answer_d2() -> None:
    assert state_check(2) == 7


def test_answer_d3() -> None:
    assert state_check(3) == 8


def test_answer_d4() -> None:
    assert state_check(4) == 12


def test_answer_d5() -> None:
    assert state_check(5) == 11


def test_answer_d6() -> None:
    assert state_check(6) == 12


def test_answer_d7() -> None:
    assert state_check(7) == 8
