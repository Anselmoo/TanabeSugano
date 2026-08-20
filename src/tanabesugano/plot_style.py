"""Shared matplotlib plot styling for TanabeSugano figures.

Provides a single source of truth for line colours, linestyles, and axis
decoration so the CLI (`cmd.py plot()`) and the MCP layer (`mcp/plotting.py`)
produce visually-consistent figures.

Design choices
--------------
* **Colour = spin multiplicity.** The leading integer of a term symbol like
  ``2_T_2`` or ``4_T_1`` is ``2S+1``. Mapping spin to colour keeps quartet
  states visually distinct from doublets -- the prior rainbow colouring
  scrambled this information and made d^5 diagrams in particular hard to read.
  Colours are taken from the Okabe-Ito palette, which is colour-blind safe.
* **Linestyle = level index within a term.** The lowest level of each term
  is solid; higher levels are dashed / dotted / dash-dotted to keep the
  legend short while still letting users trace individual states.
* **Ground term is emphasised** with thicker, fully-opaque lines; other
  curves run at ~0.85 alpha so dense regions don't crowd out the baseline.
* **Light grid + thin spines** for a publication-friendly look.
"""

from __future__ import annotations

import re

from typing import TYPE_CHECKING
from typing import Any

import matplotlib as mpl


if TYPE_CHECKING:
    from matplotlib.axes import Axes


# Okabe-Ito colour-blind-safe palette, indexed by spin multiplicity (2S+1).
# Index 0 unused. Singlets are grey; spectroscopically inactive on most TS
# diagrams but kept for completeness.
SPIN_COLORS: dict[int, str] = {
    1: "#999999",  # singlet — grey
    2: "#E69F00",  # doublet — orange
    3: "#0072B2",  # triplet — blue
    4: "#009E73",  # quartet — green
    5: "#D55E00",  # quintet — vermillion
    6: "#CC79A7",  # sextet  — magenta
    7: "#56B4E9",  # septet  — sky (rare; fallback)
}

_LineStyle = str | tuple[int, tuple[int, ...]]
LEVEL_LINESTYLES: tuple[_LineStyle, ...] = ("-", "--", ":", "-.", (0, (3, 1, 1, 1)))

_FALLBACK_COLOR = "#444444"


def multiplicity_of(term: str) -> int | None:
    """Return 2S+1 from a term-symbol key like ``4_T_1``; None if unparseable.

    Presentation-layer helper: an unrecognised key falls back to a default
    colour/linestyle rather than failing a plot. Code that reasons about the
    *physics* must use ``_compute.term_multiplicity``, which raises instead --
    silently treating a free-ion string like ``"3F"`` as "no multiplicity" is
    how the spin-allowed filter came to be disabled across four tools.

    Both share :data:`_TERM_RE` so there is one parse mechanism, not two.
    """
    match = _TERM_RE.match(term)
    return int(match.group("mult")) if match else None


def color_for(term: str) -> str:
    """Pick a colour for *term* based on its spin multiplicity."""
    m = multiplicity_of(term)
    if m is None:
        return _FALLBACK_COLOR
    return SPIN_COLORS.get(m, _FALLBACK_COLOR)


def linestyle_for(level: int) -> _LineStyle:
    """Pick a linestyle for the n-th level within a term."""
    return LEVEL_LINESTYLES[level % len(LEVEL_LINESTYLES)]


def line_style_for(term: str, *, level: int = 0, is_ground: bool = False) -> dict[str, Any]:
    """Return matplotlib `plot()` kwargs for one curve.

    Args:
        term: Term-symbol key (e.g. ``"2_T_2"``).
        level: Level index within the term (0 = lowest).
        is_ground: True for curves belonging to the ground-state term;
            renders thicker / fully opaque to anchor the diagram.

    """
    return {
        "color": color_for(term),
        "linestyle": linestyle_for(level),
        "linewidth": 2.0 if is_ground else 1.2,
        "alpha": 1.0 if is_ground else 0.85,
    }


def style_axes(ax: Axes, *, title: str, x_label: str, y_label: str) -> None:
    """Apply consistent grid / legend / spine styling."""
    ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)
    ax.set_title(title, fontsize=12)
    ax.grid(visible=True, alpha=0.25, linewidth=0.6)
    ax.minorticks_on()
    ax.tick_params(which="both", direction="in", top=False, right=False, length=4)
    ax.tick_params(which="minor", length=2)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    handles, labels = ax.get_legend_handles_labels()
    if handles:
        ax.legend(
            handles,
            labels,
            loc="best",
            fontsize=8,
            ncol=2,
            frameon=False,
            handlelength=2.4,
            labelspacing=0.35,
            columnspacing=1.0,
        )


# Term-symbol grammar produced by `tanabesugano.matrices.dN.solver()`.
#
# STRICT by design. The previous pattern was `\d+_[ABET](_\d+)?(_[gu])?`, which
# accepted "1_T_3" (no T3 irrep exists in Oh), "5_E_1" (Eg carries no subscript),
# "9_B_2", "1_T_9" and "0_A_1". That permissiveness is *why* the first two
# survived for the life of the project: nothing in the codebase could tell a
# real key from a typo. Now: multiplicity 1..6; A and T carry subscript 1 or 2;
# E carries none. Trailing "_g"/"_u" is tolerated for forward compatibility --
# current keys are gerade-only.
#
# `terms.TERM_KEY_RE` is the same grammar; this copy exists because plot_style
# is imported by `terms`-free code paths and must stay dependency-light. The
# two are kept in step by test_terms.py, which validates both against the
# closed TermKey set.
_TERM_RE = re.compile(
    r"^(?P<mult>[1-6])_(?:(?P<irrep>[AT])_(?P<sub>[12])|(?P<e_irrep>E))"
    r"(?:_(?P<parity>[gu]))?$",
)


def term_to_mathtext(term: str, *, assume_gerade: bool = True) -> str:
    """Convert a key like ``"4_T_1"`` to matplotlib mathtext ``r"$^{4}T_{1g}$"``.

    Falls back to the raw key with underscores stripped if the pattern doesn't
    match, so unknown / forward-compatible term strings still render readably.

    Args:
        term: The raw term-symbol key from `tanabesugano.matrices.solver()`.
        assume_gerade: When True (default) and no parity is encoded in the key,
            append the octahedral ``_g`` subscript that's standard for d^n
            crystal-field terms.

    """
    m = _TERM_RE.match(term)
    if not m:
        return term.replace("_", " ")
    mult = m.group("mult")
    irrep = m.group("irrep") or m.group("e_irrep")
    sub = m.group("sub")
    parity = m.group("parity") or ("g" if assume_gerade else "")
    sub_part = f"{sub}{parity}" if sub else parity
    if sub_part:
        return rf"$^{{{mult}}}{irrep}_{{{sub_part}}}$"
    return rf"$^{{{mult}}}{irrep}$"


_SUPER = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")
_SUB = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")


def term_to_unicode(term: str, *, assume_gerade: bool = True) -> str:
    """Convert a key like ``"4_T_1"`` to Unicode ``"⁴T₁g"``.

    Uses Unicode superscript digits for multiplicity and subscript digits for
    the symmetry label. Suitable for Prefab DataTable cells, chart labels, and
    any context that cannot render matplotlib mathtext or LaTeX.

    Falls back to the raw key with underscores replaced by spaces if the
    pattern does not match.

    Args:
        term: The raw term-symbol key from `tanabesugano.matrices.solver()`.
        assume_gerade: When True (default) and no parity is encoded in the key,
            append the octahedral ``g`` subscript.

    """
    m = _TERM_RE.match(term)
    if not m:
        return term.replace("_", " ")
    mult = m.group("mult").translate(_SUPER)
    irrep = m.group("irrep") or m.group("e_irrep")
    sub = (m.group("sub") or "").translate(_SUB)
    parity = m.group("parity") or ("g" if assume_gerade else "")
    return f"{mult}{irrep}{sub}{parity}"


def term_to_ascii(term: str, *, assume_gerade: bool = True) -> str:
    """Convert a key like ``"4_T_1"`` to plain ASCII ``"4T1g"``.

    The lowest-fidelity rung of the same notation ladder as
    :func:`term_to_unicode` and :func:`term_to_mathtext`: identical spelling,
    no characters outside ASCII. For log lines, CSV columns and any terminal
    that cannot be trusted with Unicode digits.

    This is *not* the raw solver key -- ``4_T_1`` keeps its underscores and is
    what :attr:`tanabesugano.levels.Level.uid` is built from.

    Falls back to the raw key with underscores replaced by spaces if the
    pattern does not match.

    Args:
        term: The raw term-symbol key from `tanabesugano.matrices.solver()`.
        assume_gerade: When True (default) and no parity is encoded in the key,
            append the octahedral ``g`` subscript.

    """
    m = _TERM_RE.match(term)
    if not m:
        return term.replace("_", " ")
    irrep = m.group("irrep") or m.group("e_irrep")
    parity = m.group("parity") or ("g" if assume_gerade else "")
    return f"{m.group('mult')}{irrep}{m.group('sub') or ''}{parity}"


def apply_scientific_rcparams() -> None:
    """Push a single set of publication-style rcParams.

    Idempotent: safe to call from every render. Uses DejaVu Serif (ships with
    matplotlib, no extra fonts needed) and Computer Modern math so term
    symbols look like a Coordination Chemistry textbook rather than the
    matplotlib 2.x default.
    """
    mpl.rcParams.update(
        {
            "font.family": "serif",
            "font.serif": ["DejaVu Serif", "Computer Modern Roman", "Times New Roman"],
            "mathtext.fontset": "cm",
            "axes.labelsize": 11,
            "axes.titlesize": 12,
            "axes.titleweight": "regular",
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "axes.formatter.use_mathtext": True,
            "axes.formatter.limits": (-3, 4),
            "grid.alpha": 0.25,
            "grid.linewidth": 0.6,
            "xtick.direction": "in",
            "ytick.direction": "in",
            "xtick.minor.visible": True,
            "ytick.minor.visible": True,
            "xtick.major.size": 4.0,
            "ytick.major.size": 4.0,
            "xtick.minor.size": 2.0,
            "ytick.minor.size": 2.0,
            "legend.frameon": False,
            "legend.fontsize": 8,
            "figure.dpi": 144,
            "savefig.bbox": "tight",
            "savefig.facecolor": "white",
        },
    )


def annotate_ground_term(
    ax: Axes,
    *,
    term: str,
    x: float,
    y: float,
) -> None:
    """Place a small mathtext annotation flagging the ground-state term.

    Used by the matplotlib renderer to label the ground term at the right
    edge of the plot without crowding the legend.
    """
    ax.annotate(
        term_to_mathtext(term),
        xy=(x, y),
        xytext=(4, 0),
        textcoords="offset points",
        fontsize=9,
        color=color_for(term),
        va="center",
        ha="left",
    )
