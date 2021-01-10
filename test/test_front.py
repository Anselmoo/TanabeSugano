from test import frontapp


def calc_case():
    return frontapp.CMDmain(
        Dq=4000.0, B=400.0, C=3600.0, nroots=100, mode=5
    ).calculation()


def test_answer():
    calc_case()
