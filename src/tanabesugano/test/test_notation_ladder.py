"""One term symbol, four alphabets: the notation ladder must not fork.

``plot_style`` renders a solver key in four ways -- ASCII (``4T1g``), Unicode
(``⁴T₁g``), matplotlib mathtext (``$^{4}T_{1g}$``) and plotly markup
(``<sup>4</sup>T<sub>1g</sub>``) -- because four renderers each understand a
different subset of typography. Chart.js prints LaTeX verbatim; matplotlib
prints plotly tags verbatim; a CSV cell wants neither.

Four spellings of one symbol is exactly the shape of drift that put ``1_T_3``
and ``5_E_1`` into this codebase for years, so the contract here is not "each
rung renders something" but "all four rungs say the SAME THING". Each is
stripped back to its bare letters and checked against ``TermKey``'s own
``multiplicity`` / ``irrep`` / ``subscript`` properties -- an oracle that does
not run through ``plot_style._TERM_RE`` and so cannot be wrong in the same way
the thing under test is wrong.

The plotly rung is new; the other three are pinned here for the first time.
"""

from __future__ import annotations

import re

import pytest

from tanabesugano import plot_style
from tanabesugano.levels import LevelSet
from tanabesugano.mcp._defaults import DEFAULTS
from tanabesugano.terms import TermKey


ALL_D = tuple(range(2, 9))
ALL_TERMS = tuple(TermKey)

_UNSUPER = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹", "0123456789")
_UNSUB = str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789")


def _expected_ascii(term: TermKey) -> str:
    """``4T1g`` built from TermKey's own properties, not from plot_style."""
    sub = "" if term.subscript is None else str(term.subscript)
    return f"{term.multiplicity}{term.irrep.value}{sub}g"


def _strip(rendering: str, rung: str) -> str:
    """Reduce any rung to its bare letters and digits."""
    if rung == "unicode":
        return rendering.translate(_UNSUPER).translate(_UNSUB)
    if rung == "plotly":
        return re.sub(r"</?su[pb]>", "", rendering)
    if rung == "latex":
        return re.sub(r"[${}^_]", "", rendering)
    return rendering


class TestLadderRungsAgree:
    """Every rung spells every term the same way."""

    @pytest.mark.parametrize("term", ALL_TERMS, ids=lambda t: t.value)
    @pytest.mark.parametrize("rung", ["ascii", "unicode", "latex", "plotly"])
    def test_rung_matches_termkey_properties(self, term: TermKey, rung: str) -> None:
        render = {
            "ascii": plot_style.term_to_ascii,
            "unicode": plot_style.term_to_unicode,
            "latex": plot_style.term_to_mathtext,
            "plotly": plot_style.term_to_plotly,
        }[rung]
        assert _strip(render(term.value), rung) == _expected_ascii(term)

    @pytest.mark.parametrize("term", ALL_TERMS, ids=lambda t: t.value)
    def test_plotly_rung_is_well_formed_markup(self, term: TermKey) -> None:
        """Plotly.js accepts only a small tag subset; unbalanced tags print raw."""
        rendered = plot_style.term_to_plotly(term.value)
        assert rendered.count("<sup>") == rendered.count("</sup>") == 1
        assert rendered.count("<sub>") == rendered.count("</sub>") <= 1
        assert not set(re.findall(r"</?(\w+)>", rendered)) - {"sup", "sub"}

    def test_unparseable_key_falls_back_like_its_siblings(self) -> None:
        """A forward-compatible key must still render, and identically to the rest."""
        for render in (
            plot_style.term_to_ascii,
            plot_style.term_to_unicode,
            plot_style.term_to_plotly,
            plot_style.term_to_mathtext,
        ):
            assert render("9_Q_7") == "9 Q 7"


class TestShadeRamp:
    """Lightness carries the level index, so it must be monotone and bounded."""

    def test_level_zero_is_the_untouched_palette_colour(self) -> None:
        assert plot_style.shade("#0072B2", 0, 7) == "#0072B2"

    def test_single_level_term_never_shades(self) -> None:
        assert plot_style.shade("#0072B2", 0, 1) == "#0072B2"

    def test_ramp_is_strictly_lighter_with_level(self) -> None:
        def luminance(hex_color: str) -> int:
            return sum(int(hex_color[i : i + 2], 16) for i in (1, 3, 5))

        ramp = [luminance(plot_style.shade("#0072B2", n, 7)) for n in range(7)]
        assert ramp == sorted(ramp)
        assert len(set(ramp)) == 7

    def test_top_of_ramp_still_holds_contrast_against_white(self) -> None:
        """The cap exists so hue does not wash out; without it the ramp is unreadable."""
        top = plot_style.shade("#0072B2", 6, 7)
        assert max(int(top[i : i + 2], 16) for i in (1, 3, 5)) <= 235

    def test_non_hex_colour_passes_through_untouched(self) -> None:
        assert plot_style.shade("tab:blue", 3, 7) == "tab:blue"


class TestDashVocabulary:
    """Plotly understands five dash names; anything else prints as solid."""

    _LEGAL = {"solid", "dash", "dot", "dashdot", "longdash"}

    @pytest.mark.parametrize("level", range(len(plot_style.LEVEL_LINESTYLES)))
    def test_every_matplotlib_linestyle_maps_into_plotly(self, level: int) -> None:
        assert plot_style.to_plotly_dash(plot_style.linestyle_for(level)) in self._LEGAL

    @pytest.mark.parametrize("allowed", [True, False])
    def test_transition_dash_agrees_across_renderers(self, allowed: bool) -> None:
        matplotlib_style = plot_style.linestyle_for_transition(spin_allowed=allowed)
        assert plot_style.to_plotly_dash(matplotlib_style) == (
            plot_style.plotly_dash_for_transition(spin_allowed=allowed)
        )

    def test_allowed_and_forbidden_are_visually_different(self) -> None:
        assert plot_style.linestyle_for_transition(
            spin_allowed=True,
        ) != plot_style.linestyle_for_transition(spin_allowed=False)
        assert plot_style.plotly_dash_for_transition(
            spin_allowed=True,
        ) != plot_style.plotly_dash_for_transition(spin_allowed=False)


class TestDisplayLabelsAreUnique:
    """A figure label IS the identification, so two curves may never share one.

    Observed failure before `display_labels` existed: d6 renders two curves
    both named `³T₁g(H)` and two both named `¹T₂g(I)`, because one free-ion
    parent feeds the same irrep twice and `parent_suffix` only falls back to the
    ordinal when the PARENT is ambiguous -- a different situation.
    """

    @pytest.mark.parametrize("d_count", ALL_D)
    @pytest.mark.parametrize("renderer", ["ascii", "unicode", "latex", "plotly"])
    def test_no_two_levels_share_a_label(self, d_count: int, renderer: str) -> None:
        cfg = DEFAULTS[d_count]
        levels = LevelSet.solve(
            d_count,
            1500.0,
            float(cfg["default_B"]),
            float(cfg["default_C"]),
        )
        labels = levels.display_labels(renderer)
        assert len(labels) == levels.level_count
        assert len(set(labels.values())) == levels.level_count

    @pytest.mark.parametrize("d_count", [2, 3, 7, 8])
    def test_configurations_without_collisions_gain_no_notation(self, d_count: int) -> None:
        """The extra `,a` must appear only where it is earned."""
        cfg = DEFAULTS[d_count]
        levels = LevelSet.solve(
            d_count,
            1500.0,
            float(cfg["default_B"]),
            float(cfg["default_C"]),
        )
        labels = levels.display_labels("unicode")
        assert not [v for v in labels.values() if "," in v]
        for level in levels.levels:
            assert labels[level.uid] == level.parent_unicode

    @pytest.mark.parametrize("d_count", [4, 5, 6])
    def test_colliding_pairs_keep_their_parentage(self, d_count: int) -> None:
        """Disambiguation adds the ordinal; it must not DROP the free-ion parent."""
        cfg = DEFAULTS[d_count]
        levels = LevelSet.solve(
            d_count,
            1500.0,
            float(cfg["default_B"]),
            float(cfg["default_C"]),
        )
        labels = levels.display_labels("unicode")
        disambiguated = [v for v in labels.values() if "," in v]
        assert disambiguated, f"d{d_count} is expected to hold a parentage collision"
        for label in disambiguated:
            assert re.search(r"\([A-Z],[a-z]\)$", label), label

    def test_unknown_renderer_raises_rather_than_guessing(self) -> None:
        levels = LevelSet.solve(8, 1500.0, 1030.0, 4850.0)
        with pytest.raises(ValueError, match="unknown renderer"):
            levels.display_labels("svg")
