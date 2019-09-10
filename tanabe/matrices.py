from __future__ import print_function

import numpy as np
from numpy.linalg import eigh

_sqrt2 = np.sqrt(2.)
_sqrt3 = np.sqrt(3.)
_sqrt6 = np.sqrt(6.)

_2sqrt2 = _sqrt2 * 2.
_2sqrt3 = _sqrt3 * 2.
_3sqrt2 = _sqrt2 * 3.
_3sqrt3 = _sqrt3 * 3.
_3sqrt6 = _sqrt6 * 3.

hallo = 'hallo'


class d3(object):
	def __init__(self, Dq=0., B=918., C=4133.):
		"""
		:parameter
		---------
		All parameters in wavenumbers (cm-)

		Dq: float
			Crystalfield-Splitting
		B: float
			Racah-Parameter
		C: float
			Racah-Parameter

		:returns
		-------

		dictionary with elements of:
			* Atomic-Termsymbols: str
			* Eigen-Energies: float numpy-array
				Eigen-Energies of the atomic states depending on the crystalfield

		"""
		self.Dq = np.float64(Dq)
		self.B = np.float64(B)
		self.C = np.float64(C)

	def T_2_2_states(self):
		# -  diagonal elements

		aa = -12 * self.Dq + 5 * self.C
		bb = - 2 * self.Dq - 6 * self.B + 3 * self.C
		cc = - 2 * self.Dq + 4 * self.B + 3 * self.C
		dd = + 8 * self.Dq + 6 * self.B + 5 * self.C
		ee = + 8 * self.Dq - 2 * self.B + 3 * self.C

		# non diagonal elements

		ab = ba = - _3sqrt3 * self.B
		ac = ca = - 5 * _sqrt3 * self.B
		ad = da = 4 * self.B + 2 * self.C
		ae = ea = 2 * self.B

		bc = cb = 3 * self.B
		bd = db = - _3sqrt3 * self.B
		be = eb = - _3sqrt3 * self.B

		cd = dc = -_sqrt3 * self.B
		ce = ec = +_sqrt3 * self.B

		de = ed = 10 * self.B

		states = np.array([
			[aa, ab, ac, ad, ae],
			[ba, bb, bc, bd, be],
			[ca, cb, cc, cd, ce],
			[da, db, dc, dd, de],
			[ea, eb, ec, ed, ee]
		])

		return self.eigensolver(states)

	def T_2_1_states(self):
		# -  diagonal elements

		aa = -12 * self.Dq - 6 * self.B + 3 * self.C
		bb = - 2 * self.Dq + 3 * self.C
		cc = - 2 * self.Dq - 6 * self.B + 3 * self.C
		dd = + 8 * self.Dq - 6 * self.B + 3 * self.C
		ee = + 8 * self.Dq - 2 * self.B + 3 * self.C

		# non diagonal elements

		ab = ba = - 3 * self.B
		ac = ca = + 3 * self.B
		ad = da = 0.
		ae = ea = - _2sqrt3 * self.B

		bc = cb = - 3 * self.B
		bd = db = + 3 * self.B
		be = eb = _3sqrt3 * self.B

		cd = dc = - 3 * self.B
		ce = ec = - _sqrt3 * self.B

		de = ed = _2sqrt3 * self.B

		states = np.array([
			[aa, ab, ac, ad, ae],
			[ba, bb, bc, bd, be],
			[ca, cb, cc, cd, ce],
			[da, db, dc, dd, de],
			[ea, eb, ec, ed, ee]
		])

		return self.eigensolver(states)

	def E_2_states(self):
		# -  diagonal elements

		aa = -12 * self.Dq - 6 * self.B + 3 * self.C
		bb = - 2 * self.Dq + 8 * self.B + 6 * self.C
		cc = - 2 * self.Dq - 1 * self.B + 3 * self.C
		dd = +18 * self.Dq - 8 * self.B + 4 * self.C

		# non diagonal elements

		ab = ba = - 6 * _sqrt2 * self.B
		ac = ca = - _3sqrt2 * self.B
		ad = da = 0.

		bc = cb = 10 * self.B
		bd = db = + _sqrt3 * (2 * self.B + self.C)

		cd = dc = _2sqrt3 * self.B

		states = np.array([
			[aa, ab, ac, ad],
			[ba, bb, bc, bd],
			[ca, cb, cc, cd],
			[da, db, dc, dd]
		])

		return self.eigensolver(states)

	def T_4_1_states(self):
		# -  diagonal elements

		aa = - 2 * self.Dq - 3 * self.B
		bb = + 8 * self.Dq - 12 * self.B

		# non diagonal elements

		ab = ba = 6 * self.B

		states = np.array([
			[aa, ab],
			[ba, bb]
		])

		return self.eigensolver(states)

	def eigensolver(self, M):
		"""

		:param M: 2 dimensional square array == TS matrics of Ligand field Hamiltonian
		:return: 1 dimensiona                                 l array == eigenvalues of the diagonalized Ligand field Hamiltonian
		"""

		return eigh(M)[0]

	def solver(self):
		# Ligand field independent states

		# Ligendfield single depentent states

		GS = np.array([-12 * self.Dq - 15 * self.B])

		A_4_2 = np.array([0], dtype=np.float)
		T_4_2 = np.array([- 2 * self.Dq - 15 * self.B]) - GS

		A_2_1 = np.array([- 2 * self.Dq - 11 * self.B + 3 * self.C]) - GS
		A_2_2 = np.array([- 2 * self.Dq + 9 * self.B + 3 * self.C]) - GS

		# Ligandfield dependent
		T_2_2 = self.T_2_2_states() - GS
		T_2_1 = self.T_2_1_states() - GS
		E_2 = self.E_2_states() - GS
		T_4_1 = self.T_4_1_states() - GS

		return {'2_T_2': T_2_2, '2_T_1': T_2_1, '2_E': E_2, '4_T_1': T_4_1,
		        '4_A_2': A_4_2, '4_T_2': T_4_2, '2_A_1': A_2_1, '2_A_2': A_2_2}


class d4(object):
	def __init__(self, Dq=0., B=1182., C=4362.):
		"""
		:parameter
		---------
		All parameters in wavenumbers (cm-)

		Dq: float
			Crystalfield-Splitting
		B: float
			Racah-Parameter
		C: float
			Racah-Parameter

		:returns
		-------

		dictionary with elements of:
			* Atomic-Termsymbols: str
			* Eigen-Energies: float numpy-array
				Eigen-Energies of the atomic states depending on the crystalfield

		"""
		self.Dq = np.float64(Dq)
		self.B = np.float64(B)
		self.C = np.float64(C)

	def T_3_1_states(self):
		# -  diagonal elements

		aa = -16 * self.Dq - 15 * self.B + 5 * self.C
		bb = - 6 * self.Dq - 11 * self.B + 4 * self.C
		cc = - 6 * self.Dq - 3 * self.B + 6 * self.C
		dd = 4 * self.Dq - self.B + 6 * self.C
		ee = 4 * self.Dq - 9 * self.B + 4 * self.C
		ff = 4 * self.Dq - 11 * self.B + 4 * self.C
		gg = 14 * self.Dq - 16 * self.B + 5 * self.C

		# non diagonal elements

		ab = ba = _sqrt6 * self.B
		ac = ca = _3sqrt2 * self.B
		ad = da = - _sqrt2 * (2 * self.B + self.C)
		ae = ea = _2sqrt2 * self.B
		af = fa = 0.
		ag = ga = 0.

		bc = cb = 5 * _sqrt3 * self.B
		bd = db = _sqrt3 * self.B
		be = eb = -_sqrt3 * self.B
		bf = fb = 3 * self.B
		bg = gb = _sqrt6 * self.B

		cd = dc = -3 * self.B
		ce = ec = -3 * self.B
		cf = fc = 5 * _sqrt3 * self.B
		cg = gc = _sqrt2 * (self.B + self.C)

		de = ed = -10 * self.B
		df = fd = 0.
		dg = gd = _3sqrt2 * self.B

		ef = fe = - 2 * _sqrt3 * self.B
		eg = ge = - _3sqrt2 * self.B

		fg = gf = _sqrt6 * self.B

		states = np.array([
			[aa, ab, ac, ad, ae, af, ag],
			[ba, bb, bc, bd, be, bf, bg],
			[ca, cb, cc, cd, ce, cf, cg],
			[da, db, dc, dd, de, df, dg],
			[ea, eb, ec, ed, ee, ef, eg],
			[fa, fb, fc, fd, fe, ff, fg],
			[ga, gb, gc, gd, ge, gf, gg]
		])

		return self.eigensolver(states)

	def T_1_2_states(self):
		# diagonal elements

		aa = -16 * self.Dq - 9 * self.B + 7 * self.C
		bb = - 6 * self.Dq - 9 * self.B + 6 * self.C
		cc = - 6 * self.Dq + 3 * self.B + 8 * self.C
		dd = 4 * self.Dq - 9 * self.B + 6 * self.C
		ee = 4 * self.Dq - 3 * self.B + 6 * self.C
		ff = 4 * self.Dq + 5 * self.B + 8 * self.C
		gg = 14 * self.Dq + 7 * self.C

		# non diagonal elements

		ab = ba = - _3sqrt2 * self.B
		ac = ca = 5 * _sqrt6 * self.B
		ad = da = 0.
		ae = ea = _2sqrt2 * self.B
		af = fa = - _sqrt2 * (2 * self.B + self.C)
		ag = ga = 0.

		bc = cb = -5 * _sqrt3 * self.B
		bd = db = 3 * self.B
		be = eb = -3 * self.B
		bf = fb = -3 * self.B
		bg = gb = -_sqrt6 * self.B

		cd = dc = -3 * _sqrt3 * self.B
		ce = ec = 5 * _sqrt3 * self.B
		cf = fc = -5 * _sqrt3 * self.B
		cg = gc = _sqrt2 * (3 * self.B + self.C)

		de = ed = -6 * self.B
		df = fd = 0.
		dg = gd = - _3sqrt6 * self.B

		ef = fe = - 10 * self.B
		eg = ge = _sqrt6 * self.B

		fg = gf = _sqrt6 * self.B

		states = np.array([
			[aa, ab, ac, ad, ae, af, ag],
			[ba, bb, bc, bd, be, bf, bg],
			[ca, cb, cc, cd, ce, cf, cg],
			[da, db, dc, dd, de, df, dg],
			[ea, eb, ec, ed, ee, ef, eg],
			[fa, fb, fc, fd, fe, ff, fg],
			[ga, gb, gc, gd, ge, gf, gg]
		])

		return self.eigensolver(states)

	def A_1_1_states(self):
		# diagonal elements

		aa = -16 * self.Dq + 10 * self.C
		bb = - 6 * self.Dq + 6 * self.C
		cc = 4 * self.Dq + 14 * self.B + 11 * self.C
		dd = 4 * self.Dq - 3 * self.B + 6 * self.C
		ee = 24 * self.Dq - 16 * self.B + 8 * self.C

		# non diagonal elements

		ab = ba = - 12 * _sqrt2 * self.B
		ac = ca = _sqrt2 * (4 * self.B + 2 * self.C)
		ad = da = _2sqrt2 * self.B
		ae = ea = 0.

		bc = cb = -12 * self.B
		bd = db = -6 * self.B
		be = eb = 0.

		cd = dc = 20 * self.B
		ce = ec = _sqrt6 * (2 * self.B + self.C)

		de = ed = 2 * _sqrt6 * self.B

		states = np.array([
			[aa, ab, ac, ad, ae],
			[ba, bb, bc, bd, be],
			[ca, cb, cc, cd, ce],
			[da, db, dc, dd, de],
			[ea, eb, ec, ed, ee]
		])

		return self.eigensolver(states)

	def E_1_1_states(self):
		# diagonal elements

		aa = -16 * self.Dq - 9 * self.B + 7 * self.C
		bb = - 6 * self.Dq - 6 * self.B + 6 * self.C
		cc = 4 * self.Dq + 5 * self.B + 8 * self.C
		dd = 4 * self.Dq + 6 * self.B + 9 * self.C
		ee = 4 * self.Dq - 3 * self.B + 6 * self.C

		# non diagonal elements

		ab = ba = - 6 * self.B
		ac = ca = _sqrt2 * (2 * self.B + self.C)
		ad = da = 2 * self.B
		ae = ea = 4 * self.B

		bc = cb = -_3sqrt2 * self.B
		bd = db = -12 * self.B
		be = eb = 0.

		cd = dc = 10 * _sqrt2 * self.B
		ce = ec = -10 * _sqrt2 * self.B

		de = ed = 0.

		states = np.array([
			[aa, ab, ac, ad, ae],
			[ba, bb, bc, bd, be],
			[ca, cb, cc, cd, ce],
			[da, db, dc, dd, de],
			[ea, eb, ec, ed, ee]
		])

		return self.eigensolver(states)

	def T_3_2_states(self):
		# diagonal elements

		aa = - 6 * self.Dq - 9 * self.B + 4 * self.C
		bb = - 6 * self.Dq - 5 * self.B + 6 * self.C
		cc = 4 * self.Dq - 13 * self.B + 4 * self.C
		dd = 4 * self.Dq - 9 * self.B + 4 * self.C
		ee = 14 * self.Dq - 8 * self.B + 5 * self.C

		# non diagonal elements

		ab = ba = - 5 * _sqrt3 * self.B
		ac = ca = _sqrt6 * self.B
		ad = da = _sqrt3 * self.B
		ae = ea = _sqrt6 * self.B

		bc = cb = -_3sqrt2 * self.B
		bd = db = 3 * self.B
		be = eb = _sqrt2 * (3 * self.B + self.C)

		cd = dc = -2 * _sqrt2 * self.B
		ce = ec = -6 * self.B

		de = ed = - 8 * self.B + 5 * self.C

		states = np.array([
			[aa, ab, ac, ad, ae],
			[ba, bb, bc, bd, be],
			[ca, cb, cc, cd, ce],
			[da, db, dc, dd, de],
			[ea, eb, ec, ed, ee]
		])

		return self.eigensolver(states)

	def T_1_1_states(self):
		# diagonal elements

		aa = - 6 * self.Dq - 3 * self.B + 6 * self.C
		bb = - 6 * self.Dq - 3 * self.B + 8 * self.C
		cc = 4 * self.Dq - 3 * self.B + 6 * self.C
		dd = 14 * self.Dq - 16 * self.B + 7 * self.C

		# non diagonal elements

		ab = ba = - 5 * _sqrt3 * self.B
		ac = ca = 3 * self.B
		ad = da = _sqrt6 * self.B

		bc = cb = - 5 * _sqrt3 * self.B
		bd = db = _sqrt2 * (self.B + self.C)

		cd = dc = -_sqrt6 * self.B

		states = np.array([
			[aa, ab, ac, ad],
			[ba, bb, bc, bd],
			[ca, cb, cc, cd],
			[da, db, dc, dd]
		])

		return self.eigensolver(states)

	def E_3_1_states(self):
		# diagonal elements

		aa = - 6 * self.Dq - 13 * self.B + 4 * self.C
		bb = - 6 * self.Dq - 10 * self.B + 4 * self.C
		cc = 4 * self.Dq - 11 * self.B + 4 * self.C

		# non diagonal elements

		ab = ba = - 4 * self.B
		ac = ca = 0.

		bc = cb = - _3sqrt2 * self.B

		states = np.array([
			[aa, ab, ac],
			[ba, bb, bc],
			[ca, cb, cc]
		])

		return self.eigensolver(states)

	def A_3_2_states(self):
		# diagonal elements

		aa = - 6 * self.Dq - 8 * self.B + 4 * self.C
		bb = 4 * self.Dq - 2 * self.B + 7 * self.C

		# non diagonal elements

		ab = ba = - 12 * self.B

		states = np.array([
			[aa, ab],
			[ba, bb]
		])

		return self.eigensolver(states)

	def A_1_2_states(self):
		# diagonal elements

		aa = - 6 * self.Dq - 12 * self.B + 6 * self.C
		bb = 4 * self.Dq - 3 * self.B + 6 * self.C

		# non diagonal elements

		ab = ba = - 6 * self.B

		states = np.array([
			[aa, ab],
			[ba, bb]
		])

		return self.eigensolver(states)

	def eigensolver(self, M):
		"""

		:param M: 2 dimensional square array == TS matrics of Ligand field Hamiltonian
		:return: 1 dimensional array == eigenvalues of the diagonalized Ligand field Hamiltonian
		"""

		return eigh(M)[0]

	def solver(self):
		# Ligand field independent states

		# A_6_1 = np.array( [ 0 ] )  # Starting value is -35. * B, but has to set to zero per definition
		# E_4 = self.E_4_states( ) + 35 * self.B
		# A_4_1 = np.array( [ -25 * self.B + 5 * self.C ] ) + 35 * self.B
		# A_4_2 = np.array( [ -13 * self.B + 7 * self.C ] ) + 35 * self.B

		# Ligendfield single depentent states

		GS = np.array([-6 * self.Dq - 21 * self.B])

		E_5_1 = np.array([0], dtype=np.float)
		T_5_2 = np.array([4 * self.Dq - 21 * self.B]) - GS

		A_3_1 = np.array([- 6 * self.Dq - 12 * self.B + 4 * self.C]) - GS

		# Ligandfield dependent
		T_1_2 = self.T_1_2_states() - GS
		T_3_1 = self.T_3_1_states() - GS
		A_1_1 = self.A_1_1_states() - GS
		E_1_1 = self.E_1_1_states() - GS
		T_3_2 = self.T_3_2_states() - GS
		T_1_1 = self.T_1_1_states() - GS
		E_3_1 = self.E_3_1_states() - GS
		A_3_2 = self.A_3_2_states() - GS
		A_1_2 = self.A_1_2_states() - GS

		if T_3_1[0] <= 0:
			T_1_2 -= T_3_1[0]

			A_1_1 -= T_3_1[0]
			E_1_1 -= T_3_1[0]
			T_3_2 -= T_3_1[0]
			T_1_1 -= T_3_1[0]
			E_3_1 -= T_3_1[0]
			A_3_2 -= T_3_1[0]
			A_1_2 -= T_3_1[0]
			T_3_1 -= T_3_1[0]
		return {'3_T_1': T_3_1, '1_T_2': T_1_2, '1_A_1': A_1_1, '1_E_1': E_1_1, '3_T_2': T_3_2, '1_T_1': T_1_1,
		        '3_E_1': E_3_1, '3_A_2': A_3_2, '1_A_2': A_1_2, '5_E_1': E_5_1, '5_T_2': T_5_2, '3_A_1': A_3_1}


class d5(object):
	def __init__(self, Dq=0., B=1293., C=4823.):
		"""
		:parameter
		---------
		All parameters in wavenumbers (cm-)

		Dq: float
			Crystalfield-Splitting
		B: float
			Racah-Parameter
		C: float
			Racah-Parameter

		:returns
		-------

		dictionary with elements of:
			* Atomic-Termsymbols: str
			* Eigen-Energies: float numpy-array
				Eigen-Energies of the atomic states depending on the crystalfield

		"""
		self.Dq = np.float64(Dq)
		self.B = np.float64(B)
		self.C = np.float64(C)

	def T_2_2_states(self):
		# diagonal elements

		aa = -20 * self.Dq - 20 * self.B + 10 * self.C
		bb = -10 * self.Dq - 8 * self.B + 9 * self.C
		cc = -10 * self.Dq - 18 * self.B + 9 * self.C
		dd = - 16 * self.B + 8 * self.C
		ee = - 12 * self.B + 8 * self.C
		ff = 2 * self.B + 12 * self.C
		gg = -  6 * self.B + 10 * self.C
		HH = 10 * self.Dq - 18 * self.B + 9 * self.C
		II = 10 * self.Dq - 8 * self.B + 9 * self.C
		JJ = 20 * self.Dq - 20 * self.B + 10 * self.C

		# non diagonal elements

		ab = ba = -_3sqrt6 * self.B
		ac = ca = -_sqrt6 * self.B
		ad = da = 0.
		ae = ea = -2 * _sqrt3 * self.B
		af = fa = 4 * self.B + 2 * self.C
		ag = ga = 2 * self.B
		AH = HA = 0.
		AI = IA = 0.
		AJ = JA = 0.

		bc = cb = 3 * self.B
		bd = db = -_sqrt6 / 2. * self.B
		be = eb = _3sqrt2 / 2. * self.B
		bf = fb = -_3sqrt6 / 2. * self.B
		bg = gb = -_3sqrt6 / 2. * self.B
		BH = HB = 0.
		BI = IB = -4 * self.B + self.C
		BJ = JB = 0.

		cd = dc = -_3sqrt6 / 2. * self.B
		ce = ec = _3sqrt2 / 2. * self.B
		cf = fc = -5 * _sqrt6 / 2. * self.B
		cg = gc = +5 * _sqrt6 / 2. * self.B
		CH = HC = -self.C
		CI = IC = 0.
		CJ = JC = 0.

		de = ed = 2 * _sqrt3 * self.B
		df = fd = 0.
		dg = gd = 0.
		DH = HD = -_3sqrt6 / 2. * self.B
		DI = ID = -_sqrt6 / 2. * self.B
		DJ = JD = 0.

		ef = fe = -10 * _sqrt3 * self.B
		eg = ge = 0.
		EH = HE = _3sqrt2 / 2. * self.B
		EI = IE = _3sqrt2 / 2. * self.B
		EJ = JE = -2 * _sqrt3 * self.B

		fg = gf = 0.
		FH = HF = -5 * _sqrt6 / 2. * self.B
		FI = IF = -_3sqrt6 / 2. * self.B
		FJ = JF = 4 * self.B + 2 * self.C

		GH = HG = -5 * _sqrt6 / 2. * self.B
		GI = IG = _3sqrt6 / 2. * self.B
		GJ = JG = -2. * self.B

		HI = IH = 3 * self.B
		HJ = JH = -_sqrt6 * self.B

		IJ = JI = -_3sqrt6 * self.B

		states = np.array([
			[aa, ab, ac, ad, ae, af, ag, AH, AI, AJ],
			[ba, bb, bc, bd, be, bf, bg, BH, BI, BJ],
			[ca, cb, cc, cd, ce, cf, cg, CH, CI, CJ],
			[da, db, dc, dd, de, df, dg, DH, DI, DJ],
			[ea, eb, ec, ed, ee, ef, eg, EH, EI, EJ],
			[fa, fb, fc, fd, fe, ff, fg, FH, FI, FJ],
			[ga, gb, gc, gd, ge, gf, gg, GH, GI, GJ],
			[HA, HB, HC, HD, HE, HF, HG, HH, HI, HJ],
			[IA, IB, IC, ID, IE, IF, IG, IH, II, IJ],
			[JA, JB, JC, JD, JE, JF, JG, JH, JI, JJ]
		])

		return self.eigensolver(states)

	def T_2_1_states(self):
		# diagonal elements

		aa = -10 * self.Dq - 22 * self.B + 9 * self.C
		bb = -10 * self.Dq - 8 * self.B + 9 * self.C
		cc = -  4 * self.B + 10 * self.C
		dd = - 12 * self.B + 8 * self.C
		ee = - 10 * self.B + 10 * self.C
		ff = -  6 * self.B + 10 * self.C
		gg = 10 * self.Dq - 8 * self.B + 9 * self.C
		HH = 10 * self.Dq - 22 * self.B + 9 * self.C

		# non diagonal elements

		ab = ba = -3 * self.B
		ac = ca = _3sqrt2 / 2. * self.B
		ad = da = -_3sqrt2 / 2. * self.B
		ae = ea = _3sqrt2 / 2. * self.B
		af = fa = _3sqrt6 / 2. * self.B
		ag = ga = 0.
		AH = HA = -self.C

		bc = cb = -_3sqrt2 / 2. * self.B
		bd = db = -_3sqrt2 / 2. * self.B
		be = eb = -15 * _sqrt2 / 2. * self.B
		bf = fb = -5 * _sqrt6 / 2. * self.B
		bg = gb = -4 * self.B - self.C
		BH = HB = 0.

		cd = dc = 0.
		ce = ec = 0.
		cf = fc = 10 * _sqrt3 * self.B
		cg = gc = _3sqrt2 / 2. * self.B
		CH = HC = -_3sqrt2 / 2. * self.B

		de = ed = 0.
		df = fd = 0.
		dg = gd = -_3sqrt2 / 2. * self.B
		DH = HD = -_3sqrt2 / 2. * self.B

		ef = fe = 2 * _sqrt3 * self.B
		eg = ge = 15 * _sqrt2 / 2. * self.B
		EH = HE = -_3sqrt2 / 2. * self.B

		fg = gf = 5 * _sqrt6 / 2. * self.B
		FH = HF = -_3sqrt6 / 2. * self.B

		GH = HG = -3 * self.B

		states = np.array([
			[aa, ab, ac, ad, ae, af, ag, AH],
			[ba, bb, bc, bd, be, bf, bg, BH],
			[ca, cb, cc, cd, ce, cf, cg, CH],
			[da, db, dc, dd, de, df, dg, DH],
			[ea, eb, ec, ed, ee, ef, eg, EH],
			[fa, fb, fc, fd, fe, ff, fg, FH],
			[ga, gb, gc, gd, ge, gf, gg, GH],
			[HA, HB, HC, HD, HE, HF, HG, HH]
		])

		return self.eigensolver(states)

	def E_2_states(self):
		# diagonal elements

		aa = -10 * self.Dq - 4 * self.B + 12 * self.C
		bb = -10 * self.Dq - 13 * self.B + 9 * self.C
		cc = -  4 * self.B + 10 * self.C
		dd = - 16 * self.B + 8 * self.C
		ee = - 12 * self.B + 8 * self.C
		ff = 10 * self.Dq - 13 * self.B + 9 * self.C
		gg = 10 * self.Dq - 4 * self.B + 12 * self.C

		# non diagonal elements

		ab = ba = - 10 * self.B
		ac = ca = 6 * self.B
		ad = da = 6 * _sqrt3 * self.B
		ae = ea = 6 * _sqrt2 * self.B
		af = fa = -2 * self.B
		ag = ga = 4 * self.B + 2 * self.C

		bc = cb = 3 * self.B
		bd = db = -3 * _sqrt3 * self.B
		be = eb = 0.
		bf = fb = -2 * self.B - self.C
		bg = gb = -2 * self.B

		cd = dc = 0.
		ce = ec = 0.
		cf = fc = -3 * self.B
		cg = gc = -6 * self.B

		de = ed = 2 * _sqrt6 * self.B
		df = fd = -3 * _sqrt3 * self.B
		dg = gd = 6 * _sqrt3 * self.B

		ef = fe = 0.
		eg = ge = 6 * _sqrt2 * self.B

		fg = gf = -10 * self.B

		states = np.array([
			[aa, ab, ac, ad, ae, af, ag],
			[ba, bb, bc, bd, be, bf, bg],
			[ca, cb, cc, cd, ce, cf, cg],
			[da, db, dc, dd, de, df, dg],
			[ea, eb, ec, ed, ee, ef, eg],
			[fa, fb, fc, fd, fe, ff, fg],
			[ga, gb, gc, gd, ge, gf, gg]
		])

		return self.eigensolver(states)

	def A_2_1_states(self):
		# diagonal elements

		aa = -10 * self.Dq - 3 * self.B + 9 * self.C
		bb = - 12 * self.B + 8 * self.C
		cc = - 19 * self.B + 8 * self.C
		dd = 10 * self.Dq - 3 * self.B + 9 * self.C

		# non diagonal elements

		ab = ba = _3sqrt2 * self.B
		ac = ca = 0.
		ad = da = -6 * self.B - self.C

		bc = cb = -4 * _sqrt3 * self.B
		bd = db = _3sqrt2 * self.B

		cd = dc = 0.

		states = np.array([
			[aa, ab, ac, ad],
			[ba, bb, bc, bd],
			[ca, cb, cc, cd],
			[da, db, dc, dd]
		])

		return self.eigensolver(states)

	def A_2_2_states(self):
		# diagonal elements

		aa = -10 * self.Dq - 23 * self.B + 9 * self.C
		bb = - 12 * self.B + 8 * self.C
		cc = 10 * self.Dq - 23 * self.B + 9 * self.C

		# non diagonal elements

		ab = ba = -_3sqrt2 * self.B
		ac = ca = _2sqrt2 * self.B - self.C

		bc = cb = -_3sqrt2 * self.B

		states = np.array([
			[aa, ab, ac],
			[ba, bb, bc],
			[ca, cb, cc]
		])

		return self.eigensolver(states)

	def T_4_1_states(self):
		# diagonal elements

		aa = -10 * self.Dq - 25 * self.B + 6 * self.C
		bb = - 16 * self.B + 7 * self.C
		cc = 10 * self.Dq - 25 * self.B + 6 * self.C

		# non diagonal elements

		ab = ba = _3sqrt2 * self.B
		ac = ca = - self.C

		bc = cb = -_3sqrt2 * self.B

		states = np.array([
			[aa, ab, ac],
			[ba, bb, bc],
			[ca, cb, cc]
		])

		return self.eigensolver(states)

	def T_4_2_states(self):
		# diagonal elements

		aa = -10 * self.Dq - 17 * self.B + 6 * self.C
		bb = - 22 * self.B + 5 * self.C
		cc = 10 * self.Dq - 17 * self.B + 6 * self.C

		# non diagonal elements

		ab = ba = -_sqrt6 * self.B
		ac = ca = -4 * self.B - self.C

		bc = cb = - _sqrt6 * self.B

		# ab = bc = ac = 0
		states = np.array([
			[aa, ab, ac],
			[ba, bb, bc],
			[ca, cb, cc]
		])

		return self.eigensolver(states)

	def E_4_states(self):
		# diagonal elements

		aa = - 22 * self.B + 5 * self.C
		bb = - 21 * self.B + 5 * self.C

		# non diagonal elements

		ab = ba = -2 * _sqrt3 * self.B

		states = np.array([
			[aa, ab],
			[ba, bb]
		])

		return self.eigensolver(states)

	def eigensolver(self, M):
		"""

		:param M: 2 dimensional square array == TS matrics of Ligand field Hamiltonian
		:return: 1 dimensional array == eigenvalues of the diagonalized Ligand field Hamiltonian
		"""

		return eigh(M)[0]

	def solver(self):
		# Ligand field independent states
		GS = 35 * self.B

		A_6_1 = np.array([0.], dtype=float)  # Starting value is -35. * B, but has to set to zero per definition
		E_4 = self.E_4_states() + GS
		A_4_1 = np.array([-25 * self.B + 5 * self.C]) + GS
		A_4_2 = np.array([-13 * self.B + 7 * self.C]) + GS

		# Ligandfield dependent
		T_2_2 = self.T_2_2_states() + GS
		T_2_1 = self.T_2_1_states() + GS
		E_2 = self.E_2_states() + GS
		A_2_1 = self.A_2_1_states() + GS
		A_2_2 = self.A_2_2_states() + GS
		T_4_1 = self.T_4_1_states() + GS
		T_4_2 = self.T_4_2_states() + GS

		if T_2_2[0] <= 0:
			A_6_1 -= T_2_2[0]
			E_4 -= T_2_2[0]
			A_4_1 -= T_2_2[0]
			A_4_2 -= T_2_2[0]
			T_2_1 -= T_2_2[0]
			E_2 -= T_2_2[0]
			A_2_1 -= T_2_2[0]
			A_2_2 -= T_2_2[0]
			T_4_1 -= T_2_2[0]
			T_4_2 -= T_2_2[0]
			# Finally create new ligand field independent state
			T_2_2 -= T_2_2[0]

		return {'2_T_2': T_2_2, '2_T_1': T_2_1, '2_E': E_2, '2_A_1': A_2_1, '2_A_2': A_2_2, '4_T_1': T_4_1,
		        '4_T_2': T_4_2, '4_E': E_4, '6_A_1': A_6_1, '4_A_1': A_4_1, '4_A_2': A_4_2}


# return { "2_T_2": T_2_2,"4_E": E_4, '6_A_1': A_6_1, '4_A_1': A_4_1, '4_A_2': A_4_2 }


class d6(object):
	def __init__(self, Dq=0., B=1182., C=4362.):
		"""
		:parameter
		---------
		All parameters in wavenumbers (cm-)

		Dq: float
			Crystalfield-Splitting
		B: float
			Racah-Parameter
		C: float
			Racah-Parameter

		:returns
		-------

		dictionary with elements of:
			* Atomic-Termsymbols: str
			* Eigen-Energies: float numpy-array
				Eigen-Energies of the atomic states depending on the crystalfield

		"""
		self.Dq = np.float64(Dq)
		self.B = np.float64(B)
		self.C = np.float64(C)

	def T_3_1_states(self):
		# -  diagonal elements

		aa = +16 * self.Dq - 15 * self.B + 5 * self.C
		bb = + 6 * self.Dq - 11 * self.B + 4 * self.C
		cc = + 6 * self.Dq - 3 * self.B + 6 * self.C
		dd = -4 * self.Dq - self.B + 6 * self.C
		ee = -4 * self.Dq - 9 * self.B + 4 * self.C
		ff = -4 * self.Dq - 11 * self.B + 4 * self.C
		gg = -14 * self.Dq - 16 * self.B + 5 * self.C

		# non diagonal elements

		ab = ba = -_sqrt6 * self.B
		ac = ca = -_3sqrt2 * self.B
		ad = da = _sqrt2 * (2 * self.B + self.C)
		ae = ea = -_2sqrt2 * self.B
		af = fa = 0.
		ag = ga = 0.

		bc = cb = 5 * _sqrt3 * self.B
		bd = db = _sqrt3 * self.B
		be = eb = -_sqrt3 * self.B
		bf = fb = 3 * self.B
		bg = gb = _sqrt6 * self.B

		cd = dc = -3 * self.B
		ce = ec = -3 * self.B
		cf = fc = 5 * _sqrt3 * self.B
		cg = gc = _sqrt2 * (self.B + self.C)

		de = ed = -10 * self.B
		df = fd = 0.
		dg = gd = _3sqrt2 * self.B

		ef = fe = - 2 * _sqrt3 * self.B
		eg = ge = - _3sqrt2 * self.B

		fg = gf = _sqrt6 * self.B

		states = np.array([
			[aa, ab, ac, ad, ae, af, ag],
			[ba, bb, bc, bd, be, bf, bg],
			[ca, cb, cc, cd, ce, cf, cg],
			[da, db, dc, dd, de, df, dg],
			[ea, eb, ec, ed, ee, ef, eg],
			[fa, fb, fc, fd, fe, ff, fg],
			[ga, gb, gc, gd, ge, gf, gg]
		])

		return self.eigensolver(states)

	def T_1_2_states(self):
		# diagonal elements

		aa = +16 * self.Dq - 9 * self.B + 7 * self.C
		bb = + 6 * self.Dq - 9 * self.B + 6 * self.C
		cc = + 6 * self.Dq + 3 * self.B + 8 * self.C
		dd = -4 * self.Dq - 9 * self.B + 6 * self.C
		ee = -4 * self.Dq - 3 * self.B + 6 * self.C
		ff = -4 * self.Dq + 5 * self.B + 8 * self.C
		gg = -14 * self.Dq + 7 * self.C

		# non diagonal elements

		ab = ba = _3sqrt2 * self.B
		ac = ca = - 5 * _sqrt6 * self.B
		ad = da = 0.
		ae = ea = -_2sqrt2 * self.B
		af = fa = _sqrt2 * (2 * self.B + self.C)
		ag = ga = 0.

		bc = cb = -5 * _sqrt3 * self.B
		bd = db = 3 * self.B
		be = eb = -3 * self.B
		bf = fb = -3 * self.B
		bg = gb = -_sqrt6 * self.B

		cd = dc = -3 * _sqrt3 * self.B
		ce = ec = 5 * _sqrt3 * self.B
		cf = fc = -5 * _sqrt3 * self.B
		cg = gc = _sqrt2 * (3 * self.B + self.C)

		de = ed = -6 * self.B
		df = fd = 0.
		dg = gd = - _3sqrt6 * self.B

		ef = fe = - 10 * self.B
		eg = ge = _sqrt6 * self.B

		fg = gf = _sqrt6 * self.B

		states = np.array([
			[aa, ab, ac, ad, ae, af, ag],
			[ba, bb, bc, bd, be, bf, bg],
			[ca, cb, cc, cd, ce, cf, cg],
			[da, db, dc, dd, de, df, dg],
			[ea, eb, ec, ed, ee, ef, eg],
			[fa, fb, fc, fd, fe, ff, fg],
			[ga, gb, gc, gd, ge, gf, gg]
		])

		return self.eigensolver(states)

	def A_1_1_states(self):
		# diagonal elements

		aa = +16 * self.Dq + 10 * self.C
		bb = + 6 * self.Dq + 6 * self.C
		cc = -4 * self.Dq + 14 * self.B + 11 * self.C
		dd = -4 * self.Dq - 3 * self.B + 6 * self.C
		ee = -24 * self.Dq - 16 * self.B + 8 * self.C

		# non diagonal elements

		ab = ba = - 12 * _sqrt2 * self.B
		ac = ca = _sqrt2 * (4 * self.B + 2 * self.C)
		ad = da = _2sqrt2 * self.B
		ae = ea = 0.

		bc = cb = -12 * self.B
		bd = db = -6 * self.B
		be = eb = 0.

		cd = dc = 20 * self.B
		ce = ec = _sqrt6 * (2 * self.B + self.C)

		de = ed = 2 * _sqrt6 * self.B

		states = np.array([
			[aa, ab, ac, ad, ae],
			[ba, bb, bc, bd, be],
			[ca, cb, cc, cd, ce],
			[da, db, dc, dd, de],
			[ea, eb, ec, ed, ee]
		])

		return self.eigensolver(states)

	def E_1_1_states(self):
		# diagonal elements

		aa = +16 * self.Dq - 9 * self.B + 7 * self.C
		bb = + 6 * self.Dq - 6 * self.B + 6 * self.C
		cc = -4 * self.Dq + 5 * self.B + 8 * self.C
		dd = -4 * self.Dq + 6 * self.B + 9 * self.C
		ee = -4 * self.Dq - 3 * self.B + 6 * self.C

		# non diagonal elements

		ab = ba = 6 * self.B
		ac = ca = _sqrt2 * (2 * self.B + self.C)
		ad = da = -2 * self.B
		ae = ea = -4 * self.B

		bc = cb = -_3sqrt2 * self.B
		bd = db = -12 * self.B
		be = eb = 0.

		cd = dc = 10 * _sqrt2 * self.B
		ce = ec = -10 * _sqrt2 * self.B

		de = ed = 0.

		states = np.array([
			[aa, ab, ac, ad, ae],
			[ba, bb, bc, bd, be],
			[ca, cb, cc, cd, ce],
			[da, db, dc, dd, de],
			[ea, eb, ec, ed, ee]
		])

		return self.eigensolver(states)

	def T_3_2_states(self):
		# diagonal elements

		aa = + 6 * self.Dq - 9 * self.B + 4 * self.C
		bb = + 6 * self.Dq - 5 * self.B + 6 * self.C
		cc = -4 * self.Dq - 13 * self.B + 4 * self.C
		dd = -4 * self.Dq - 9 * self.B + 4 * self.C
		ee = -14 * self.Dq - 8 * self.B + 5 * self.C

		# non diagonal elements

		ab = ba = - 5 * _sqrt3 * self.B
		ac = ca = _sqrt6 * self.B
		ad = da = _sqrt3 * self.B
		ae = ea = -_sqrt6 * self.B

		bc = cb = -_3sqrt2 * self.B
		bd = db = 3 * self.B
		be = eb = _sqrt2 * (3 * self.B + self.C)

		cd = dc = -2 * _sqrt2 * self.B
		ce = ec = -6 * self.B

		de = ed = 3 * _sqrt2 * self.B

		states = np.array([
			[aa, ab, ac, ad, ae],
			[ba, bb, bc, bd, be],
			[ca, cb, cc, cd, ce],
			[da, db, dc, dd, de],
			[ea, eb, ec, ed, ee]
		])

		return self.eigensolver(states)

	def T_1_1_states(self):
		# diagonal elements

		aa = + 6 * self.Dq - 3 * self.B + 6 * self.C
		bb = + 6 * self.Dq - 3 * self.B + 8 * self.C
		cc = -4 * self.Dq - 3 * self.B + 6 * self.C
		dd = -14 * self.Dq - 16 * self.B + 7 * self.C

		# non diagonal elements

		ab = ba = 5 * _sqrt3 * self.B
		ac = ca = 3 * self.B
		ad = da = _sqrt6 * self.B

		bc = cb = - 5 * _sqrt3 * self.B
		bd = db = _sqrt2 * (self.B + self.C)

		cd = dc = -_sqrt6 * self.B

		states = np.array([
			[aa, ab, ac, ad],
			[ba, bb, bc, bd],
			[ca, cb, cc, cd],
			[da, db, dc, dd]
		])

		return self.eigensolver(states)

	def E_3_1_states(self):
		# diagonal elements

		aa = + 6 * self.Dq - 13 * self.B + 4 * self.C
		bb = - 6 * self.Dq - 10 * self.B + 4 * self.C
		cc = -4 * self.Dq - 11 * self.B + 4 * self.C

		# non diagonal elements

		ab = ba = - 4 * self.B
		ac = ca = 0.

		bc = cb = - _3sqrt2 * self.B

		states = np.array([
			[aa, ab, ac],
			[ba, bb, bc],
			[ca, cb, cc]
		])

		return self.eigensolver(states)

	def A_3_2_states(self):
		# diagonal elements

		aa = + 6 * self.Dq - 8 * self.B + 4 * self.C
		bb = -4 * self.Dq - 2 * self.B + 7 * self.C

		# non diagonal elements

		ab = ba = - 12 * self.B

		states = np.array([
			[aa, ab],
			[ba, bb]
		])

		return self.eigensolver(states)

	def A_1_2_states(self):
		# diagonal elements

		aa = + 6 * self.Dq - 12 * self.B + 6 * self.C
		bb = -4 * self.Dq - 3 * self.B + 6 * self.C

		# non diagonal elements

		ab = ba = 6 * self.B

		states = np.array([
			[aa, ab],
			[ba, bb]
		])

		return self.eigensolver(states)

	def eigensolver(self, M):
		"""

		:param M: 2 dimensional square array == TS matrics of Ligand field Hamiltonian
		:return: 1 dimensional array == eigenvalues of the diagonalized Ligand field Hamiltonian
		"""

		return eigh(M)[0]

	def solver(self):
		# Ligand field independent states

		# A_6_1 = np.array( [ 0 ] )  # Starting value is -35. * B, but has to set to zero per definition
		# E_4 = self.E_4_states( ) + 35 * self.B
		# A_4_1 = np.array( [ -25 * self.B + 5 * self.C ] ) + 35 * self.B
		# A_4_2 = np.array( [ -13 * self.B + 7 * self.C ] ) + 35 * self.B

		# Ligendfield single depentent states

		GS = np.array([- 4 * self.Dq - 21 * self.B])

		T_5_2 = np.array([0], dtype=np.float)

		E_5_1 = np.array([6 * self.Dq - 21 * self.B]) - GS

		A_3_1 = np.array([6 * self.Dq - 12 * self.B + 4 * self.C]) - GS

		# Ligandfield dependent
		T_1_2 = - GS + self.T_1_2_states()
		T_3_1 = - GS + self.T_3_1_states()
		A_1_1 = - GS + self.A_1_1_states()
		E_1_1 = - GS + self.E_1_1_states()
		T_3_2 = - GS + self.T_3_2_states()
		T_1_1 = - GS + self.T_1_1_states()
		E_3_1 = - GS + self.E_3_1_states()
		A_3_2 = - GS + self.A_3_2_states()
		A_1_2 = - GS + self.A_1_2_states()

		if A_1_1[0] <= 1e-4:
			T_1_2 -= A_1_1[0]

			E_1_1 -= A_1_1[0]
			T_3_2 -= A_1_1[0]
			T_1_1 -= A_1_1[0]
			E_3_1 -= A_1_1[0]
			A_3_2 -= A_1_1[0]
			A_1_2 -= A_1_1[0]
			T_3_1 -= A_1_1[0]

			E_5_1 -= A_1_1[0]
			T_5_2 -= A_1_1[0]
			A_3_1 -= A_1_1[0]
			A_1_1 -= A_1_1[0]

		return {'3_T_1': T_3_1, '1_T_2': T_1_2, '1_A_1': A_1_1, '1_E_1': E_1_1, '3_T_2': T_3_2, '1_T_1': T_1_1,
		        '3_E_1': E_3_1, '3_A_2': A_3_2, '1_A_2': A_1_2, '5_E_1': E_5_1, '5_T_2': T_5_2, '3_A_1': A_3_1}


class d7(object):
	def __init__(self, Dq=0., B=971., C=4499.):
		"""
		:parameter
		---------
		All parameters in wavenumbers (cm-)

		Dq: float
			Crystalfield-Splitting
		B: float
			Racah-Parameter
		C: float
			Racah-Parameter

		:returns
		-------

		dictionary with elements of:
			* Atomic-Termsymbols: str
			* Eigen-Energies: float numpy-array
				Eigen-Energies of the atomic states depending on the crystalfield

		"""
		self.Dq = np.float64(Dq)
		self.B = np.float64(B)
		self.C = np.float64(C)

	def T_2_2_states(self):
		# -  diagonal elements

		aa = +12 * self.Dq + 5 * self.C
		bb = + 2 * self.Dq - 6 * self.B + 3 * self.C
		cc = + 2 * self.Dq + 4 * self.B + 3 * self.C
		dd = - 8 * self.Dq + 6 * self.B + 5 * self.C
		ee = - 8 * self.Dq - 2 * self.B + 3 * self.C

		# non diagonal elements

		ab = ba = - _3sqrt3 * self.B
		ac = ca = - 5 * _sqrt3 * self.B
		ad = da = 4 * self.B + 2 * self.C
		ae = ea = 2 * self.B

		bc = cb = 3 * self.B
		bd = db = - _3sqrt3 * self.B
		be = eb = - _3sqrt3 * self.B

		cd = dc = -_sqrt3 * self.B
		ce = ec = +_sqrt3 * self.B

		de = ed = 10 * self.B

		states = np.array([
			[aa, ab, ac, ad, ae],
			[ba, bb, bc, bd, be],
			[ca, cb, cc, cd, ce],
			[da, db, dc, dd, de],
			[ea, eb, ec, ed, ee]
		])

		return self.eigensolver(states)

	def T_2_1_states(self):
		# -  diagonal elements

		aa = +12 * self.Dq - 6 * self.B + 3 * self.C
		bb = + 2 * self.Dq + 3 * self.C
		cc = + 2 * self.Dq - 6 * self.B + 3 * self.C
		dd = - 8 * self.Dq - 6 * self.B + 3 * self.C
		ee = - 8 * self.Dq - 2 * self.B + 3 * self.C

		# non diagonal elements

		ab = ba = - 3 * self.B
		ac = ca = + 3 * self.B
		ad = da = 0.
		ae = ea = - _2sqrt3 * self.B

		bc = cb = - 3 * self.B
		bd = db = + 3 * self.B
		be = eb = _3sqrt3 * self.B

		cd = dc = - 3 * self.B
		ce = ec = - _sqrt3 * self.B

		de = ed = _2sqrt3 * self.B

		states = np.array([
			[aa, ab, ac, ad, ae],
			[ba, bb, bc, bd, be],
			[ca, cb, cc, cd, ce],
			[da, db, dc, dd, de],
			[ea, eb, ec, ed, ee]
		])

		return self.eigensolver(states)

	def E_2_states(self):
		# -  diagonal elements

		aa = +12 * self.Dq - 6 * self.B + 3 * self.C
		bb = + 2 * self.Dq + 8 * self.B + 6 * self.C
		cc = + 2 * self.Dq - 1 * self.B + 3 * self.C
		dd = -18 * self.Dq - 8 * self.B + 4 * self.C

		# non diagonal elements

		ab = ba = - 6 * _sqrt2 * self.B
		ac = ca = - _3sqrt2 * self.B
		ad = da = 0.

		bc = cb = 10 * self.B
		bd = db = + _sqrt3 * (2 * self.B + self.C)

		cd = dc = _2sqrt3 * self.B

		states = np.array([
			[aa, ab, ac, ad],
			[ba, bb, bc, bd],
			[ca, cb, cc, cd],
			[da, db, dc, dd]
		])

		return self.eigensolver(states)

	def T_4_1_states(self):
		# -  diagonal elements

		aa = + 2 * self.Dq - 3 * self.B
		bb = - 8 * self.Dq - 12 * self.B

		# non diagonal elements

		ab = ba = 6 * self.B

		states = np.array([
			[aa, ab],
			[ba, bb]
		])

		return self.eigensolver(states)

	def eigensolver(self, M):
		"""

		:param M: 2 dimensional square array == TS matrics of Ligand field Hamiltonian
		:return: 1 dimensiona                                 l array == eigenvalues of the diagonalized Ligand field Hamiltonian
		"""

		return eigh(M)[0]

	def solver(self):
		# Ligand field independent states

		# Ligandfield multi depnedent state become GS

		T_4_1 = self.T_4_1_states()

		# Ligendfield single depentent states

		GS = T_4_1[0]

		T_4_1[0] = np.array([0.], dtype=float)
		A_4_2 = np.array([12 * self.Dq - 15 * self.B]) - GS
		T_4_2 = np.array([2 * self.Dq - 15 * self.B]) - GS

		A_2_1 = np.array([2 * self.Dq - 11 * self.B + 3 * self.C]) - GS
		A_2_2 = np.array([2 * self.Dq + 9 * self.B + 3 * self.C]) - GS

		# Ligandfield dependent
		T_2_2 = self.T_2_2_states() - GS
		T_2_1 = self.T_2_1_states() - GS
		E_2 = self.E_2_states() - GS
		T_4_1[1] -= GS

		if E_2[0] <= 0:
			A_4_2 -= E_2[0]
			T_4_2 -= E_2[0]
			A_2_1 -= E_2[0]
			A_2_2 -= E_2[0]
			T_2_2 -= E_2[0]
			T_2_1 -= E_2[0]
			T_4_1 -= E_2[0]
			E_2 -= E_2[0]

		return {'2_T_2': T_2_2, '2_T_1': T_2_1, '2_E': E_2, '4_T_1': T_4_1,
		        '4_A_2': A_4_2, '4_T_2': T_4_2, '2_A_1': A_2_1, '2_A_2': A_2_2}


if __name__ == '__main__':
	# print( d5( Dq=0, B=1293., C=4823. ).E_4_states( ) )
	import matplotlib.pylab as plt

	for i in np.linspace(0, 1500, 30):
		states = d6(Dq=i).solver()
		states = states['1_A_1']
		# en_step = np.full( len( states ), i )
		# plt.plot( en_step, states, 'o', color='r' )
		plt.plot(i, states[0], 'o', color='r')

	for i in np.linspace(0, 1500, 30):
		states = d6(Dq=i).solver()
		states = states['3_T_2']
		# en_step = np.full( len( states ), i )
		# plt.plot( en_step, states, 'o', color='g' )
		plt.plot(i, states[0], 'o', color='g')

	for i in np.linspace(0, 1500, 30):
		states = d6(Dq=i).solver()
		states = states['3_T_1']
		# en_step = np.full( len( states ), i )
		# plt.plot( en_step, states, 'v', color='b' )
		plt.plot(i, states[0], 'v', color='b')
	plt.show()
