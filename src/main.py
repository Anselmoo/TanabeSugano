#!/usr/bin/env python
import argparse

import matplotlib.pylab as plt
try:
	from . import matrices as ts
except:
	import matrices as ts
import numpy as np
from prettytable import PrettyTable


class main(object):
	def __init__(self, Dq=4000., B=400., C=3600., nroots=100, mode=5, slater=False):
		self.Dq = Dq
		self.B = B
		self.C = C

		if slater == True: self.B, self.C = self.racah(B, C)
		self.nroot = nroots
		self.e_range = np.linspace(0., self.Dq, nroots)
		self.delta_B = self.e_range / self.B

		self.spin_state = int(mode)
		if self.spin_state == 4 or self.spin_state == 5 or self.spin_state == 6: self._size = 42
		if self.spin_state == 3 or self.spin_state == 7: self._size = 19
		self.result = np.zeros((self._size + 1, nroots))

	# self.result[0,:] = self.delta_B

	def plot(self):

		fig_1 = plt.figure(1)

		fig_1.canvas.set_window_title('Tanabe-Sugano-Diagram')
		for i in range(self._size + 1):
			plt.plot(self.delta_B, self.result[i, :] / self.B, ls='--')
		# plt.title( 'Tanabe-Sugano-Diagram' )
		plt.ylabel('$E/B$')
		plt.xlabel('$\Delta/B$')

		fig_2 = plt.figure(2)
		fig_2.canvas.set_window_title('DD excitations -Diagram')
		for i in range(self._size + 1):
			plt.plot(self.e_range * 10., self.result[i, :], ls='--')
		# plt.title( 'DD excitations -Diagram' )
		plt.ylabel('$dd energy transfer (1/cm)$')
		plt.xlabel('$10Dq (1/cm)$')

		plt.show()

	def savetxt(self):

		title_TS = 'TS-diagram_d%i_10Dq_%i_B_%i_C_%i.txt' % (self.spin_state, self.Dq * 10., self.B, self.C)
		ts_states = np.concatenate((np.array([self.delta_B]), np.divide(self.result, self.B)))
		np.savetxt(title_TS, ts_states.T, delimiter='\t', fmt='%.6f')

		title_DD = 'DD-energies_d%i_10Dq_%i_B_%i_C_%i.txt' % (self.spin_state, self.Dq * 10., self.B, self.C)
		dd_states = np.concatenate((np.array([self.e_range * 10.]), self.result))
		np.savetxt(title_DD, dd_states.T, delimiter='\t', fmt='%.6f')

	def calculation(self):
		"""

		Is filling the self.result with the TS states iterated of energy range
		"""
		for i, dq in enumerate(self.e_range):

			if self.spin_state == 3:

				states = ts.d3(Dq=dq, B=self.B, C=self.C).solver()
				self.result[:, i] = np.concatenate(list(states.values()))


			elif self.spin_state == 4:

				states = ts.d4(Dq=dq, B=self.B, C=self.C).solver()
				self.result[:, i] = np.concatenate(list(states.values()))

			elif self.spin_state == 5:
				states = ts.d5(Dq=dq, B=self.B, C=self.C).solver()
				self.result[:, i] = np.concatenate(list(states.values()))


			elif self.spin_state == 6:

				states = ts.d6(Dq=dq, B=self.B, C=self.C).solver()
				self.result[:, i] = np.concatenate(list(states.values()))

			elif self.spin_state == 7:

				states = ts.d7(Dq=dq, B=self.B, C=self.C).solver()
				self.result[:, i] = np.concatenate(list(states.values()))

			else:

				print('not a correct value!')

	def ci_cut(self, dq_ci=None):

		if self.spin_state == 3:

			states = ts.d3(Dq=dq_ci / 10., B=self.B, C=self.C).solver()
			self.ts_print(states, dq_ci=dq_ci)

		elif self.spin_state == 4:

			states = ts.d4(Dq=dq_ci / 10., B=self.B, C=self.C).solver()
			self.ts_print(states, dq_ci=dq_ci)

		elif self.spin_state == 5:

			states = ts.d5(Dq=dq_ci / 10., B=self.B, C=self.C).solver()
			self.ts_print(states, dq_ci=dq_ci)

		elif self.spin_state == 6:

			states = ts.d6(Dq=dq_ci / 10., B=self.B, C=self.C).solver()
			self.ts_print(states, dq_ci=dq_ci)

		elif self.spin_state == 7:

			states = ts.d7(Dq=dq_ci / 10., B=self.B, C=self.C).solver()
			self.ts_print(states, dq_ci=dq_ci)

	def ts_print(self, states, dq_ci=None):
		count = 0
		cut = np.zeros(self._size + 1, dtype=[('state', np.unicode_, 7), ('cm', int), ('eV', float)])
		for irreducible in states.keys():
			for energy in states[irreducible]:
				cut['state'][count] = irreducible
				cut['cm'][count] = np.int(np.round(energy, 0))
				cut['eV'][count] = np.round(energy * 0.00012, 4)

				count += 1

		results = np.sort(cut, order='eV')

		x = PrettyTable(results.dtype.names)
		for row in results:
			x.add_row(row)
		# Change some column alignments; default was 'c'
		x.field_names = ["State", "cm-", "eV"]
		x.align['state'] = 'l'
		x.align['cm'] = 'r'
		x.align['eV'] = 'r'
		print(x)
		title = 'TS_Cut_d%i_10Dq_%i_B_%i_C_%i.txt' % (self.spin_state, dq_ci, self.B, self.C)

		np.savetxt(title, results.T, delimiter='\t', header='state\tcm\teV', fmt='%s\t%i\t%.4f')

	def racah(self, F2, F4):
		eVcm = 8065.54
		B = eVcm * (F2 / 49. - 5 / 441. * F4)
		C = eVcm * (35 / 441. * F4)
		return B, C


# 'T_3_1': T_3_1, 'T_1_2': T_1_2, 'A_1_1': A_1_1, 'E_1_1': E_1_1, 'T_3_2': T_3_2, 'T_1_1': T_1_1
# 'E_3_1': E_3_1, 'A_3_2': A_3_2, 'A_1_2': A_1_2, 'E_5_1': E_5_1, 'T_5_2': T_5_2, 'A_3_1': A_3_1

if __name__ == '__main__':

	parser = argparse.ArgumentParser(description='Tanabe-Sugano matrices solver')
	parser.add_argument("-d", type=int, default=6,
	                    help="Number of unpaired electrons (default d5)")
	parser.add_argument("-Dq", type=float, default=25065.,
	                    help="10Dq crystal field splitting (default 10Dq = 8065 cm-)")
	parser.add_argument("-cut", type=float, default=24000,
	                    help="10Dq crystal field splitting (default 10Dq = 8065 cm-)")
	parser.add_argument("-B", type=float, nargs=2, default=[1080., 1.],
	                    help="Racah Parameter B and the corresponding reduction (default B = 860 cm- * 1.)")
	parser.add_argument('-C', type=float, nargs=2, default=[4773., 1.],
	                    help="Racah Parameter C and the corresponding reduction (default C= 4.477*860 cm- * 1.)")
	parser.add_argument("-n", type=int, default=500,
	                    help="Number of roots (default nroots=500)")
	parser.add_argument("-ndisp", action="store_true", default=False,
	                    help="Plot TS-diagram (default = on)")
	parser.add_argument("-ntxt", action="store_true", default=False,
	                    help="Save TS-diagram and dd energies (default = on)")
	parser.add_argument("-slater", action="store_true", default=False,
	                    help="Using Slater-Condon F2,F4 parameter instead Racah-Parameter B,C (default = off)")
	args = parser.parse_args()

	tmm = main(Dq=args.Dq / 10., B=args.B[0] * args.B[1], C=args.C[0] * args.C[1], nroots=args.n, mode=args.d,
	           slater=args.slater)
	tmm.calculation()

	if args.ndisp != True: tmm.plot()
	if args.ntxt != True: tmm.savetxt()
	if args.cut != None: tmm.ci_cut(dq_ci=args.cut)
