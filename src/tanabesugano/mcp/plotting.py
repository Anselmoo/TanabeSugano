"""Matplotlib renderer for MCP plot tools.

Returns raw PNG bytes so the MCP layer can wrap them as ImageContent without
needing matplotlib at import time on the agent side. The palette is shared
with the CLI (see tanabesugano.plot_style) so both surfaces produce
visually-consistent figures.
"""

from __future__ import annotations

import io

import matplotlib as mpl


# Force headless backend BEFORE importing pyplot.
mpl.use("Agg")
import matplotlib.pyplot as plt

from tanabesugano.mcp._compute import sweep_dq
from tanabesugano.plot_style import line_style_for
from tanabesugano.plot_style import style_axes


def render_diagram_png(
    d_count: int,
    dq_min: float = 0.0,
    dq_max: float = 1.5,
    steps: int = 50,
    B: float = 860.0,
    C: float = 3801.0,
    *,
    normalize: bool = True,
    dpi: int = 120,
) -> bytes:
    """Render a Tanabe-Sugano (or DD-energy) diagram and return PNG bytes.

    Curves are coloured by spin multiplicity (Okabe-Ito palette, colour-blind
    safe), level index within a term uses linestyle, and the ground-state
    line is emphasised. Replaces the prior rainbow colouring, which made
    states from different spin manifolds indistinguishable.

    Args:
        d_count: 2..8.
        dq_min: Lower Dq bound of the sweep (cm^-1).
        dq_max: Upper Dq bound of the sweep (cm^-1).
        steps: Number of sweep points.
        B: Racah B parameter (cm^-1).
        C: Racah C parameter (cm^-1).
        normalize: If True, render the classical Tanabe-Sugano diagram
            (E/B vs 10Dq/B). If False, render the DD-energy diagram
            (energy vs 10Dq, both in cm^-1).
        dpi: Output resolution.

    """
    dq_values, points = sweep_dq(d_count, dq_min, dq_max, steps, B, C)
    term_keys = list(points[0].keys())

    # Identify the ground term — the one with the lowest eigenvalue at Dq=0.
    ground_term = min(
        term_keys,
        key=lambda t: min(points[0][t]) if points[0][t] else float("inf"),
    )

    fig, ax = plt.subplots(figsize=(6.8, 4.6), dpi=dpi)
    x_axis = (dq_values * 10.0 / B) if normalize else (dq_values * 10.0)
    x_label = r"$10Dq/B$" if normalize else r"$10Dq$ (cm$^{-1}$)"
    y_label = r"$E/B$" if normalize else r"$E$ (cm$^{-1}$)"

    for term in term_keys:
        series = [pt[term] for pt in points]
        max_n = max(len(s) for s in series)
        for n in range(max_n):
            y = [s[n] if n < len(s) else float("nan") for s in series]
            y_plot = [v / B if normalize else v for v in y]
            style = line_style_for(term, level=n, is_ground=(term == ground_term))
            ax.plot(
                x_axis,
                y_plot,
                label=term if n == 0 else None,
                **style,
            )

    style_axes(
        ax,
        title=f"Tanabe-Sugano d{d_count} (B={B:g}, C={C:g})",
        x_label=x_label,
        y_label=y_label,
    )
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    return buf.getvalue()
