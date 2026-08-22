"""One decision about how a level is drawn, read by four renderers.

Before `figure_style` existed each surface decided for itself and all four
disagreed. The contract tested here is not "a colour comes back" but "the same
level gets the same treatment everywhere, and a column name resolves to the
level it actually names".

The column-name half is a real regression guard, not a formality. `cmd._split`
resolved a column by splitting on the last underscore, and EVERY A and T term
key already ends in a digit -- so `"3_A_1"` split into `("3_A", 1)`,
`color_for("3_A")` matched no term, and every single-level A/T curve was drawn
in the fallback grey `#444444` instead of its multiplicity colour. Observed
before the fix:

    3_A_1  -> _split gives 3_A  -> #444444   (correct: #0072B2)
    1_A_2  -> _split gives 1_A  -> #444444   (correct: #999999)
    5_T_2  -> _split gives 5_T  -> #444444   (correct: #D55E00)

Splitting is only decidable against `TermKey` membership, which is what
`column_to_uid` does.
"""

from __future__ import annotations

from itertools import pairwise

import pytest

from tanabesugano import plot_style
from tanabesugano.figure_style import column_to_uid
from tanabesugano.figure_style import series_styles
from tanabesugano.levels import LevelSet
from tanabesugano.mcp._defaults import DEFAULTS
from tanabesugano.terms import TermKey


ALL_D = tuple(range(2, 9))


def _styles(d_count: int, dq: float = 1500.0):
    cfg = DEFAULTS[d_count]
    return series_styles(d_count, dq, float(cfg["default_B"]), float(cfg["default_C"]))


class TestColumnToUid:
    """CSV column names must resolve to the level they name."""

    @pytest.mark.parametrize(
        ("column", "expected"),
        [
            ("3_T_1_0", "3_T_1#0"),
            ("3_T_1_6", "3_T_1#6"),
            ("1_E_3", "1_E#3"),
            # Single-level terms: the whole key IS the term, digit and all.
            ("3_A_1", "3_A_1#0"),
            ("1_A_2", "1_A_2#0"),
            ("5_T_2", "5_T_2#0"),
            ("5_E", "5_E#0"),
        ],
    )
    def test_resolves_against_termkey_not_the_last_underscore(
        self,
        column: str,
        expected: str,
    ) -> None:
        assert column_to_uid(column) == expected

    @pytest.mark.parametrize("term", list(TermKey), ids=lambda t: t.value)
    def test_every_bare_term_key_is_level_zero_of_itself(self, term: TermKey) -> None:
        """The exact case the last-underscore split got wrong, over the closed set."""
        assert column_to_uid(term.value) == f"{term.value}#0"

    @pytest.mark.parametrize("d_count", ALL_D)
    def test_every_real_column_resolves_to_a_real_level(self, d_count: int) -> None:
        """Round-trip against the CLI's own column names, not invented ones."""
        from tanabesugano.batch import ELECTRON_CONFIG_SOLVERS
        from tanabesugano.cmd import CMDmain

        cfg = DEFAULTS[d_count]
        b, c = float(cfg["default_B"]), float(cfg["default_C"])
        states = ELECTRON_CONFIG_SOLVERS[d_count](Dq=150.0, B=b, C=c).solver().as_dict()
        columns = CMDmain.subsplit_states(states)

        styles = series_styles(d_count, 1500.0, b, c)
        unresolved = [col for col in columns if column_to_uid(col) not in styles]
        assert not unresolved

    @pytest.mark.parametrize("d_count", ALL_D)
    def test_no_column_lands_on_the_fallback_colour(self, d_count: int) -> None:
        """The regression this module exists for: grey means 'term not recognised'."""
        for style in _styles(d_count).values():
            assert style.base_color != "#444444"
            assert style.base_color == plot_style.SPIN_COLORS[style.multiplicity]


class TestEncodingIsCoherent:
    """Hue, lightness and dash each have to carry exactly one thing."""

    @pytest.mark.parametrize("d_count", ALL_D)
    def test_exactly_one_ground_level(self, d_count: int) -> None:
        """Ground is a LEVEL, not a term.

        Low-spin d6 has `1_A_1` as ground term and that term holds five levels;
        emphasising the term would draw five thick curves and anchor nothing.
        """
        assert sum(s.is_ground for s in _styles(d_count).values()) == 1

    @pytest.mark.parametrize("d_count", ALL_D)
    def test_matplotlib_and_plotly_agree_on_every_level(self, d_count: int) -> None:
        """The two renderers may differ in alphabet, never in decision."""
        for style in _styles(d_count).values():
            assert style.dash == plot_style.to_plotly_dash(style.linestyle)
            assert style.matplotlib_kwargs()["color"] == style.color

    @pytest.mark.parametrize("d_count", ALL_D)
    def test_hue_is_multiplicity_alone(self, d_count: int) -> None:
        """Two levels of different multiplicity may never share a base hue."""
        by_mult: dict[int, set[str]] = {}
        for style in _styles(d_count).values():
            by_mult.setdefault(style.multiplicity, set()).add(style.base_color)
        assert all(len(colors) == 1 for colors in by_mult.values())
        hues = [next(iter(c)) for c in by_mult.values()]
        assert len(hues) == len(set(hues))

    def test_d5_high_spin_is_entirely_forbidden(self) -> None:
        """Mn(II) is pale because every d-d band is spin-forbidden.

        The clearest check that dash tracks physics rather than an ordinal.
        """
        styles = series_styles(5, 800.0, 860.0, 3850.0)
        solid = [s for s in styles.values() if s.dash == "solid"]
        assert [s.uid for s in solid] == [s.uid for s in styles.values() if s.is_ground]

    def test_d3_solid_curves_are_exactly_the_three_observable_bands(self) -> None:
        """Cr(III): 4A2g -> 4T2g, 4T1g(F), 4T1g(P), and nothing else."""
        styles = series_styles(3, 400.0, 918.0, 4132.0)
        excited = sorted(
            s.label_unicode for s in styles.values() if s.dash == "solid" and not s.is_ground
        )
        assert excited == ["⁴T₁g(F)", "⁴T₁g(P)", "⁴T₂g"]


class TestSpreadLabels:
    """Direct labels are useless if they land on top of each other."""

    def test_order_is_never_swapped(self) -> None:
        """A label must stay nearest the curve it names, or the leader lies."""
        positions = [1.0, 1.05, 1.1, 8.0, 8.01]
        out = plot_style.spread_labels(positions, span=(0.0, 10.0), pitch=1.0)
        assert sorted(range(len(out)), key=lambda i: out[i]) == sorted(
            range(len(positions)),
            key=lambda i: positions[i],
        )

    def test_every_gap_reaches_the_pitch(self) -> None:
        positions = [5.0] * 6
        out = sorted(plot_style.spread_labels(positions, span=(0.0, 20.0), pitch=1.0))
        assert all(b - a >= 1.0 - 1e-9 for a, b in pairwise(out))

    def test_a_full_stack_is_pushed_back_inside_the_span(self) -> None:
        """Without the downward pass the top of a dense cluster escapes the axes."""
        positions = [9.5] * 8
        out = plot_style.spread_labels(positions, span=(0.0, 10.0), pitch=1.0)
        assert max(out) <= 10.0 + 1e-9
        assert min(out) >= 0.0 - 1e-9

    def test_empty_input_is_not_an_error(self) -> None:
        assert plot_style.spread_labels([], span=(0.0, 1.0), pitch=0.1) == []


class TestEveryLevelIsLabelled:
    """The defect that started this: dashed curves with no names.

    `render_diagram` passed `label=... if n == 0 else None`, so the legend
    carried one entry per TERM and every second-and-later level of a multiplet
    was drawn anonymously. For d6 that is 43 curves sharing 12 names.

    Asserted against the figure rather than the encoded bytes -- which is why
    `build_diagram` was split out of `render_diagram`. A claim about labels
    that can only be checked by rasterising and reading pixels is a claim
    nothing checks, which is how this survived.
    """

    @pytest.mark.parametrize("d_count", ALL_D)
    def test_one_curve_and_one_label_per_level(self, d_count: int) -> None:
        import matplotlib.pyplot as plt

        from tanabesugano.mcp.plotting import build_diagram

        cfg = DEFAULTS[d_count]
        b, c = float(cfg["default_B"]), float(cfg["default_C"])
        expected = LevelSet.solve(d_count, 1500.0, b, c).level_count

        fig = build_diagram(d_count, 0.0, 1500.0, 12, b, c)
        try:
            ax = fig.axes[0]
            assert len(ax.lines) == expected
            labels = [text.get_text() for text in ax.texts]
            assert len(labels) == expected
            assert len(set(labels)) == expected
        finally:
            plt.close(fig)

    def test_labels_carry_parentage_not_the_positional_ordinal(self) -> None:
        """`(a)`/`(b)` is this package's internal spelling; `(F)`/`(P)` is the literature's."""
        import matplotlib.pyplot as plt

        from tanabesugano.mcp.plotting import build_diagram

        fig = build_diagram(8, 0.0, 1500.0, 12, 1030.0, 4850.0)
        try:
            labels = {text.get_text() for text in fig.axes[0].texts}
        finally:
            plt.close(fig)
        assert "$^{3}T_{1g}(F)$" in labels
        assert "$^{3}T_{1g}(P)$" in labels
        assert not [x for x in labels if x.endswith(("(a)$", "(b)$"))]


class TestOneColourStandard:
    """No surface may carry its own palette.

    Two copies of the multiplicity table lived in `mcp/apps.py`, both shifted by
    one multiplicity against `plot_style.SPIN_COLORS`, and the React app carried
    a third. `scripts/plot_uvvis_fits.py` and `script_export.py` each declared
    an `OBSERVED_COLOR`, and they disagreed: vermillion in one, blue in the
    other, for figures a reader compares side by side.

    A literal `"#rrggbb"` anywhere but `plot_style` is how every one of those
    started, so that is what this checks.
    """

    _SOURCE_ROOTS = ("src/tanabesugano", "scripts")

    def _python_sources(self):
        from pathlib import Path

        root = Path(__file__).parents[3]
        for source_root in self._SOURCE_ROOTS:
            for path in sorted((root / source_root).rglob("*.py")):
                if path.name == "plot_style.py" or "/test/" in path.as_posix():
                    continue
                yield path

    def test_no_module_spells_a_colour_itself(self) -> None:
        import re

        pattern = re.compile(r'"#[0-9A-Fa-f]{6}"')
        offenders = {
            path.name: sorted(set(pattern.findall(path.read_text(encoding="utf-8"))))
            for path in self._python_sources()
            if pattern.search(path.read_text(encoding="utf-8"))
        }
        assert not offenders

    def test_annotation_roles_never_collide_with_a_term_hue_by_accident(self) -> None:
        """Reuse is allowed, but only where it is written down as deliberate."""
        shared = set(plot_style.ANNOTATION_COLORS.values()) & set(
            plot_style.SPIN_COLORS.values(),
        )
        # Documented in ANNOTATION_COLORS' docstring: annotation marks never
        # share an axes with term curves, so the palette stays colour-blind safe
        # rather than inventing new hues.
        assert shared <= {"#D55E00", "#0072B2", "#009E73"}

    def test_observed_means_one_colour_everywhere(self) -> None:
        """The single association a reader carries between figure surfaces."""
        from tanabesugano import script_export

        source = script_export.fit_figure_script.__globals__["__file__"]
        text = __import__("pathlib").Path(source).read_text(encoding="utf-8")
        assert 'ANNOTATION_COLORS["observed"]' in text
        assert plot_style.ANNOTATION_COLORS["observed"] == "#D55E00"
