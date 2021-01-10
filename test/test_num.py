from test import *


def state_check(x):
    for i in np.linspace(0, 1500, 30):
        if x == 3:
            states = matrices.d3(Dq=i).solver()
            return len(states)
        elif x == 4:
            states = matrices.d4(Dq=i).solver()
            return len(states)
        elif x == 5:
            states = matrices.d5(Dq=i).solver()
            return len(states)
        elif x == 6:
            states = matrices.d6(Dq=i).solver()
            return len(states)
        elif x == 7:
            states = matrices.d7(Dq=i).solver()
            return len(states)


def test_answer_d3():
    assert state_check(3) == 8


def test_answer_d4():
    assert state_check(4) == 12


def test_answer_d5():
    assert state_check(5) == 11


def test_answer_d6():
    assert state_check(6) == 12


def test_answer_d7():
    assert state_check(7) == 8
