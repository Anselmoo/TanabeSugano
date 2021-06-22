from tanabesugano import __main__ as frontapp


def test_frontapp():
    return frontapp.CMDmain(
        Dq=4000.0, B=400.0, C=3600.0, nroots=100, mode=5
    ).calculation()
    assert True



