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


def test_answer():
    assert state_check(3) == 8
    assert state_check(4) == 12
    assert state_check(5) == 11
    assert state_check(6) == 12
    assert state_check(7) == 8