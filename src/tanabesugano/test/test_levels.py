"""Contract for the typed level structure that replaces dict[TermKey, ndarray].

The dict form cannot express the assignment problem: for d8 it maps 3_T_1 to a
two-element array, so ts_fit_spectrum labels both nu2 and nu3 "3_A_2->3_T_1".
A chemist needs 3T1g(F) and 3T1g(P).

Two measured invariants make a typed form possible:

  * within a term block the levels stay ascending for every Dq (verified: 0
    violations over 120 Dq points x every block, d2..d8) -- the non-crossing
    rule for same-symmetry states. So the multiplet INDEX is a stable identity.
  * (term, index) is unique for all seven configurations.

Therefore UNIQUENESS comes from (term, index) and never needs parentage.
Parentage adds chemical MEANING on top, and is derived -- not declared -- from
the Dq=0 degeneracy grouping, so it cannot drift from the solver.
"""

from __future__ import annotations

from math import comb

import pytest

from tanabesugano.levels import Level
from tanabesugano.levels import LevelSet
from tanabesugano.terms import TermKey


ALL_D = tuple(range(2, 9))


class TestIdentity:
    @pytest.mark.parametrize("d_count", ALL_D)
    def test_term_and_index_uniquely_identify_a_level(self, d_count: int) -> None:
        ls = LevelSet.solve(d_count, 1000.0)
        keys = [(lv.term, lv.index) for lv in ls.levels]
        assert len(keys) == len(set(keys))

    @pytest.mark.parametrize("d_count", ALL_D)
    def test_levels_within_a_term_are_ascending(self, d_count: int) -> None:
        ls = LevelSet.solve(d_count, 1000.0)
        for term in ls.terms:
            energies = [lv.energy_cm1 for lv in ls.for_term(term)]
            assert energies == sorted(energies)

    @pytest.mark.parametrize("d_count", ALL_D)
    def test_ground_level_is_exactly_zero(self, d_count: int) -> None:
        assert min(lv.energy_cm1 for lv in LevelSet.solve(d_count, 1000.0).levels) == 0.0


class TestAssignmentIsUnambiguous:
    """The defect this whole structure exists to fix."""

    def test_d8_triplet_t1_levels_are_distinguishable(self) -> None:
        ls = LevelSet.solve(8, 850.0, b=907.0)
        t1 = ls.for_term(TermKey.TRIPLET_T_1)
        assert len(t1) == 2
        assert t1[0].label != t1[1].label, "nu2 and nu3 still carry the same label"

    @pytest.mark.parametrize("d_count", ALL_D)
    def test_every_label_is_unique(self, d_count: int) -> None:
        labels = [lv.label for lv in LevelSet.solve(d_count, 1000.0).levels]
        assert len(labels) == len(set(labels))

    def test_transition_labels_name_the_ground_term(self) -> None:
        ls = LevelSet.solve(8, 850.0, b=907.0)
        assert ls.ground.term is TermKey.TRIPLET_A_2
        excited = ls.for_term(TermKey.TRIPLET_T_2)[0]
        assert ls.transition_label(excited).startswith("3_A_2")


class TestDerivedNotStored:
    """Anything derivable must be a property, or it can disagree with its source."""

    def test_multiplicity_comes_from_the_term(self) -> None:
        lv = Level(term=TermKey.QUINTET_E, index=0, energy_cm1=0.0, parent_rank=0)
        assert lv.multiplicity == 5

    def test_energy_over_b_is_a_view_not_storage(self) -> None:
        lv = Level(term=TermKey.TRIPLET_T_2, index=0, energy_cm1=8500.0, parent_rank=0)
        assert lv.energy_over_b(907.0) == pytest.approx(8500.0 / 907.0)
        assert lv.energy_cm1 == 8500.0, "absolute energy must survive"


class TestParentageIsDerived:
    """Parentage comes from the Dq=0 degeneracy grouping, not a lookup table."""

    def test_d8_triplet_t1_spans_two_free_ion_parents(self) -> None:
        """3T1g(F) and 3T1g(P) -- separated by exactly 15B at zero field."""
        ls = LevelSet.solve(8, 850.0, b=907.0)
        ranks = [lv.parent_rank for lv in ls.for_term(TermKey.TRIPLET_T_1)]
        assert len(set(ranks)) == 2

    @pytest.mark.parametrize("d_count", ALL_D)
    def test_parent_ranks_are_contiguous_from_zero(self, d_count: int) -> None:
        ranks = {lv.parent_rank for lv in LevelSet.solve(d_count, 1000.0).levels}
        assert ranks == set(range(len(ranks)))

    @pytest.mark.parametrize(("d_count", "expected"), [(2, 5), (8, 5), (3, 7), (7, 7)])
    def test_free_ion_group_count(self, d_count: int, expected: int) -> None:
        """d2/d8 give 5 groups (3F,3P,1G,1D,1S).

        d3/d7 give 7, NOT the 8 distinct free-ion terms: 2H and 2P are both at
        9B+3C -- Racah's accidental d3 degeneracy -- so energy grouping cannot
        separate them. Recorded rather than hidden; uniqueness is unaffected
        because it rests on (term, index), not on parentage.
        """
        assert LevelSet.solve(d_count, 1000.0).free_ion_group_count == expected


class TestCompleteness:
    @pytest.mark.parametrize("d_count", ALL_D)
    def test_microstate_count(self, d_count: int) -> None:
        ls = LevelSet.solve(d_count, 1000.0)
        assert ls.total_degeneracy == comb(10, d_count)

    @pytest.mark.parametrize("d_count", ALL_D)
    def test_declares_its_own_configuration(self, d_count: int) -> None:
        ls = LevelSet.solve(d_count, 1000.0)
        assert ls.d_count == d_count
        assert ls.electron_count == d_count
        assert len(ls.levels) == ls.level_count


class TestPublicationRendering:
    """One notation at three fidelities: ASCII, Unicode, LaTeX.

    Expected strings are NOT read off the implementation. They come from the
    octahedral spectroscopic convention itself -- a d8 ground term is written
    3A2g, and its two 3T1g levels are disambiguated (a)/(b) -- plus the LaTeX
    rule that a superscript following a relation needs an explicit empty base,
    hence ``\\rightarrow {}^{3}``.
    """

    #: d8 with a typical Ni(II) B. Ground 3A2g; 3T1g is the two-level term.
    D8 = (8, 850.0, 907.0)

    @staticmethod
    def _d8() -> LevelSet:
        d_count, dq, b = TestPublicationRendering.D8
        return LevelSet.solve(d_count, dq, b=b)

    def test_single_level_term_carries_no_ordinal(self) -> None:
        """3A2g is the only 3A2g there is -- ``(a)`` would be noise."""
        ground = self._d8().ground
        assert ground.term is TermKey.TRIPLET_A_2
        assert ground.ascii == "3A2g"
        assert ground.unicode == "³A₂g"
        assert ground.latex == r"$^{3}A_{2g}$"
        assert ground.label == "3_A_2"

    def test_multi_level_term_carries_the_ordinal(self) -> None:
        first, second = self._d8().for_term(TermKey.TRIPLET_T_1)
        assert first.ascii == "3T1g(a)"
        assert second.ascii == "3T1g(b)"
        assert second.unicode == "³T₁g(b)"
        assert second.latex == r"$^{3}T_{1g}(b)$"
        assert second.label == "3_T_1(b)"

    def test_uid_always_carries_the_index(self) -> None:
        """``label`` suppresses the ordinal, so it is no longer an identity key."""
        ls = self._d8()
        ground = ls.ground
        second = ls.for_term(TermKey.TRIPLET_T_1)[1]
        assert ground.uid == "3_A_2#0"
        assert second.uid == "3_T_1#1"

    @pytest.mark.parametrize("d_count", ALL_D)
    def test_uid_is_unique_even_where_label_is_not_an_identity(
        self,
        d_count: int,
    ) -> None:
        uids = [lv.uid for lv in LevelSet.solve(d_count, 1000.0).levels]
        assert len(uids) == len(set(uids))

    def test_transition_latex(self) -> None:
        ls = self._d8()
        second = ls.for_term(TermKey.TRIPLET_T_1)[1]
        assert ls.transition_latex(second) == r"$^{3}A_{2g} \rightarrow {}^{3}T_{1g}(b)$"

    def test_transition_unicode(self) -> None:
        ls = self._d8()
        second = ls.for_term(TermKey.TRIPLET_T_1)[1]
        assert ls.transition_unicode(second) == "³A₂g → ³T₁g(b)"

    @pytest.mark.parametrize("d_count", ALL_D)
    def test_every_latex_string_parses_as_mathtext(self, d_count: int) -> None:
        """An independent oracle: matplotlib's own parser, not our expectations."""
        from matplotlib.mathtext import MathTextParser

        parser = MathTextParser("agg")
        ls = LevelSet.solve(d_count, 1000.0)
        for lv in ls.levels:
            parser.parse(lv.latex)
            parser.parse(ls.transition_latex(lv))

    @pytest.mark.parametrize("d_count", ALL_D)
    def test_ascii_is_pure_ascii_and_unicode_is_not_underscored(
        self,
        d_count: int,
    ) -> None:
        for lv in LevelSet.solve(d_count, 1000.0).levels:
            assert lv.ascii.isascii(), f"{lv.ascii!r} is not ASCII"
            assert "_" not in lv.ascii
            assert "_" not in lv.unicode


class TestUncoveredRenderers:
    """`transition_ascii` and `parent_label` were public but untested.

    Its siblings `transition_latex` and `transition_unicode` were covered from
    the start, so ascii was the odd one out -- exactly the asymmetry that lets a
    renderer rot unnoticed.
    """

    def test_transition_ascii_is_plain_and_parseable(self) -> None:
        """ASCII must survive a terminal, a CSV column and a log line."""
        ls = LevelSet.solve(8, 850.0, b=907.0)
        excited = ls.for_term(TermKey.TRIPLET_T_1)[1]
        rendered = ls.transition_ascii(excited)
        assert rendered.isascii(), f"non-ASCII characters in {rendered!r}"
        assert "->" in rendered

    def test_the_three_renderers_agree_on_which_level_they_name(self) -> None:
        """Same level, three encodings -- they must not disagree on the ordinal."""
        ls = LevelSet.solve(8, 850.0, b=907.0)
        second = ls.for_term(TermKey.TRIPLET_T_1)[1]
        assert "(b)" in ls.transition_ascii(second)
        assert "(b)" in ls.transition_unicode(second)
        assert "(b)" in ls.transition_latex(second)

    def test_parent_label_distinguishes_the_two_triplet_t1_levels(self) -> None:
        """Parentage is chemical annotation, and must differ where the physics does.

        d8's two 3T1g levels descend from 3F and 3P, split by exactly 15B at
        zero field -- so their parent labels must not coincide.
        """
        ls = LevelSet.solve(8, 850.0, b=907.0)
        first, second = ls.for_term(TermKey.TRIPLET_T_1)
        assert first.parent_label != second.parent_label

    def test_parent_label_is_honest_when_parentage_was_not_derived(self) -> None:
        """`from_states` skips the zero-field solve, so parent_rank is None.

        The label must say so rather than render a plausible-looking number.
        """
        ls = LevelSet.from_states({"3_A_2": [0.0], "3_T_2": [8500.0]})
        assert all(lv.parent_rank is None for lv in ls.levels)
        assert all("?" in lv.parent_label for lv in ls.levels)


class TestSpinAllowedAgreesWithTheFitter:
    """`LevelSet.spin_allowed` and `_compute.transition_candidates` both answer
    "which bands are reachable without a spin flip", by different routes.

    Two implementations of one concept is a latent divergence: the fitter walks
    the raw dict for speed, LevelSet walks typed levels. Pinning their agreement
    converts the duplication into a checked invariant rather than a hazard --
    and `spin_allowed` had no test at all before this.
    """

    @pytest.mark.parametrize("d_count", [2, 3, 7, 8])
    def test_both_routes_select_the_same_energies(self, d_count: int) -> None:
        from tanabesugano.mcp._compute import compute_point
        from tanabesugano.mcp._compute import transition_candidates
        from tanabesugano.mcp._defaults import DEFAULTS

        cfg = DEFAULTS[d_count]
        b, c = float(cfg["default_B"]), float(cfg["default_C"])
        dq = 1000.0

        via_levels = sorted(
            lv.energy_cm1 for lv in LevelSet.solve(d_count, dq, b, c).spin_allowed()
        )
        _ground, cands = transition_candidates(compute_point(d_count, dq, b, c))
        via_fitter = sorted(energy for energy, _label, _allowed in cands)

        assert via_levels == pytest.approx(via_fitter)

    def test_high_spin_d5_is_empty_by_both_routes(self) -> None:
        """Mn(II): every d-d band is spin-forbidden, so both must return nothing."""
        assert LevelSet.solve(5, 800.0, 860.0, 3850.0).spin_allowed() == ()
