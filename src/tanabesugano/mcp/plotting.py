"""Matplotlib renderer for MCP plot tools.

Returns raw PNG bytes so the MCP layer can wrap them as ImageContent without
needing matplotlib at import time on the agent side. The palette and axis
styling are shared with the CLI (see tanabesugano.plot_style) so both
surfaces produce visually-consistent, publication-style figures.
"""

from __future__ import annotations

import io

import matplotlib as mpl


# Force headless backend BEFORE importing pyplot.
mpl.use("Agg")
import matplotlib.pyplot as plt

from tanabesugano.mcp._compute import sweep_dq
from tanabesugano.plot_style import annotate_ground_term
from tanabesugano.plot_style import apply_scientific_rcparams
from tanabesugano.plot_style import line_style_for
from tanabesugano.plot_style import style_axes
from tanabesugano.plot_style import term_to_mathtext


def render_diagram_png(
    d_count: int,
    dq_min: float = 0.0,
    dq_max: float = 1500.0,
    steps: int = 60,
    B: float = 860.0,
    C: float = 3850.0,
    *,
    normalize: bool = True,
    dpi: int = 144,
) -> bytes:
    """Render a Tanabe-Sugano (or DD-energy) diagram and return PNG bytes.

    Visual conventions (see tanabesugano.plot_style for the helpers):

    * Colour = spin multiplicity (Okabe-Ito palette, colour-blind safe).
    * Linestyle = level index within a term (solid -> dashed -> dotted -> ...).
    * Ground term: thicker, fully-opaque line + inline mathtext annotation
      at the right edge.
    * Term labels use mathtext so legends read as $^{4}T_{1g}$ rather than
      `4_T_1`.
    * When `normalize=True`, the top x-axis carries 10Dq in cm^-1 alongside
      the bottom 10Dq/B so users can read raw crystal-field strengths.

    Args:
        d_count: 2..8.
        dq_min: Lower Dq bound of the sweep (cm^-1).
        dq_max: Upper Dq bound of the sweep (cm^-1).
        steps: Number of sweep points.
        B: Racah B parameter (cm^-1).
        C: Racah C parameter (cm^-1).
        normalize: Classical Tanabe-Sugano view (E/B vs 10Dq/B) when True;
            DD-energy diagram (cm^-1 on both axes) when False.
        dpi: Output resolution.

    """
    apply_scientific_rcparams()

    dq_values, points = sweep_dq(d_count, dq_min, dq_max, steps, B, C)
    term_keys = list(points[0].keys())

    # Ground term: lowest eigenvalue at the first Dq point.
    ground_term = min(
        term_keys,
        key=lambda t: min(points[0][t]) if points[0][t] else float("inf"),
    )

    fig, ax = plt.subplots(figsize=(7.2, 4.8), dpi=dpi)
    x_axis = (dq_values * 10.0 / B) if normalize else (dq_values * 10.0)
    x_label = r"$10\,Dq / B$" if normalize else r"$10\,Dq$ (cm$^{-1}$)"
    y_label = r"$E / B$" if normalize else r"$E$ (cm$^{-1}$)"

    # Track the y-position of the ground term's level-0 at xmax for annotation.
    # Sentinel None means "not yet found"; avoids placing annotation at y=0
    # when the ground term produces an empty eigenseries.
    ground_end_y: float | None = None

    for term in term_keys:
        series = [pt[term] for pt in points]
        max_n = max(len(s) for s in series)
        label = term_to_mathtext(term)
        for n in range(max_n):
            y = [s[n] if n < len(s) else float("nan") for s in series]
            y_plot = [v / B if normalize else v for v in y]
            style = line_style_for(term, level=n, is_ground=(term == ground_term))
            ax.plot(
                x_axis,
                y_plot,
                label=label if n == 0 else None,
                **style,
            )
            if term == ground_term and n == 0 and y_plot:
                import math

                last = y_plot[-1]
                if not math.isnan(last):  # skip NaN
                    ground_end_y = float(last)

    style_axes(
        ax,
        title=f"Tanabe-Sugano d{d_count} (B={B:g} cm$^{{-1}}$, C={C:g} cm$^{{-1}}$)",
        x_label=x_label,
        y_label=y_label,
    )

    # Inline annotation of the ground term at the right edge (only when found).
    if x_axis.size and ground_end_y is not None:
        annotate_ground_term(ax, term=ground_term, x=float(x_axis[-1]), y=ground_end_y)

    # Secondary x-axis: when normalized show raw 10Dq in cm^-1 on top.
    if normalize:
        secax = ax.secondary_xaxis(
            "top",
            functions=(lambda v: v * B, lambda v: v / B),
        )
        secax.set_xlabel(r"$10\,Dq$ (cm$^{-1}$)", fontsize=9)
        secax.tick_params(direction="in", labelsize=8)

    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    return buf.getvalue()
