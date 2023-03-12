#!/usr/bin/env python
import argparse
from logging import warning


import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
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
    ) -> None:
        self.Dq = Dq  # Oh-crystalfield-splitting
        self.B = B  # Racah-Parameter B in wavenumbers
        self.C = C  # Racah-Parameter C in wavenumbers

        if slater:
            # Transforming Racah to Slater-Condon
            self.B, self.C = tools.racah(B, C)
        self.nroot = nroots
        energy = np.linspace(0.0, self.Dq, nroots)

        self.d_count = d_count
        if self.d_count in {4, 5, 6}:
            self._size = 42
        if self.d_count in {3, 7}:
            self._size = 19
        if self.d_count in {2, 8}:
            self._size = 10
        self.result = np.zeros((self._size + 1, nroots))

        self.df = pd.DataFrame({"Energy": energy, "delta_B": energy / self.B})

    def plot(self) -> None:

        # Figure one for classical Tanabe-Sugano-Diagram with B-dependency
        plt.figure(1)

        # Set Window Title

        plt.plot(
            self.df["delta_B"],
            # get the states from self.df
            self.df.drop(["Energy", "delta_B"], axis=1).to_numpy() / self.B,
            ls="--",
        )
        self.label_plot("Tanabe-Sugano-Diagram", "$E/B$", "$\Delta/B$")
        # Figure one for Energy-Correlation-Diagram Dq-Energy versus State-Energy
        plt.figure(2)

        plt.plot(
            self.df["Energy"] * 10.0,
            self.df.drop(["Energy", "delta_B"], axis=1).to_numpy(),
            ls="--",
        )
        self.label_plot(
            "DD excitations -Diagram", "$dd-state-energy\,(1/cm)$", "$10Dq\,(1/cm)$"
        )
        plt.show()

    def label_plot(self, arg0: str, arg1: str, arg2: str) -> None:
        """Labels the plot."""
        plt.title(arg0)
        plt.ylabel(arg1)
        plt.xlabel(arg2)

    def savetxt(self) -> None:

        title_TS = (
            f"TS-diagram_d{self.d_count}_10Dq_{self.Dq * 10.0}_"
            f"B_{self.B}_C_{self.C}.csv"
        )

        pd.concat(
            [self.df["delta_B"], self.df.drop(["Energy", "delta_B"], axis=1) / self.B],
            axis=1,
        ).to_csv(title_TS, index=False)

        title_DD = (
            f"DD-energies_d{self.d_count}_10Dq_{self.Dq * 10.0}_"
            f"B_{self.B}_C_{self.C}.csv"
        )

        pd.concat(
            [self.df["Energy"] * 10.0, self.df.drop(["Energy", "delta_B"], axis=1)],
            axis=1,
        ).to_csv(title_DD, index=False)

    def calculation(self) -> None:
        """
        Is filling the self.result with the iTS states of over-iterated energy range
        """
        result = []
        for dq in self.df["Energy"]:
            if self.d_count == 2:  # d2
                result.append(
                    self.subsplit_states(
                        matrices.d2(Dq=dq, B=self.B, C=self.C).solver()
                    )
                )
            elif self.d_count == 3:  # d3
                result.append(
                    self.subsplit_states(
                        matrices.d3(Dq=dq, B=self.B, C=self.C).solver()
                    )
                )
            elif self.d_count == 4:  # d4
                result.append(
                    self.subsplit_states(
                        matrices.d4(Dq=dq, B=self.B, C=self.C).solver()
                    )
                )
            elif self.d_count == 5:  # d5
                result.append(
                    self.subsplit_states(
                        matrices.d5(Dq=dq, B=self.B, C=self.C).solver()
                    )
                )
            elif self.d_count == 6:  # d6
                result.append(
                    self.subsplit_states(
                        matrices.d6(Dq=dq, B=self.B, C=self.C).solver()
                    )
                )
            elif self.d_count == 7:  # d7
                result.append(
                    self.subsplit_states(
                        matrices.d7(Dq=dq, B=self.B, C=self.C).solver()
                    )
                )
            elif self.d_count == 8:  # d8
                result.append(
                    self.subsplit_states(
                        matrices.d8(Dq=dq, B=self.B, C=self.C).solver()
                    )
                )
            else:
                raise ValueError("`d_count` must be in {2,3,4,5,6,7,8}")

        # Transform list of dictionaries to dictionary of arrays
        result = {
            key: np.array([d[key] for d in result]).flatten() for key in result[0]
        }
        self.df = pd.concat([self.df, pd.DataFrame(result)], axis=1)

    @staticmethod
    def subsplit_states(states: dict) -> dict:
        """Subsplitting the states for a better overview."""
        rearranged_states = {}
        for key, value in states.items():
            if len(value) > 1:
                for i, _value in enumerate(value):
                    rearranged_states[f"{key}_{i}"] = np.array([_value])
            else:
                rearranged_states[key] = value
        return rearranged_states

    def ci_cut(self, dq_ci=None) -> None:
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

    def ts_print(self, states, dq_ci=None) -> None:
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
        title = "TS_Cut_d%i_10Dq_%i_B_%i_C_%i.csv" % (
            self.d_count,
            dq_ci,
            self.B,
            self.C,
        )

        np.savetxt(
            title,
            results.T,
            delimiter=",",
            header="state,cm,eV",
            fmt=r"%s,%i,%.4f",
            # Remove # for comments
            comments="",
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
