"""How one energy level is drawn, decided once for every renderer.

``plot_style`` owns the vocabulary -- what colours exist, how a term symbol is
spelled in four alphabets, which dash means what. This module owns the
*decision*: given a configuration, it says that level ``3_T_1#1`` is this
colour, this dash, and carries this label, and it says so identically to
matplotlib, to plotly, to Chart.js and to the manifest the docs site reads.

That split matters. Before it existed, four surfaces each decided for
themselves and all four disagreed: the committed plotly diagrams keyed
``px.colors.qualitative.Light24`` off the first character of a solver key, the
React app carried a hand-written palette that mapped a quartet to orange where
matplotlib maps it to green, and ``mcp/apps.py`` held a second Okabe-Ito table
shifted by one multiplicity. Same state, four colours.

The encoding
------------
* **Hue = spin multiplicity** (Okabe-Ito, colour-blind safe) -- unchanged.
* **Lightness = level index within the term.** d6's ``3_T_1`` holds seven
  levels; five recycling dash patterns cannot separate them, a lightness ramp
  can.
* **Dash = spin-allowedness**, relative to the ground level. Solid is a
  transition a chemist can actually observe. d5 comes out entirely dashed,
  which is precisely why Mn(II) is pale.

Spin-allowedness is evaluated at ONE point, not per x-value, because a curve
carries one dash for its whole length. :func:`series_styles` therefore takes the
Dq the caller wants it judged at, and figure code passes the sweep's upper
bound -- the same anchor ``mcp.plotting._diagram_ground_term`` already uses for
the ground-term annotation, so the two agree by construction. For d4-d7 the
ground term crosses over, so a figure spanning a crossover must say which end
its dashes refer to; that is the encoding key's job, not this module's.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from tanabesugano.terms import TermKey


if TYPE_CHECKING:
    from tanabesugano.plot_style import LineKwargs
    from tanabesugano.plot_style import _LineStyle


@dataclass(frozen=True)
class SeriesStyle:
    """Everything any renderer needs in order to draw one level."""

    uid: str
    """``3_T_1#1`` -- the machine key. Round-trips; never key on a label."""
    term: str
    level_index: int
    multiplicity: int
    color: str
    """``#rrggbb``, already shaded for :attr:`level_index`."""
    base_color: str
    """The unshaded palette colour for this multiplicity.

    A direct label drawn in :attr:`color` inherits the lightness ramp, and at
    the top of a seven-level term that is pale enough to be unreadable as text.
    Lines can afford the ramp because they are long; four-character labels
    cannot. So the curve gets :attr:`color` and its label gets this.
    """
    dash: str
    """Plotly dash name."""
    linestyle: _LineStyle
    """Matplotlib linestyle -- the same decision as :attr:`dash`, other alphabet."""
    label_unicode: str
    label_latex: str
    label_plotly: str
    spin_allowed: bool
    is_ground: bool
    """THE ground level, not merely a member of the ground term.

    The distinction is load-bearing: low-spin d6 has ``1_A_1`` as its ground
    term and that term holds five levels, so emphasising the term would draw
    five thick curves and anchor nothing. The ground LEVEL is the flat E = 0
    baseline, and that is the one curve a reader needs to find first.
    """

    def matplotlib_kwargs(self) -> LineKwargs:
        """``ax.plot()`` kwargs carrying this decision."""
        return {
            "color": self.color,
            "linestyle": self.linestyle,
            "linewidth": 2.0 if self.is_ground else 1.2,
            "alpha": 1.0 if self.is_ground else 0.9,
        }

    def as_manifest_entry(self) -> dict[str, object]:
        """Return the JSON the docs site reads instead of carrying its own palette.

        Plotly markup is the label here because the only consumer is the React
        app, which renders through plotly.js. Unicode rides along so a tooltip
        or table in that app has a rung that needs no HTML.
        """
        return {
            "uid": self.uid,
            "label": self.label_plotly,
            "label_unicode": self.label_unicode,
            "color": self.color,
            "dash": self.dash,
            "mult": self.multiplicity,
            "spin_allowed": self.spin_allowed,
        }


def column_to_uid(column: str) -> str:
    """Map a CSV/DataFrame column name onto a :attr:`Level.uid`.

    ``CMDmain.subsplit_states`` names a column ``3_T_1_0`` when the term holds
    several levels and plain ``3_T_1`` when it holds one -- mirroring
    ``Level.ordinal``, which suppresses the ordinal for single-level terms.

    Splitting on the last underscore is NOT enough, and this is where the
    existing ``cmd._split`` goes wrong: every A and T term key already ends in a
    digit, so ``"3_A_1"`` splits into ``("3_A", 1)`` and the caller then asks
    for the colour of ``3_A`` -- which matches no term, so every single-level
    A/T curve silently rendered in the fallback grey. Membership in
    :class:`~tanabesugano.terms.TermKey` is what makes the split decidable.
    """
    if column in TermKey.__members__.values() or _is_term(column):
        return f"{column}#0"
    head, _, tail = column.rpartition("_")
    if tail.isdigit() and _is_term(head):
        return f"{head}#{int(tail)}"
    return f"{column}#0"


def _is_term(candidate: str) -> bool:
    try:
        TermKey(candidate)
    except ValueError:
        return False
    return True


def series_styles(
    d_count: int,
    dq: float,
    B: float,
    C: float,
) -> dict[str, SeriesStyle]:
    """Decide how every level of one configuration is drawn. Keyed by uid.

    One :meth:`LevelSet.solve` call, not one per sweep point: parentage costs an
    extra zero-field solve and the answer does not depend on where along the
    sweep you ask.
    """
    from tanabesugano import plot_style
    from tanabesugano.levels import LevelSet

    levels = LevelSet.solve(d_count, dq, B, C)
    allowed = {lv.uid for lv in levels.spin_allowed()}
    ground_uid = levels.ground.uid
    multiplet_size = {term: len(levels.for_term(term)) for term in levels.terms}

    unicode_labels = levels.display_labels("unicode")
    latex_labels = levels.display_labels("latex")
    plotly_labels = levels.display_labels("plotly")

    styles: dict[str, SeriesStyle] = {}
    for level in levels.levels:
        # The ground level itself is solid: it is the state every arrow starts
        # from, so calling it "forbidden" would be meaningless rather than false.
        is_allowed = level.uid in allowed or level.energy_cm1 == 0.0
        linestyle = plot_style.linestyle_for_transition(spin_allowed=is_allowed)
        styles[level.uid] = SeriesStyle(
            uid=level.uid,
            term=level.term.value,
            level_index=level.index,
            multiplicity=level.multiplicity,
            color=plot_style.shade(
                plot_style.color_for(level.term.value),
                level.index,
                multiplet_size[level.term],
            ),
            base_color=plot_style.color_for(level.term.value),
            dash=plot_style.to_plotly_dash(linestyle),
            linestyle=linestyle,
            label_unicode=unicode_labels[level.uid],
            label_latex=latex_labels[level.uid],
            label_plotly=plotly_labels[level.uid],
            spin_allowed=is_allowed,
            is_ground=level.uid == ground_uid,
        )
    return styles
