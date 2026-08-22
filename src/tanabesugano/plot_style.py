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
* **Linestyle = spin-allowedness.** Solid where a transition from the ground
  level is spin-allowed, dashed where it is forbidden. Dash used to encode the
  level index, which recycled after five patterns while d6's ``3_T_1`` holds
  seven levels -- so the one visual channel a reader most relies on was both
  ambiguous *and* carrying an ordinal that appears in no textbook. Level index
  moved to a lightness ramp (:func:`shade`), which separates seven curves where
  five dash patterns cannot. :func:`linestyle_for` is kept for callers that have
  not migrated.
* **Ground term is emphasised** with thicker, fully-opaque lines; other
  curves run at ~0.85 alpha so dense regions don't crowd out the baseline.
* **Light grid + thin spines** for a publication-friendly look.
"""

from __future__ import annotations

import re

from typing import TYPE_CHECKING
from typing import TypedDict

import matplotlib as mpl


if TYPE_CHECKING:
    from matplotlib.axes import Axes
    from matplotlib.typing import LineStyleType


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

# matplotlib's own linestyle contract rather than a hand-written `str | tuple`.
# The loose alias type-checked here and failed at every call site: `str` is not
# assignable to the Literal set `Axes.plot` and `Line2D` actually accept, so
# every styled plot call was an error. Borrowing the upstream type means this
# cannot drift from what matplotlib will take.
type _LineStyle = LineStyleType
LEVEL_LINESTYLES: tuple[_LineStyle, ...] = ("-", "--", ":", "-.", (0, (3, 1, 1, 1)))

# The D3 encoding: dash carries spin-allowedness, which a chemist reads straight
# off the figure, rather than an internal ordinal. The forbidden dash is a long
# 5-on/2-off period on purpose -- the old "--" default rendered at 1.2 pt line
# width was what made dashed curves indistinguishable in the first place.
SPIN_ALLOWED_LINESTYLE: _LineStyle = "-"
SPIN_FORBIDDEN_LINESTYLE: _LineStyle = (0, (5, 2))

# Matplotlib linestyle -> plotly dash. Exists so the two renderers cannot
# disagree about what a dash means: plotly only understands these five names,
# so the mapping is lossy by nature and belongs in exactly one place.
PLOTLY_DASHES: dict[str, str] = {
    "-": "solid",
    "--": "dash",
    ":": "dot",
    "-.": "dashdot",
}
_FALLBACK_PLOTLY_DASH = "dash"

ANNOTATION_COLORS: dict[str, str] = {
    "observed": "#D55E00",
    "computed": "#0072B2",
    "spectrum": "#0072B2",
    "parameters": "#009E73",
    "reference_rule": "#666666",
    "marker": "#CC3311",
}
"""Colours for marks that are NOT a term curve.

Kept apart from :data:`SPIN_COLORS` because they answer a different question.
``SPIN_COLORS`` is a lookup: give it a multiplicity, get that multiplicity's
hue. These are roles: the observed spectrum, the computed one, a zero-residual
rule, a fitted-parameter marker. Nothing indexes them by a number, and a
"multiplicity" of ``observed`` is meaningless.

They deliberately reuse Okabe-Ito hues. That is safe only because they never
share an axes with term curves -- a fit plot shows observed against computed and
no manifold at all -- and it keeps the whole package inside one colour-blind-safe
palette. Adding a term curve to a fit figure would break that assumption, so
route any such figure through ``SPIN_COLORS`` and pick annotation roles that do
not collide.

``spectrum`` and ``computed`` share a hue for the same reason, one level down:
``spectrum`` is the measured absorption envelope in the UV-Vis figures and
``computed`` is a calculated band marker in the fit figures, and no figure draws
both. ``observed`` is vermillion in every surface, which is the one association
a reader carries between figures -- do not reassign it.
"""

_FALLBACK_COLOR = "#444444"

# How far the level-index ramp may travel toward white. Above ~0.55 an
# Okabe-Ito hue stops holding contrast against the white figure background,
# which would trade one unreadable channel for another.
_MAX_LIGHTEN = 0.55

# A "#rrggbb" string; anything else (a named colour, "tab:blue") is returned by
# `shade` untouched rather than mangled.
_HEX_COLOR_LENGTH = 7

# Below two levels there is no ramp to draw.
_MIN_RAMP_LEVELS = 2

# The ramp spends its full range only on terms large enough to need it. Dividing
# by `n_levels - 1` alone sent a two-level term straight to maximum lightness,
# which made d3's 4T1g(P) -- one of the three bands Cr(III) is known for -- too
# pale to read. A floor on the denominator keeps small multiplets near their
# palette colour while seven-level terms still fan out fully.
_RAMP_DENOMINATOR = 4


class LineKwargs(TypedDict):
    """Exactly the ``Axes.plot`` keywords this package sets.

    A plain ``dict[str, object]`` unpacked into ``plot(**kwargs)`` erases every
    value type, so the checker cannot tell a linestyle from a linewidth and
    reports the whole call as wrong. Naming the four keys keeps the call site
    checkable.
    """

    color: str
    linestyle: _LineStyle
    linewidth: float
    alpha: float


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


def color_for_multiplicity(multiplicity: int) -> str:
    """Palette colour for a spin multiplicity, with the neutral fallback.

    The counterpart of :func:`color_for` for callers that already hold the
    integer rather than a term key -- the Chart.js layer buckets levels by
    multiplicity before it draws them. Exists so those callers stop reaching
    for a private fallback constant, or worse, writing their own table: two
    such tables existed in ``mcp/apps.py``, both shifted by one multiplicity
    against this one.
    """
    return SPIN_COLORS.get(multiplicity, _FALLBACK_COLOR)


def linestyle_for(level: int) -> _LineStyle:
    """Pick a linestyle for the n-th level within a term.

    Superseded by :func:`linestyle_for_transition` for figures that carry
    spin-allowedness (see the module docstring). Kept because it is the
    fallback :func:`line_style_for` uses when a caller has no spin information.
    """
    return LEVEL_LINESTYLES[level % len(LEVEL_LINESTYLES)]


def linestyle_for_transition(*, spin_allowed: bool) -> _LineStyle:
    """Solid when a transition from the ground level is spin-allowed."""
    return SPIN_ALLOWED_LINESTYLE if spin_allowed else SPIN_FORBIDDEN_LINESTYLE


def to_plotly_dash(linestyle: _LineStyle) -> str:
    """Map a matplotlib linestyle onto plotly's dash vocabulary.

    Plotly understands only ``solid``/``dash``/``dot``/``dashdot``/``longdash``,
    so an explicit dash tuple like :data:`SPIN_FORBIDDEN_LINESTYLE` has no exact
    counterpart and lands on ``dash``. That loss is fine -- what must not happen
    is the two renderers each inventing their own approximation.
    """
    if isinstance(linestyle, str):
        return PLOTLY_DASHES.get(linestyle, _FALLBACK_PLOTLY_DASH)
    return _FALLBACK_PLOTLY_DASH


def plotly_dash_for_transition(*, spin_allowed: bool) -> str:
    """Return the plotly dash name for the same encoding :func:`linestyle_for_transition` uses."""
    return to_plotly_dash(linestyle_for_transition(spin_allowed=spin_allowed))


def shade(color: str, level: int, n_levels: int) -> str:
    """Lighten *color* in proportion to a level's position within its term.

    Hue keeps encoding spin multiplicity; lightness encodes the level index.
    Seven levels of one term stay separable this way, which five recycling dash
    patterns could not manage -- see the module docstring.

    ``level == 0`` returns *color* unchanged, so the lowest level of every term
    is drawn in the exact palette colour and diagrams that hold only
    single-level terms look identical to before.

    Args:
        color: Base ``#rrggbb`` colour, normally from :func:`color_for`.
        level: Level index within the term (0 = lowest).
        n_levels: Size of the term's multiplet. Values < 2 disable the ramp.

    """
    if n_levels < _MIN_RAMP_LEVELS or level <= 0:
        return color
    if not (len(color) == _HEX_COLOR_LENGTH and color.startswith("#")):
        return color
    fraction = _MAX_LIGHTEN * min(level, n_levels - 1) / max(n_levels - 1, _RAMP_DENOMINATOR)
    channels = (int(color[i : i + 2], 16) for i in (1, 3, 5))
    blended = (round(c + (255 - c) * fraction) for c in channels)
    return "#{:02X}{:02X}{:02X}".format(*blended)


def line_style_for(
    term: str,
    *,
    level: int = 0,
    is_ground: bool = False,
    n_levels: int = 1,
    spin_allowed: bool | None = None,
) -> LineKwargs:
    """Return matplotlib `plot()` kwargs for one curve.

    Two encodings live here, and which one you get depends on whether the
    caller can say anything about spin:

    * ``spin_allowed`` given -> the D3 encoding: hue = multiplicity,
      lightness = level index, dash = spin-allowedness.
    * ``spin_allowed=None`` -> the historical encoding, dash = level index.

    The fallback is deliberate rather than lazy. Spin-allowedness is defined
    relative to a *ground level*, so a caller plotting an isolated term block
    has no honest answer, and inventing one would put a meaning on the dash
    channel that the figure cannot support.

    Args:
        term: Term-symbol key (e.g. ``"2_T_2"``).
        level: Level index within the term (0 = lowest).
        is_ground: True for curves belonging to the ground-state term;
            renders thicker / fully opaque to anchor the diagram.
        n_levels: Size of the term's multiplet; drives the lightness ramp.
        spin_allowed: Whether a transition from the ground level to this level
            is spin-allowed. ``None`` when the caller cannot know.

    """
    linestyle = (
        linestyle_for(level)
        if spin_allowed is None
        else linestyle_for_transition(spin_allowed=spin_allowed)
    )
    return {
        "color": shade(color_for(term), level, n_levels),
        "linestyle": linestyle,
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


def term_to_plotly(term: str, *, assume_gerade: bool = True) -> str:
    """Convert a key like ``"4_T_1"`` to plotly markup ``"<sup>4</sup>T<sub>1g</sub>"``.

    The fourth rung of the notation ladder that :func:`term_to_mathtext`,
    :func:`term_to_unicode` and :func:`term_to_ascii` already form -- identical
    spelling, different renderer. Plotly.js understands a small HTML subset
    (``<b> <i> <sup> <sub> <br> <span>``) in trace names, hover text and axis
    titles, which typesets a term symbol properly where Unicode can only
    approximate it with pre-composed digit glyphs.

    Use this **only** on plotly surfaces. The markup is inert everywhere else
    and would be printed verbatim by matplotlib, Chart.js, a CSV cell or a
    terminal -- exactly the failure mode CLAUDE.md records for handing Chart.js
    LaTeX. Every other surface has its own rung above.

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
    sub_part = f"{m.group('sub') or ''}{parity}"
    body = f"{irrep}<sub>{sub_part}</sub>" if sub_part else irrep
    return f"<sup>{m.group('mult')}</sup>{body}"


# A curve label needs this much vertical room, in points, before it collides
# with its neighbour. Measured from the 7 pt label font plus leading, not tuned
# against a particular figure: at 7 pt a line box is ~8.4 pt tall.
LABEL_PITCH_PT = 8.6
LABEL_FONT_PT = 7.0


def darken(color: str, fraction: float = 0.35) -> str:
    """Blend a palette colour toward black for use as label text.

    The palette is chosen for LINES on white. Set the same values as 7 pt type
    and the pale end -- Okabe-Ito's singlet grey above all -- stops being
    readable. Lines keep the palette value; their labels get this.
    """
    if not (len(color) == _HEX_COLOR_LENGTH and color.startswith("#")):
        return color
    channels = (int(color[i : i + 2], 16) for i in (1, 3, 5))
    return "#{:02X}{:02X}{:02X}".format(*(round(c * (1.0 - fraction)) for c in channels))


def spread_labels(
    positions: list[float],
    *,
    span: tuple[float, float],
    pitch: float,
) -> list[float]:
    """Nudge label anchors apart so none overlaps, preserving their order.

    Two upward passes and one downward pass over positions sorted by value: push
    each label at least ``pitch`` above its predecessor, then, if that pushed the
    stack past the top of the axes, push back down from the top. Order is never
    swapped, so a label always sits nearest the curve it names -- which is the
    only property that makes a leader-free direct label readable at all.

    A collision-avoidance library (adjustText) would do this and more, but it is
    a runtime dependency for a problem whose exact shape is known: one column,
    fixed pitch, monotone order.

    Args:
        positions: Desired y anchors, in data units, one per label.
        span: ``(low, high)`` bounds the labels must stay inside.
        pitch: Minimum vertical gap, in data units.

    Returns:
        Adjusted anchors in the same order as ``positions``.

    """
    if not positions:
        return []
    order = sorted(range(len(positions)), key=lambda i: positions[i])
    placed = [positions[i] for i in order]

    for i in range(1, len(placed)):
        placed[i] = max(placed[i], placed[i - 1] + pitch)

    low, high = span
    if placed[-1] > high:
        placed[-1] = high
        for i in range(len(placed) - 2, -1, -1):
            placed[i] = min(placed[i], placed[i + 1] - pitch)
    if placed[0] < low:
        placed[0] = low
        for i in range(1, len(placed)):
            placed[i] = max(placed[i], placed[i - 1] + pitch)

    out = [0.0] * len(positions)
    for slot, original in enumerate(order):
        out[original] = placed[slot]
    return out


def encoding_key(ax: Axes, multiplicities: set[int]) -> None:
    """Legend explaining the three visual channels, not listing the states.

    A d6 diagram holds 43 levels. A legend naming each one is a wall of text
    that no reader parses, and it was previously avoided by naming only the
    lowest level of every term -- which left every other curve anonymous. The
    states are named on the curves themselves now, so the legend's job is to say
    what colour, lightness and dash MEAN.
    """
    from matplotlib.lines import Line2D

    from tanabesugano.plot_style import SPIN_ALLOWED_LINESTYLE
    from tanabesugano.plot_style import SPIN_COLORS
    from tanabesugano.plot_style import SPIN_FORBIDDEN_LINESTYLE

    names = {1: "singlet", 2: "doublet", 3: "triplet", 4: "quartet", 5: "quintet", 6: "sextet"}
    handles = [
        Line2D(
            [],
            [],
            color=SPIN_COLORS.get(m, "#444444"),
            linewidth=2.0,
            label=names.get(m, f"2S+1 = {m}"),
        )
        for m in sorted(multiplicities)
    ]
    handles += [
        Line2D([], [], color="#444444", linestyle=SPIN_ALLOWED_LINESTYLE, label="spin-allowed"),
        Line2D(
            [],
            [],
            color="#444444",
            linestyle=SPIN_FORBIDDEN_LINESTYLE,
            label="spin-forbidden",
        ),
    ]
    ax.legend(
        handles=handles,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.10),
        fontsize=8,
        ncol=min(len(handles), 5),
        frameon=False,
        handlelength=2.6,
        labelspacing=0.35,
        columnspacing=1.4,
        title="colour = spin multiplicity   ·   paler = higher level of the same term",
        title_fontsize=7.5,
    )


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
