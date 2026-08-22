#!/usr/bin/env python
"""Command-line interface for Tanabe-Sugano diagram generation."""

from __future__ import annotations

import argparse

from pathlib import Path
from typing import TYPE_CHECKING

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from prettytable import PrettyTable


try:
    import plotly.express as px
except ImportError:  # pragma: no cover
    px = None

if TYPE_CHECKING:
    from plotly.graph_objects import Figure as PlotlyFigure

from tanabesugano import __version__
from tanabesugano import tools

# Import the solver mapping from batch module
from tanabesugano.batch import ELECTRON_CONFIG_SOLVERS
from tanabesugano.constants import CM1_TO_EV
from tanabesugano.constants import matrix_size
from tanabesugano.figure_style import SeriesStyle
from tanabesugano.figure_style import column_to_uid
from tanabesugano.figure_style import series_styles
from tanabesugano.plot_style import LABEL_FONT_PT
from tanabesugano.plot_style import LABEL_PITCH_PT
from tanabesugano.plot_style import darken
from tanabesugano.plot_style import encoding_key
from tanabesugano.plot_style import spread_labels
from tanabesugano.plot_style import style_axes


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
        self._size = matrix_size(d_count)
        self.result = np.zeros((self._size + 1, nroots))

        # `energy` holds Dq, so Delta_o = 10 * Dq. The delta_B column is plotted
        # and exported under the label $\Delta/B$, so it must carry 10Dq/B --
        # it previously carried Dq/B, making the axis wrong by a factor of 10.
        self.df = pd.DataFrame(
            {
                "Energy": energy,
                "delta_B": energy * 10.0 / self.B,
                "10Dq": energy * 10.0,
            },
        )
        self.title_TS = (
            f"TS-diagram_d{self.d_count}_10Dq_{int(self.Dq * 10.0)}_B_{int(self.B)}_C_{int(self.C)}"
        )
        self.title_DD = (
            f"DD-energies_d{self.d_count}_10Dq_{int(self.Dq * 10.0)}_"
            f"B_{int(self.B)}_C_{int(self.C)}"
        )

    @property
    def data_columns(self) -> list[str]:
        """Columns of :attr:`df` that hold level energies, not axis values."""
        return [c for c in self.df.columns if c not in ("Energy", "delta_B", "10Dq")]

    def plot(self) -> None:
        """Generate and display Tanabe-Sugano and DD excitation diagrams.

        Creates two matplotlib figures:
        1. Tanabe-Sugano diagram with E/B vs Delta/B
        2. DD excitations diagram with dd-state-energy vs 10Dq

        Every level is named on the curve itself, in the free-ion parentage
        spelling a reader can check against the literature. The legend
        explains the three visual channels rather than listing states -- see
        :mod:`tanabesugano.figure_style`.
        """
        data_cols = self.data_columns
        if not data_cols:
            return

        styles = self.series_style()
        # Height follows the label count: a fixed box cannot carry d6's 43
        # names at a legible size, and unnamed curves were the whole complaint.
        fig_height = min(max(4.6, 0.21 * len(data_cols)), 11.0)

        def _draw(
            ax: plt.Axes,
            x_col: str,
            y_scale: float,
            title: str,
            x_label: str,
            y_label: str,
        ) -> None:
            endpoints: list[tuple[float, str, str]] = []
            for col in data_cols:
                style = styles[col]
                values = self.df[col] / y_scale
                ax.plot(self.df[x_col], values, **style.matplotlib_kwargs())
                endpoints.append((float(values.iloc[-1]), style.label_latex, style.base_color))

            style_axes(ax, title=title, x_label=x_label, y_label=y_label)
            encoding_key(ax, {style.multiplicity for style in styles.values()})
            self._label_curves(
                ax,
                endpoints,
                x_end=float(self.df[x_col].iloc[-1]),
                fig_height=fig_height,
            )

        fig1, ax1 = plt.subplots(num=1, figsize=(9.0, fig_height))
        fig1.subplots_adjust(left=0.09, right=0.80, top=0.92, bottom=0.16)
        _draw(ax1, "delta_B", self.B, "Tanabe-Sugano diagram", r"$\Delta/B$", r"$E/B$")

        fig2, ax2 = plt.subplots(num=2, figsize=(9.0, fig_height))
        fig2.subplots_adjust(left=0.11, right=0.80, top=0.92, bottom=0.16)
        _draw(
            ax2,
            "10Dq",
            1.0,
            "DD-excitation diagram",
            r"$10Dq$ (cm$^{-1}$)",
            r"$E$ (cm$^{-1}$)",
        )

        plt.show()

    @staticmethod
    def _label_curves(
        ax: plt.Axes,
        endpoints: list[tuple[float, str, str]],
        *,
        x_end: float,
        fig_height: float,
    ) -> None:
        """Name every curve in the right margin, spread so none overlaps."""
        if not endpoints:
            return
        from matplotlib.transforms import blended_transform_factory

        low, high = ax.get_ylim()
        high += (high - low) * 0.02
        ax.set_ylim(low, high)

        axes_height_pt = fig_height * 72.0 * ax.get_position().height
        pitch = (high - low) * LABEL_PITCH_PT / max(axes_height_pt, 1.0)
        anchors = spread_labels(
            [y for y, _label, _color in endpoints],
            span=(low, high),
            pitch=pitch,
        )
        margin = blended_transform_factory(ax.transAxes, ax.transData)
        for (y_curve, label, color), y_text in zip(endpoints, anchors, strict=True):
            ax.annotate(
                label,
                xy=(x_end, y_curve),
                xycoords="data",
                xytext=(1.015, y_text),
                textcoords=margin,
                fontsize=LABEL_FONT_PT,
                color=darken(color),
                va="center",
                ha="left",
                annotation_clip=False,
                arrowprops=(
                    {
                        "arrowstyle": "-",
                        "color": color,
                        "linewidth": 0.5,
                        "alpha": 0.5,
                        "shrinkA": 0,
                        "shrinkB": 1,
                    }
                    if abs(y_text - y_curve) > pitch * 0.6
                    else None
                ),
            )

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
            msg = "The number of d electrons should be between 2 and 8."
            raise ValueError(msg)

        result = []
        for dq in self.df["Energy"]:
            states = solver_class(Dq=dq, B=self.B, C=self.C).solver().as_dict()
            result.append(self.subsplit_states(states))

        # Transform list of dictionaries to dictionary of arrays
        result = {key: np.array([d[key] for d in result]).flatten() for key in result[0]}
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

    def ci_cut(self, dq_ci: float) -> None:
        """Extract atomic-termsymbols for specific dq by oxidation state."""
        # Get the solver class for this electron configuration
        solver_class = ELECTRON_CONFIG_SOLVERS.get(self.d_count)
        if solver_class is None:
            msg = "The number of d electrons should be between 2 and 8."
            raise ValueError(msg)

        states = solver_class(Dq=dq_ci / 10.0, B=self.B, C=self.C).solver().as_dict()
        self.ts_print(states, dq_ci=dq_ci)

    def ts_print(self, states: dict, dq_ci: float) -> None:
        """Print the atomic-termsymbols.

        Print the atomic-termsymbols for a specific dq depending on the oxidation state
        on the screen and save them as txt-file.

        Parameters
        ----------
        states : dict
            List of atomic-termsymbols for a specific oxidation state
        dq_ci : float
            Specific crystalfield-splitting as 10Dq in cm^-1. Required: the body
            divides by it, so the previous `= None` default raised TypeError for
            anyone who took the signature at its word.

        """
        count = 0
        dtype = [("state", np.str_, 7), ("cm", int), ("eV", float)]
        cut = np.zeros(self._size + 1, dtype=dtype)
        for irreducible, energies in states.items():
            for energy in energies:
                cut["state"][count] = irreducible
                cut["cm"][count] = np.round(energy, 0).astype(int)
                cut["eV"][count] = np.round(energy * CM1_TO_EV, 4)

                count += 1

        results = np.sort(cut, order="eV")

        x = PrettyTable(results.dtype.names)
        for row in results:
            x.add_row(row)
        # Change some column alignments; default was 'c'
        x.field_names = ["State", "cm-", "eV"]
        # Alignment keys must match the CURRENT field names, which were just
        # renamed above -- the old lowercase keys silently aligned nothing.
        x.align["State"] = "l"
        x.align["cm-"] = "r"
        x.align["eV"] = "r"
        # The docstring promises the table appears "on the screen"; it was built
        # and then dropped, so only the CSV was ever produced.
        print(x)
        title = f"TS_Cut_d{self.d_count}_10Dq_{int(dq_ci)}_B_{int(self.B)}_C_{int(self.C)}.csv"

        np.savetxt(
            title,
            results.T,
            delimiter=",",
            header="state,cm,eV",
            fmt=r"%s,%i,%.4f",
            # Remove # for comments
            comments="",
        )

    def series_style(self) -> dict[str, SeriesStyle]:
        """How each data column of :attr:`df` is drawn, keyed by column name.

        The single decision point behind every figure this class produces and
        behind the ``series`` block of ``ts-diagrams/manifest.json``. Anchored
        at ``self.Dq`` -- the sweep's upper bound -- so spin-allowedness is
        judged where the diagram ends, matching the ground-term annotation
        convention in ``mcp.plotting``.
        """
        styles = series_styles(self.d_count, self.Dq, self.B, self.C)
        by_column: dict[str, SeriesStyle] = {}
        for column in self.data_columns:
            uid = column_to_uid(column)
            if uid not in styles:
                # A column the level machinery does not recognise means the two
                # paths have drifted apart, which is the whole failure this
                # module exists to prevent. Loud beats mislabelled.
                msg = f"column {column!r} maps to unknown level {uid!r} for d{self.d_count}"
                raise KeyError(msg)
            by_column[column] = styles[uid]
        return by_column

    def interactive_plot(self, *, include_plotlyjs: str | bool = "cdn") -> None:
        """Write the two interactive Plotly diagrams as standalone HTML.

        Args:
            include_plotlyjs: Passed through to ``write_html``. ``"cdn"``
                (default) references plotly.js from the CDN and needs a network
                connection to render; ``True`` inlines the whole ~4.9 MB bundle
                into every file, which is what produced 160 MB of committed
                artifacts; ``"directory"`` writes one shared ``plotly.min.js``
                next to the diagrams, keeping them offline-capable.

        Labels use :attr:`Level.parent_plotly`, so a legend reads
        ``³T₁g(F)`` typeset rather than the raw solver key ``3_T_1_0``. Colour,
        lightness and dash come from :mod:`tanabesugano.figure_style`, the same
        source matplotlib and the docs site read -- see its module docstring for
        what each channel encodes.

        """
        if px is None:
            msg = "Plotly is not installed. Install with: pip install tanabesugano[plotly]"
            raise ImportError(msg)

        styles = self.series_style()
        _font = {"family": "Avant Garde, sans-serif", "size": 12, "color": "grey"}
        _template = "plotly_white"
        _size = {"autosize": False, "width": 900, "height": 800}

        # Renaming the columns rather than patching trace names afterwards:
        # plotly express bakes the column name into each trace's hovertemplate,
        # so setting `trace.name` alone leaves the hover box still showing
        # `3_T_1_0` while the legend shows the typeset symbol.
        renames = {column: style.label_plotly for column, style in styles.items()}
        by_label = {style.label_plotly: style for style in styles.values()}
        labels = list(renames.values())

        def _decorate(fig: PlotlyFigure) -> None:
            """Attach colour, dash and the machine key to every trace."""
            for trace in fig.data:
                style = by_label[trace.name]
                trace.line.color = style.color
                trace.line.dash = style.dash
                trace.line.width = 3.0 if style.is_ground else 1.6
                # The uid is the only machine-readable key left in the file once
                # labels are typeset. `scripts/regenerate_ts_diagrams.py` reads
                # it to tell a stale diagram from a current one; without it the
                # drift gate has nothing to compare and passes vacuously.
                trace.meta = {"uid": style.uid}
                trace.legendgroup = str(style.multiplicity)
                trace.hovertemplate = (
                    f"<b>{style.label_plotly}</b><br>"
                    "%{xaxis.title.text}: %{x:.4g}<br>"
                    "%{yaxis.title.text}: %{y:.4g}<extra></extra>"
                )

        dd_df = self.df.rename(columns=renames)
        fig_1 = px.line(
            dd_df,
            x="10Dq",
            y=labels,
            title=f"Energy-Correlation Diagram \u2014 d<sup>{self.d_count}</sup>",
            labels={"variable": "State", "value": "E (cm⁻¹)", "10Dq": "10Dq (cm⁻¹)"},
        )
        _decorate(fig_1)
        fig_1.update_layout(
            xaxis_title="10Dq (cm⁻¹)",
            yaxis_title="E (cm⁻¹)",
            legend_title="State",
            template=_template,
            font=_font,
            **_size,
        )
        fig_1.write_html(Path(f"{self.title_DD}.html"), include_plotlyjs=include_plotlyjs)

        ts_df = dd_df.copy()
        ts_df[labels] = ts_df[labels].div(self.B, axis=0)
        fig_2 = px.line(
            ts_df,
            x="delta_B",
            y=labels,
            title=f"Tanabe-Sugano Diagram \u2014 d<sup>{self.d_count}</sup>",
            labels={"variable": "State", "value": "E / B", "delta_B": "Δ / B"},
        )
        _decorate(fig_2)
        fig_2.update_layout(
            xaxis_title="Δ / B",
            yaxis_title="E / B",
            legend_title="State",
            template=_template,
            font=_font,
            **_size,
        )
        fig_2.write_html(Path(f"{self.title_TS}.html"), include_plotlyjs=include_plotlyjs)


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
        help="Number of d electrons, 2-8 (default d5)",
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
        help="Racah Parameter B and the corresponding reduction (default B = 860 cm- * 1.)",
    )
    parser.add_argument(
        "-C",
        type=float,
        nargs=2,
        default=[4773.0, 1.0],
        help="Racah Parameter C and the corresponding reduction (default C = 4.477*860 cm- * 1.)",
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
        help="Using Slater-Condon F2,F4 parameter instead Racah-Parameter B,C (default = off)",
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
        help="Save the interactive Plotly diagrams as HTML (default = off)",
    )
    parser.add_argument(
        "-html-offline",
        dest="html_offline",
        action="store_true",
        default=False,
        help=(
            "With -html, write a shared plotly.min.js beside the diagrams so "
            "they render without a network connection (default = CDN)"
        ),
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
        tmm.interactive_plot(include_plotlyjs="directory" if args.html_offline else "cdn")
