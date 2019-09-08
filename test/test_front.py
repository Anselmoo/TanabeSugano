from test import *

def calc_case():
	return frontapp.CMDmain(Dq=4000., B=400., C=3600., nroots=100, mode=5).calculation()
def test_answer():
	calc_case()
