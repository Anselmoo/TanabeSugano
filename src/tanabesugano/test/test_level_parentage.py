"""Free-ion parentage labels on Level: 3T_1g(F) rather than 3T_1g(b).

The (a)/(b) ordinal is positional -- it says "second level of this term block"
and carries no chemistry. The literature labels the same levels by the free-ion
term they descend from, and a generated figure whose axis reads (b) will not
match a caption that reads (P).

Provenance: every expected value here comes from Racah's free-ion table via
group theory, not from running the labeller. The d8 case is fixed by an
identity the package cannot influence -- E(3P) - E(3F) = 15B exactly at zero
field -- which is already asserted independently in test_matrices_invariants.py.
"""

from __future__ import annotations

import math

import pytest

from tanabesugano.levels import LevelSet


B_REF, C_REF = 1000.0, 4000.0


class TestUnambiguousParentage:
    """d2/d8: every level has exactly one possible free-ion parent."""

    @pytest.mark.parametrize("d_count", [2, 8])
    def test_the_two_triplet_t1_levels_are_3f_and_3p(self, d_count: int) -> None:
        """The headline case, and the one Figure 6 depends on.

        Provenance: at zero field 3F is the ground term and 3P sits at exactly
        15B above it (test_matrices_invariants.py::test_3p_minus_3f_is_15b).
        F reduces to A_2 + T_1 + T_2 and P reduces to T_1 alone, so the lower
        3T_1 must be 3F's and the upper must be 3P's. Neither statement comes
        from this labeller.
        """
        manifold = LevelSet.solve(d_count, dq=800.0, b=B_REF, c=C_REF)
        t1 = sorted(
            (lv for lv in manifold.levels if lv.term.value == "3_T_1"),
            key=lambda lv: lv.energy_cm1,
        )
        assert len(t1) == 2
        assert [lv.parent_symbol for lv in t1] == ["3F", "3P"]

    @pytest.mark.parametrize("d_count", [2, 8])
    def test_parentage_labels_replace_the_positional_ordinal(self, d_count: int) -> None:
        """3T_1g(F) / 3T_1g(P), not 3T_1g(a) / 3T_1g(b)."""
        manifold = LevelSet.solve(d_count, dq=800.0, b=B_REF, c=C_REF)
        t1 = sorted(
            (lv for lv in manifold.levels if lv.term.value == "3_T_1"),
            key=lambda lv: lv.energy_cm1,
        )
        assert [lv.parent_label_display for lv in t1] == ["3_T_1(F)", "3_T_1(P)"]
        assert t1[1].parent_latex == r"$^{3}T_{1g}(P)$"

    @pytest.mark.parametrize("d_count", [2, 8])
    def test_single_level_terms_suppress_the_parent_suffix(self, d_count: int) -> None:
        """3A_2g, not 3A_2g(F) -- matching how Level.label suppresses (a).

        A term holding one level needs no disambiguator, and the literature
        prints it plain. This mirrors the existing rule for the ordinal, so the
        two label styles stay consistent.
        """
        manifold = LevelSet.solve(d_count, dq=800.0, b=B_REF, c=C_REF)
        a2 = next(lv for lv in manifold.levels if lv.term.value == "3_A_2")
        assert a2.multiplet_size == 1
        assert a2.parent_label_display == "3_A_2"

    @pytest.mark.parametrize("d_count", [2, 8])
    def test_every_level_resolves_to_exactly_one_parent(self, d_count: int) -> None:
        """d2/d8 have no accidental degeneracies, so nothing may be ambiguous."""
        manifold = LevelSet.solve(d_count, dq=700.0, b=B_REF, c=C_REF)
        unresolved = [lv.uid for lv in manifold.levels if lv.parent_symbol is None]
        assert not unresolved, f"d{d_count} left {unresolved} without a unique parent"


class TestAmbiguityIsReported:
    """d3/d7: 2H and 2P coincide at 9B+3C, so some levels genuinely cannot be named."""

    @pytest.mark.parametrize("d_count", [3, 7])
    def test_doublet_t1_levels_in_the_2h_2p_group_are_ambiguous(self, d_count: int) -> None:
        """Provenance: Racah puts 2H and 2P both at 9B + 3C for every (B, C).
        2H reduces to E + 2T_1 + T_2 and 2P to T_1, so that energy carries three
        T_1 levels -- two from 2H, one from 2P -- and energy cannot say which.
        The labeller must return None rather than guess.
        """
        manifold = LevelSet.solve(d_count, dq=900.0, b=B_REF, c=C_REF)
        target = 9 * B_REF + 3 * C_REF
        zero_field = LevelSet.solve(d_count, dq=0.0, b=B_REF, c=C_REF)
        degenerate_t1 = [
            lv
            for lv in zero_field.levels
            if lv.term.value == "2_T_1" and abs(lv.energy_cm1 - target) < 1e-6
        ]
        assert len(degenerate_t1) == 3, "expected 2H's two T_1 plus 2P's one"
        assert all(lv.parent_symbol is None for lv in degenerate_t1)
        assert all(set(lv.parent_candidates) == {"2H", "2P"} for lv in degenerate_t1), (
            "both candidates must be reported, not silently dropped"
        )
        assert manifold.levels  # the field-on manifold still solves

    @pytest.mark.parametrize("d_count", [3, 7])
    def test_irrep_filtering_resolves_what_energy_alone_cannot(self, d_count: int) -> None:
        """2E and 2T_2 at 9B+3C are unambiguously 2H, because 2P reduces to T_1 only.

        This is the payoff of matching on irrep as well as energy: a purely
        energy-based match would have called all five levels ambiguous.
        """
        zero_field = LevelSet.solve(d_count, dq=0.0, b=B_REF, c=C_REF)
        target = 9 * B_REF + 3 * C_REF
        resolved = [
            lv
            for lv in zero_field.levels
            if lv.term.value in {"2_E", "2_T_2"} and abs(lv.energy_cm1 - target) < 1e-6
        ]
        assert resolved, "expected 2H's E and T_2 levels at this energy"
        assert all(lv.parent_symbol == "2H" for lv in resolved)

    @pytest.mark.parametrize("d_count", [3, 7])
    def test_ambiguous_levels_fall_back_to_the_positional_ordinal(self, d_count: int) -> None:
        """A label must always be printable. When the parent is unknown the
        display falls back to (a)/(b) rather than emitting an empty or
        plausible-but-wrong suffix.
        """
        zero_field = LevelSet.solve(d_count, dq=0.0, b=B_REF, c=C_REF)
        ambiguous = [lv for lv in zero_field.levels if lv.parent_symbol is None]
        assert ambiguous
        for lv in ambiguous:
            assert lv.parent_label_display == lv.label


class TestParentageIsCompleteAcrossTheManifold:
    """Whole-manifold arithmetic, not spot checks."""

    @pytest.mark.parametrize("d_count", [2, 3, 4, 5, 6, 7, 8])
    def test_every_level_has_at_least_one_candidate(self, d_count: int) -> None:
        """A level with no candidate parent means the table missed a term."""
        manifold = LevelSet.solve(d_count, dq=0.0, b=B_REF, c=C_REF)
        orphans = [lv.uid for lv in manifold.levels if not lv.parent_candidates]
        assert not orphans, f"d{d_count}: levels descending from no free-ion term: {orphans}"

    @pytest.mark.parametrize("d_count", [2, 3, 4, 5, 6, 7, 8])
    def test_degeneracy_still_sums_to_the_microstate_count(self, d_count: int) -> None:
        """C(10, n) once more -- parentage must not have dropped or added a level."""
        manifold = LevelSet.solve(d_count, dq=650.0, b=B_REF, c=C_REF)
        assert sum(lv.degeneracy for lv in manifold.levels) == math.comb(10, d_count)

    @pytest.mark.parametrize("d_count", [2, 3, 4, 5, 6, 7, 8])
    def test_parentage_is_independent_of_dq(self, d_count: int) -> None:
        """Parentage is a zero-field property; turning the field on cannot change it.

        Levels of one symmetry do not cross, so the same (term, index) must
        carry the same parent at every Dq.
        """
        weak = {
            lv.uid: lv.parent_symbol for lv in LevelSet.solve(d_count, 50.0, B_REF, C_REF).levels
        }
        strong = {
            lv.uid: lv.parent_symbol for lv in LevelSet.solve(d_count, 2500.0, B_REF, C_REF).levels
        }
        assert weak == strong


class TestForTermAcceptsStringKeys:
    """`for_term("3_T_1")` must not silently return nothing.

    TermKey is a StrEnum precisely so it *is* a str at every boundary
    (CLAUDE.md). But `for_term` compared with `is`, which is False for a plain
    string even though `==` is True — so a caller passing the documented string
    spelling got an empty tuple and no error. That is the same silent-empty
    failure mode as `_multiplicity_of` returning 0 for an unparsable term,
    which disabled spin-allowed filtering across four tools.

    Observed failure before the fix::

        for_term("3_T_1") -> ()          # expected two levels
        for_term(TermKey.TRIPLET_T_1) -> (3_T_1#0, 3_T_1#1)
    """

    def test_string_and_enum_keys_agree(self) -> None:
        from tanabesugano.terms import TermKey

        manifold = LevelSet.solve(8, dq=850.0, b=1030.0, c=4850.0)
        by_str = manifold.for_term("3_T_1")
        by_enum = manifold.for_term(TermKey.TRIPLET_T_1)
        assert by_enum, "fixture precondition: d8 has two 3_T_1 levels"
        assert by_str == by_enum

    def test_d8_has_exactly_two_triplet_t1_levels(self) -> None:
        """Provenance: 3F reduces to A_2+T_1+T_2 and 3P to T_1, so exactly two
        3T_1 levels exist — group theory, not a value read off the solver.
        """
        manifold = LevelSet.solve(8, dq=850.0, b=1030.0, c=4850.0)
        assert len(manifold.for_term("3_T_1")) == 2

    def test_an_unknown_term_still_returns_empty(self) -> None:
        """d8 has no quintets; absence must stay absence, not raise."""
        assert LevelSet.solve(8, dq=850.0, b=1030.0, c=4850.0).for_term("5_E") == ()
