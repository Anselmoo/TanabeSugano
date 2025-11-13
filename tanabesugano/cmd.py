#!/usr/bin/env python
"""Command-line interface for Tanabe-Sugano diagram generation."""

from __future__ import annotations

import argparse

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from prettytable import PrettyTable


try:
    import plotly.express as px
except ImportError:  # pragma: no cover
    px = None

from tanabesugano import __version__
from tanabesugano import tools

# Import the solver mapping from batch module
from tanabesugano.batch import ELECTRON_CONFIG_SOLVERS
from tanabesugano.constants import ElectronConfiguration


class CMDmain:
    """Command-line interface for Tanabe-Sugano diagram generation and visualization.

    This class provides the main interface for generating and plotting Tanabe-Sugano
    diagrams from the command line, supporting both matplotlib and plotly outputs.
    """

    def __init__(
        self,
        Dq: float = 4000.0,
        B: float = 400.0,
        C: float = 3600.0,
        nroots: int = 100,
        d_count: int = 5,
        slater: bool = False,
    ) -> None:
        """CMD Interface for Tanabe-Sugano-Diagram.

        Parameters
        ----------
        Dq : float, optional
            Oh-crystalfield-splitting, by default 4000.0
        B : float, optional
            Racah-Parameter B in wavenumbers, by default 400.0
        C : float, optional
            Racah-Parameter C in wavenumbers, by default 3600.0
        nroots : int, optional
            Number of roots to calculate the TS-diagram , by default 100
        d_count : int, optional
            Electron count, by default 5
        slater : bool, optional
             Transforming from Racah to Slater-Condon, by default False

        """
        self.Dq = Dq
        self.B = B
        self.C = C

        if slater:
            self.B, self.C = tools.racah(B, C)
        self.nroot = nroots
        energy = np.linspace(0.0, self.Dq, nroots)

        self.d_count = d_count
        if self.d_count in {
            ElectronConfiguration.D4,
            ElectronConfiguration.D5,
            ElectronConfiguration.D6,
        }:
            self._size = 42
        if self.d_count in {ElectronConfiguration.D3, ElectronConfiguration.D7}:
            self._size = 19
        if self.d_count in {ElectronConfiguration.D2, ElectronConfiguration.D8}:
            self._size = 10
        self.result = np.zeros((self._size + 1, nroots))

        self.df = pd.DataFrame(
            {"Energy": energy, "delta_B": energy / self.B, "10Dq": energy * 10.0},
        )
        self.title_TS = (
            f"TS-diagram_d{self.d_count}_10Dq_{int(self.Dq * 10.0)}_"
            f"B_{int(self.B)}_C_{int(self.C)}"
        )
        self.title_DD = (
            f"DD-energies_d{self.d_count}_10Dq_{int(self.Dq * 10.0)}_"
            f"B_{int(self.B)}_C_{int(self.C)}"
        )

    def plot(self) -> None:
        """Generate and display Tanabe-Sugano and DD excitation diagrams.

        Creates two matplotlib figures:
        1. Tanabe-Sugano diagram with E/B vs Delta/B
        2. DD excitations diagram with dd-state-energy vs 10Dq

        """
        # Figure one for classical Tanabe-Sugano-Diagram with B-dependency
        plt.figure(1)

        # Set Window Title

        plt.plot(
            self.df["delta_B"],
            # get the states from self.df
            self.df.drop(["Energy", "delta_B", "10Dq"], axis=1).to_numpy() / self.B,
            ls="--",
        )
        self.label_plot("Tanabe-Sugano-Diagram", "$E/B$", r"$\Delta/B$")
        # Figure one for Energy-Correlation-Diagram Dq-Energy versus State-Energy
        plt.figure(2)

        plt.plot(
            self.df["10Dq"],
            self.df.drop(["Energy", "delta_B", "10Dq"], axis=1).to_numpy(),
            ls="--",
        )
        self.label_plot(
            "DD excitations -Diagram",
            r"$dd-state-energy\,(1/cm)$",
            r"$10Dq\,(1/cm)$",
        )
        plt.show()

    def label_plot(self, arg0: str, arg1: str, arg2: str) -> None:
        """Labels the plot."""
        plt.title(arg0)
        plt.ylabel(arg1)
        plt.xlabel(arg2)

    def savetxt(self) -> None:
        """Save Tanabe-Sugano and DD excitation data to CSV files.

        Creates two CSV files:
        - TS diagram data (E/B vs Delta/B)
        - DD excitations data (dd-state-energy vs 10Dq)

        """
        pd.concat(
            [
                self.df["delta_B"],
                self.df.drop(["Energy", "delta_B", "10Dq"], axis=1) / self.B,
            ],
            axis=1,
        ).to_csv(Path(f"{self.title_TS}.csv"), index=False)

        pd.concat(
            [self.df["10Dq"], self.df.drop(["Energy", "delta_B", "10Dq"], axis=1)],
            axis=1,
        ).to_csv(Path(f"{self.title_DD}.csv"), index=False)

    def calculation(self) -> None:
        """Fill self.result with iTS states of over-iterated energy range."""
        # Get the solver class for this electron configuration
        solver_class = ELECTRON_CONFIG_SOLVERS.get(self.d_count)
        if solver_class is None:
            msg = "The number of unpaired electrons should be between 2 and 8."
            raise ValueError(msg)

        result = []
        for dq in self.df["Energy"]:
            states = solver_class(Dq=dq, B=self.B, C=self.C).solver()
            result.append(self.subsplit_states(states))

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

    def ci_cut(self, dq_ci: float | None = None) -> None:
        """Extract atomic-termsymbols for specific dq by oxidation state."""
        # Get the solver class for this electron configuration
        solver_class = ELECTRON_CONFIG_SOLVERS.get(self.d_count)
        if solver_class is None:
            msg = "The number of unpaired electrons should be between 2 and 8."
            raise ValueError(msg)

        states = solver_class(Dq=dq_ci / 10.0, B=self.B, C=self.C).solver()
        self.ts_print(states, dq_ci=dq_ci)

    def ts_print(self, states: dict, dq_ci: float | None = None) -> None:
        """Print the atomic-termsymbols.

        Print the atomic-termsymbols for a specific dq depending on the oxidation state
        on the screen and save them as txt-file.

        Parameters
        ----------
        states : dict
            List of atomic-termsymbols for a specific oxidation state
        dq_ci : float, optional
            Specific crystalfield-splitting in Dq, by default None

        """
        count = 0
        dtype = [("state", np.str_, 7), ("cm", int), ("eV", float)]
        cut = np.zeros(self._size + 1, dtype=dtype)
        for irreducible, energies in states.items():
            for energy in energies:
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
        title = (
            f"TS_Cut_d{self.d_count}_10Dq_{int(dq_ci)}_B_{int(self.B)}"
            f"_C_{int(self.C)}.csv"
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

    def interactive_plot(self) -> None:
        """Interactive plot for the tanabe-sugano-diagram."""
        if px is None:
            msg = (
                "Plotly is not installed. "
                "Install with: pip install tanabesugano[plotly]"
            )
            raise ImportError(msg)

        _col = self.df.drop(["Energy", "delta_B", "10Dq"], axis=1).columns
        _font = {"family": "Avant Garde, sans-serif", "size": 12, "color": "grey"}
        _template = "plotly_white"
        _size = {
            "autosize": False,
            "width": 800,
            "height": 800,
        }
        color_discrete_sequence = [
            px.colors.qualitative.Light24[int(i[0]) - 1] for i in _col
        ]

        _df = self.df.copy()

        fig_1 = px.line(
            _df,
            x="10Dq",
            y=_col,
            title="Energy-Correlation-Diagram",
            labels={
                "variable": "State",
                "value": "Energy (cm-1)",
                "10Dq": "10Dq (cm-1)",
            },
            color_discrete_sequence=color_discrete_sequence,
        )
        fig_1.update_layout(
            xaxis_title="10Dq (cm-1)",
            yaxis_title="dd-states (cm-1)",
            legend_title="State",
            template=_template,
            font=_font,
            **_size,
        )
        # Save as html-file
        fig_1.write_html(Path(f"{self.title_DD}.html"))

        # Apply / self.B to every column except for _col
        _df[_col] = _df[_col].div(self.B, axis=0)

        # Plot the tanabe-sugano-diagram
        fig_2 = px.line(
            _df,
            x="delta_B",
            y=_col,
            title="Tanabe-Sugano-Diagram",
            labels={
                "variable": "State",
                "value": " E / B",
                "delta_B": "Δ / B",
            },
            color_discrete_sequence=color_discrete_sequence,
        )
        fig_2.update_layout(
            xaxis_title="Δ / B",
            yaxis_title="E / B",
            legend_title="State",
            template=_template,
            font=_font,
            **_size,
        )
        # Save as html-file
        fig_2.write_html(Path(f"{self.title_TS}.html"))


def cmd_line() -> None:
    """Command line interface for tanabe-sugano."""
    description = (
        "A python-based Eigensolver for Tanabe-Sugano- & "
        "Energy-Correlation-Diagrams based on studies by "
        "*Yukito Tanabe and Satoru Sugano* for d3-d8 transition metal ions:\n"
        "For further help, please use tanabe '--help'"
    )

    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "-d",
        type=int,
        default=6,
        help="Number of unpaired electrons (default d5)",
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
        "-n",
        type=int,
        default=500,
        help="Number of roots (default nroots = 500)",
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
        "instead Racah-Parameter B,C (default = off)",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="Print version number and exit",
    )
    parser.add_argument(
        "-html",
        action="store_true",
        default=False,
        help="Save TS-diagram and dd energies (default = off)",
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
    if args.html:
        tmm.interactive_plot()
