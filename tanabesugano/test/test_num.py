from __future__ import annotations

import numpy as np

from tanabesugano import matrices


def state_check(x) -> int:
    for i in np.linspace(0, 1500, 30):
        if x == 2:
            states = matrices.d2(Dq=i).solver()
            return len(states)
        if x == 3:
            states = matrices.d3(Dq=i).solver()
            return len(states)
        if x == 4:
            states = matrices.d4(Dq=i).solver()
            return len(states)
        if x == 5:
            states = matrices.d5(Dq=i).solver()
            return len(states)
        if x == 6:
            states = matrices.d6(Dq=i).solver()
            return len(states)
        if x == 7:
            states = matrices.d7(Dq=i).solver()
            return len(states)
        if x == 8:
            states = matrices.d8(Dq=i).solver()
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
