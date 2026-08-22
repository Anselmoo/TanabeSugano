"""Matplotlib renderer for MCP plot tools.

Returns raw encoded bytes (PNG, PDF or SVG) so the MCP layer can wrap them
without needing matplotlib at import time on the agent side. The palette and axis
styling are shared with the CLI (see tanabesugano.plot_style) so both
surfaces produce visually-consistent, publication-style figures.
"""

from __future__ import annotations

import io
import math

from typing import TYPE_CHECKING

import matplotlib as mpl


# Force headless backend BEFORE importing pyplot.
mpl.use("Agg")
import matplotlib.pyplot as plt

from tanabesugano.figure_style import series_styles
from tanabesugano.mcp._compute import sweep_dq
from tanabesugano.plot_style import LABEL_FONT_PT
from tanabesugano.plot_style import LABEL_PITCH_PT
from tanabesugano.plot_style import apply_scientific_rcparams
from tanabesugano.plot_style import darken
from tanabesugano.plot_style import encoding_key
from tanabesugano.plot_style import spread_labels
from tanabesugano.plot_style import style_axes


if TYPE_CHECKING:
    from matplotlib.figure import Figure


_Y_LABEL_MATHTEXT: dict[str, str] = {
    "cm1": r"$E$ (cm$^{-1}$)",
    "eV": r"$E$ (eV)",
    "nm": r"$\lambda$ (nm)",
}

EXPORT_MIME_TYPES: dict[str, str] = {
    "png": "image/png",
    "pdf": "application/pdf",
    "svg": "image/svg+xml",
}
"""Renderable output formats -> their IANA-registered media types.

Spelled out rather than derived from the extension. FastMCP's
``File(data=..., format=...)`` helper maps a bare extension to
``application/<ext>``, which yields ``application/svg`` and ``application/png``
-- neither is a registered type and no client renders them. matplotlib's Agg,
PDF and SVG backends all accept these three via ``fig.savefig(format=...)``.
"""

_CM1_TO_EV_PNG: float = 1.0 / 8065.54


def _convert_energy_png(e_cm: float, unit: str) -> float:
    """Convert cm^-1 to the requested unit for matplotlib rendering."""
    if unit == "eV":
        return e_cm * _CM1_TO_EV_PNG
    if unit == "nm":
        return 1e7 / e_cm if e_cm else float("nan")
    return e_cm


def _ground_term_of(point: dict[str, list[float]]) -> str:
    """Term holding the lowest eigenvalue at one sweep point.

    ``sorted`` makes the tie deterministic; ties are real at Dq = 0.
    """
    return min(
        sorted(point),
        key=lambda term: min(point[term]) if point[term] else float("inf"),
    )


def _diagram_ground_term(
    d_count: int,
    dq_max: float,
    B: float,
    C: float,
    *,
    steps: int = 60,
) -> str:
    """Ground term at ``dq_max`` -- the term :func:`render_diagram` emphasises.

    Evaluated at the LAST sweep point, not the first, for two reasons that
    compound:

    * At Dq = 0 the ligand field vanishes, so every crystal-field component of
      the free-ion ground term is exactly degenerate and the argmin is decided
      by a tie-break rather than by physics -- d6 returns ``5_E`` where the
      weak-field ground term is ``5_T_2``. (The same trap is documented on
      :data:`~tanabesugano.mcp._compute.WEAK_FIELD_DQ_CM1`.)
    * d4-d7 cross over, so even a correct weak-field answer names the wrong
      term at strong field.

    The annotation is drawn at the right edge, so anchoring the choice there
    makes the label true where it is placed, by construction. Exposed
    separately from :func:`render_diagram` so it can be tested without
    rendering a figure.
    """
    _dq_values, points = sweep_dq(d_count, 0.0, dq_max, steps, B, C)
    return _ground_term_of(points[-1])


def _title(d_count: int, B: float, C: float, *, normalize: bool) -> str:
    """Figure title naming which diagram this is, not just the configuration."""
    kind = "Tanabe-Sugano" if normalize else "Energy-correlation"
    return f"{kind} diagram, d$^{{{d_count}}}$ (B = {B:g}, C = {C:g} cm$^{{-1}}$)"


def build_diagram(
    d_count: int,
    dq_min: float = 0.0,
    dq_max: float = 1500.0,
    steps: int = 60,
    B: float = 860.0,
    C: float = 3850.0,
    *,
    normalize: bool = True,
    energy_unit: str = "cm1",
    dpi: int = 144,
) -> Figure:
    """Build a Tanabe-Sugano (or DD-energy) diagram as a matplotlib Figure.

    Separated from :func:`render_diagram` so the figure itself can be
    asserted on. While this returned only encoded bytes, "every level carries
    its own label" was a claim no test could check without rasterising and
    reading pixels -- which is exactly how the figures came to name only the
    first level of each term and nobody noticed.

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
            DD-energy diagram (energy_unit axes) when False.
        energy_unit: "cm1", "eV", or "nm". Only affects the y-axis when
            normalize=False.  "nm" inverts the energy axis.
        dpi: Output resolution.

    """
    apply_scientific_rcparams()

    dq_values, points = sweep_dq(d_count, dq_min, dq_max, steps, B, C)
    term_keys = list(points[0].keys())
    styles = series_styles(d_count, dq_max, B, C)
    level_count = len(styles)

    # Height scales with how many labels have to fit down the right margin, and
    # width leaves that margin room. A fixed 7.2 x 4.8 in figure cannot carry
    # d6's 43 labels at any legible font size.
    fig_height = min(max(4.8, 0.21 * level_count), 11.0)
    fig, ax = plt.subplots(figsize=(9.0, fig_height), dpi=dpi)
    # Set the axes box BEFORE measuring it: the label pitch is derived from the
    # axes height in points, so measuring first and shrinking afterwards
    # computes the spacing for a figure that no longer exists.
    fig.subplots_adjust(left=0.09, right=0.80, top=0.88, bottom=0.16)

    x_axis = (dq_values * 10.0 / B) if normalize else (dq_values * 10.0)
    x_label = r"$10\,Dq / B$" if normalize else r"$10\,Dq$ (cm$^{-1}$)"
    y_label = r"$E / B$" if normalize else _Y_LABEL_MATHTEXT.get(energy_unit, r"$E$ (cm$^{-1}$)")

    # (end-of-curve y, label, colour) for every level, collected while drawing
    # so the label placement pass sees exactly what was plotted.
    endpoints: list[tuple[float, str, str]] = []

    for term in term_keys:
        series = [pt[term] for pt in points]
        max_n = max(len(s) for s in series)
        for n in range(max_n):
            style = styles[f"{term}#{n}"]
            y = [s[n] if n < len(s) else float("nan") for s in series]
            if normalize:
                y_plot = [v / B for v in y]
            else:
                y_plot = [_convert_energy_png(v, energy_unit) for v in y]
            ax.plot(x_axis, y_plot, **style.matplotlib_kwargs())
            last = y_plot[-1] if y_plot else float("nan")
            if not math.isnan(last):
                endpoints.append((float(last), style.label_latex, style.base_color))

    style_axes(
        ax, title=_title(d_count, B, C, normalize=normalize), x_label=x_label, y_label=y_label
    )
    encoding_key(ax, {style.multiplicity for style in styles.values()})

    # Direct labels in the right margin: every level is named, which the legend
    # never did -- it carried one entry per TERM, so each term's second and
    # later levels were drawn as anonymous dashes.
    if endpoints:
        low, high = ax.get_ylim()
        # Labels are spread inside the axes box, so without headroom the
        # topmost cluster is squeezed against the secondary x-axis.
        high += (high - low) * 0.02
        ax.set_ylim(low, high)
        axes_height_pt = fig_height * 72.0 * ax.get_position().height
        pitch = (high - low) * LABEL_PITCH_PT / max(axes_height_pt, 1.0)
        anchors = spread_labels(
            [y for y, _label, _color in endpoints],
            span=(low, high),
            pitch=pitch,
        )
        leader_threshold = pitch * 0.6
        # x in axes fraction, y in data: labels sit in a fixed right margin
        # regardless of the x-axis units, while their anchors track the curves.
        from matplotlib.transforms import blended_transform_factory

        margin = blended_transform_factory(ax.transAxes, ax.transData)
        x_right = float(x_axis[-1])
        for (y_curve, label, color), y_text in zip(endpoints, anchors, strict=True):
            ax.annotate(
                label,
                xy=(x_right, y_curve),
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
                    if abs(y_text - y_curve) > leader_threshold
                    else None
                ),
            )

    # Secondary x-axis: when normalized show raw 10Dq in cm^-1 on top.
    if normalize:
        secax = ax.secondary_xaxis(
            "top",
            functions=(lambda v: v * B, lambda v: v / B),
        )
        secax.set_xlabel(r"$10\,Dq$ (cm$^{-1}$)", fontsize=9)
        secax.tick_params(direction="in", labelsize=8)

    return fig


def render_diagram(
    d_count: int,
    dq_min: float = 0.0,
    dq_max: float = 1500.0,
    steps: int = 60,
    B: float = 860.0,
    C: float = 3850.0,
    *,
    normalize: bool = True,
    energy_unit: str = "cm1",
    dpi: int = 144,
    fmt: str = "png",
) -> bytes:
    """Render a diagram and return encoded bytes.

    ``fmt`` selects the container: ``"png"`` (raster, the default), ``"pdf"``
    or ``"svg"`` (both vector, for publication). ``dpi`` only affects the
    raster path; the vector backends carry true geometry.

    See :func:`build_diagram` for the arguments and the visual conventions.
    """
    if fmt not in EXPORT_MIME_TYPES:
        msg = f"unsupported format {fmt!r}; choose one of {sorted(EXPORT_MIME_TYPES)}"
        raise ValueError(msg)

    fig = build_diagram(
        d_count,
        dq_min,
        dq_max,
        steps,
        B,
        C,
        normalize=normalize,
        energy_unit=energy_unit,
        dpi=dpi,
    )
    buf = io.BytesIO()
    fig.savefig(buf, format=fmt)
    plt.close(fig)
    return buf.getvalue()
