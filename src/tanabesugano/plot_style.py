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

from typing import TYPE_CHECKING
from typing import Any


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
    """Return 2S+1 from a term-symbol key like ``4_T_1``; None if unparseable."""
    head = term.split("_", 1)[0]
    try:
        return int(head)
    except ValueError:
        return None


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
    ax.set_title(title, fontsize=11)
    ax.grid(visible=True, alpha=0.2, linewidth=0.6)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    ax.legend(
        loc="best",
        fontsize=7,
        ncol=2,
        frameon=False,
        handlelength=2.2,
    )
