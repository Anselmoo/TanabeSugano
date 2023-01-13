#!/usr/bin/env python
import argparse

import matplotlib.pyplot as plt
import numpy as np
from prettytable import PrettyTable

from tanabesugano import matrices, tools


class CMDmain(object):
    def __init__(
        self,
        Dq: float = 4000.0,
        B: float = 400.0,
        C: float = 3600.0,
        nroots: int = 100,
        d_count: int = 5,
        slater: bool = False,
    ):
        self.Dq = Dq  # Oh-crystalfield-splitting
        self.B = B  # Racah-Parameter B in wavenumbers
        self.C = C  # Racah-Parameter C in wavenumbers

        if slater:
            # Transformin Racah to Slater-Condon
            self.B, self.C = tools.racah(B, C)
        self.nroot = nroots
        self.e_range = np.linspace(0.0, self.Dq, nroots)
        self.delta_B = self.e_range / self.B

        self.d_count = d_count
        if self.d_count in {4, 5, 6}:
            self._size = 42
        if self.d_count in {3, 7}:
            self._size = 19
        if self.d_count in {2, 8}:
            self._size = 10
        self.result = np.zeros((self._size + 1, nroots))

    def plot(self):

        # Figure one for classical Tanabe-Sugano-Diagram with B-dependency
        plt.figure(1)

        # Set Window Title

        for i in range(self._size + 1):
            plt.plot(self.delta_B, self.result[i, :] / self.B, ls="--")
        plt.title("Tanabe-Sugano-Diagram")
        plt.ylabel("$E/B$")
        plt.xlabel("$\Delta/B$")

        # Figure one for Energy-Correlation-Diagram Dq-Energy versus State-Energy
        plt.figure(2)
        for i in range(self._size + 1):
            plt.plot(self.e_range * 10.0, self.result[i, :], ls="--")
        plt.title("DD excitations -Diagram")
        plt.ylabel("$dd-state-energy\,(1/cm)$")
        plt.xlabel("$10Dq\,(1/cm)$")

        plt.show()

    def savetxt(self):

        title_TS = "TS-diagram_d%i_10Dq_%i_B_%i_C_%i.txt" % (
            self.d_count,
            self.Dq * 10.0,
            self.B,
            self.C,
        )
        ts_states = np.concatenate(
            (np.array([self.delta_B]), np.divide(self.result, self.B))
        )
        np.savetxt(title_TS, ts_states.T, delimiter="\t", fmt="%.6f")

        title_DD = "DD-energies_d%i_10Dq_%i_B_%i_C_%i.txt" % (
            self.d_count,
            self.Dq * 10.0,
            self.B,
            self.C,
        )
        dd_states = np.concatenate((np.array([self.e_range * 10.0]), self.result))
        np.savetxt(title_DD, dd_states.T, delimiter="\t", fmt="%.6f")

    def calculation(self):
        """
        Is filling the self.result with the iTS states of over-iterated energy range
        """
        for i, dq in enumerate(self.e_range):

            if self.d_count == 2:  # d3

                states = matrices.d2(Dq=dq, B=self.B, C=self.C).solver()
                self.result[:, i] = np.concatenate(list(states.values()))

            elif self.d_count == 3:  # d3

                states = matrices.d3(Dq=dq, B=self.B, C=self.C).solver()
                self.result[:, i] = np.concatenate(list(states.values()))

            elif self.d_count == 4:  # d4

                states = matrices.d4(Dq=dq, B=self.B, C=self.C).solver()
                self.result[:, i] = np.concatenate(list(states.values()))

            elif self.d_count == 5:  # d5
                states = matrices.d5(Dq=dq, B=self.B, C=self.C).solver()
                self.result[:, i] = np.concatenate(list(states.values()))

            elif self.d_count == 6:  # d6

                states = matrices.d6(Dq=dq, B=self.B, C=self.C).solver()
                self.result[:, i] = np.concatenate(list(states.values()))

            elif self.d_count == 7:  # d7

                states = matrices.d7(Dq=dq, B=self.B, C=self.C).solver()
                self.result[:, i] = np.concatenate(list(states.values()))

            elif self.d_count == 8:  # d8

                states = matrices.d8(Dq=dq, B=self.B, C=self.C).solver()
                self.result[:, i] = np.concatenate(list(states.values()))

            else:

                print("not a correct value!")

    def ci_cut(self, dq_ci=None):
        """
        Extracting the atomic-termsymbols for a specific dq depending on the oxidation state
        """
        if self.d_count == 2:  # d2

            states = matrices.d2(Dq=dq_ci / 10.0, B=self.B, C=self.C).solver()
            self.ts_print(states, dq_ci=dq_ci)

        elif self.d_count == 3:  # d3

            states = matrices.d3(Dq=dq_ci / 10.0, B=self.B, C=self.C).solver()
            self.ts_print(states, dq_ci=dq_ci)

        elif self.d_count == 4:  # d4

            states = matrices.d4(Dq=dq_ci / 10.0, B=self.B, C=self.C).solver()
            self.ts_print(states, dq_ci=dq_ci)

        elif self.d_count == 5:  # d5

            states = matrices.d5(Dq=dq_ci / 10.0, B=self.B, C=self.C).solver()
            self.ts_print(states, dq_ci=dq_ci)

        elif self.d_count == 6:  # d6

            states = matrices.d6(Dq=dq_ci / 10.0, B=self.B, C=self.C).solver()
            self.ts_print(states, dq_ci=dq_ci)

        elif self.d_count == 7:  # d7

            states = matrices.d7(Dq=dq_ci / 10.0, B=self.B, C=self.C).solver()
            self.ts_print(states, dq_ci=dq_ci)

        elif self.d_count == 8:  # d8

            states = matrices.d8(Dq=dq_ci / 10.0, B=self.B, C=self.C).solver()
            self.ts_print(states, dq_ci=dq_ci)

    def ts_print(self, states, dq_ci=None):
        """

        parameter
        ---------

        states: str-list
                List of atomic-termsymbols for a specific oxidation state
        dq_ci: float (optional)
                Specific crystalfield-splitting in Dq

        action
        ------

        Table: str
                Print the state-energies and their atomic-termsymbols on the screen

        txt-file: ascii
                Save the state-energies and their atomic-termsymbols as txt-file

        """
        count = 0
        cut = np.zeros(
            self._size + 1,
            dtype=[("state", np.unicode_, 7), ("cm", int), ("eV", float)],
        )
        for irreducible in states.keys():
            for energy in states[irreducible]:
                cut["state"][count] = irreducible
                cut["cm"][count] = np.round(energy, 0).astype(int)
                cut["eV"][count] = np.round(energy * 0.00012, 4)

                count += 1

        results = np.sort(cut, order="eV")

        x = PrettyTable(results.dtype.names)
        for row in results:
            x.add_row(row)
        # Change some column alignments; default was 'c'
        x.field_names = ["State", "cm-", "eV"]
        x.align["state"] = "l"
        x.align["cm"] = "r"
        x.align["eV"] = "r"
        print(x)
        title = "TS_Cut_d%i_10Dq_%i_B_%i_C_%i.txt" % (
            self.d_count,
            dq_ci,
            self.B,
            self.C,
        )

        np.savetxt(
            title,
            results.T,
            delimiter="\t",
            header="state\tcm\teV",
            fmt="%s\t%i\t%.4f",
        )


def cmd_line() -> None:
    description = (
        "A python-based Eigensolver for Tanabe-Sugano- & Energy-Correlation-Diagrams "
        "based on the original three proposed studies of *Yukito Tanabe and Satoru Sugano* "
        "for d3-d8 transition metal ions:\n"
        "For futher help, please use tanabe '--help'"
    )

    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "-d", type=int, default=6, help="Number of unpaired electrons (default d5)"
    )
    parser.add_argument(
        "-Dq",
        type=float,
        default=25065.0,
        help="10Dq crystal field splitting (default 10Dq = 8065 cm-)",
    )
    parser.add_argument(
        "-cut",
        type=float,
        default=24000,
        help="10Dq crystal field splitting (default 10Dq = 8065 cm-)",
    )
    parser.add_argument(
        "-B",
        type=float,
        nargs=2,
        default=[1080.0, 1.0],
        help="Racah Parameter B and the corresponding "
        "reduction (default B = 860 cm- * 1.)",
    )
    parser.add_argument(
        "-C",
        type=float,
        nargs=2,
        default=[4773.0, 1.0],
        help="Racah Parameter C and the corresponding "
        "reduction (default C = 4.477*860 cm- * "
        "1.)",
    )
    parser.add_argument(
        "-n", type=int, default=500, help="Number of roots (default nroots = 500)"
    )
    parser.add_argument(
        "-ndisp",
        action="store_true",
        default=False,
        help="Plot TS-diagram (default = on)",
    )
    parser.add_argument(
        "-ntxt",
        action="store_true",
        default=False,
        help="Save TS-diagram and dd energies (default = on)",
    )
    parser.add_argument(
        "-slater",
        action="store_true",
        default=False,
        help="Using Slater-Condon F2,F4 parameter "
        "instead Racah-Parameter B,C (default = "
        "off)",
    )
    args = parser.parse_args()

    tmm = CMDmain(
        Dq=args.Dq / 10.0,
        B=args.B[0] * args.B[1],
        C=args.C[0] * args.C[1],
        nroots=args.n,
        d_count=args.d,
        slater=args.slater,
    )
    tmm.calculation()

    if args.ndisp is not True:
        tmm.plot()
    if args.ntxt is not True:
        tmm.savetxt()
    if args.cut is not None:
        tmm.ci_cut(dq_ci=args.cut)
