"""Which solver blocks have an ABSOLUTE oracle, and which only a relative one.

A mutation campaign against this suite found two survivors, and both share a
cause worth stating plainly:

  * perturbing d3 alone kills 3 tests; perturbing **d3 and d7 together** kills
    ZERO. Hole conjugation asserts d^n(+Dq) == d^(10-n)(-Dq) -- a *relative*
    invariant, structurally incapable of seeing a symmetric edit. That is
    exactly the edit a careful developer makes ("these are conjugates, change
    both").
  * a global constant perturbed 0.5% also survived: every level shifts, so
    every difference is preserved.

The lesson is not "write more invariants". A relative invariant can only catch
a bug that breaks the symmetry it asserts. What is needed is an inventory of
which blocks are pinned by an ABSOLUTE oracle -- a test that fixes a value, not
a relationship -- so the gaps are visible rather than merely absent.

ABSOLUTE oracles currently available, all in test_matrices_invariants.py:
  * ground state at exactly 0.0                     (every config)
  * Dq=0 free-ion Racah closed forms                (d2 fully; d5 quartets)
  * Dq=0 Racah free-ion table, values AND Oh irrep
    multiplicities                                  (d3, d4, d6, d7)
  * nu1 = 10Dq                                      (d3, d8)
  * 20B and 4B+3C gaps                              (d3)
  * 12B+2C gap                                      (d2, d8)

The d4/d6/d7 entry is what closed the gap this module was written to record.
TestFreeIonRacahClosedForms fixes every zero-field level of those manifolds
against Racah's published free-ion term energies -- an oracle with no contact
with this package, so a symmetric conjugate-pair edit and a shifted global
constant both have somewhere to show up.

This module does not add oracles. It makes the inventory executable, so a new
solver block cannot be added without a deliberate decision about how it will be
pinned. Adding a method and leaving it out of the inventory fails the test.
"""

from __future__ import annotations

import pytest

from tanabesugano import matrices


ALL_D = tuple(range(2, 9))


def state_methods(d_count: int) -> set[str]:
    """Every ligand-field block method on a solver -- the mutation targets."""
    return {m for m in dir(getattr(matrices, f"d{d_count}")) if m.endswith("_states")}


# Blocks pinned by an ABSOLUTE oracle: some test fixes a VALUE for them, so a
# numeric edit inside the block changes a hard-coded expectation.
ABSOLUTE_ORACLE: dict[int, set[str]] = {
    2: {"A_1_1_states", "E_1_states", "T_1_2_states", "T_3_1_states"},
    3: {"E_2_states", "T_2_1_states", "T_2_2_states", "T_4_1_states"},
    8: {"A_1_1_states", "E_1_states", "T_1_2_states", "T_3_1_states"},
}

# d5's QUARTET blocks are pinned by the Dq=0 free-ion closed forms
# (4G = 10B+5C, 4P = 7B+7C, 4D = 17B+5C, 4F = 22B+7C) in
# test_matrices_invariants.py::test_d5_quartet_free_ion_levels.
# d5 is pinned in full: racah_d5 covers all sixteen free-ion terms, doublets
# included, so every d5 block feeds a level with a fixed expected value.
ABSOLUTE_ORACLE[5] = state_methods(5)

# d3, d4, d6 and d7 are pinned block by block by
# test_matrices_invariants.py::TestFreeIonRacahClosedForms, which fixes every
# Dq=0 level against Racah's free-ion table. Each of these methods feeds the
# dict solver() returns, and that test walks the dict key by key, so a numeric
# edit anywhere inside one of them moves a level off its free-ion term.
for _d in (3, 4, 6, 7):
    ABSOLUTE_ORACLE[_d] = state_methods(_d)

# Blocks with only a RELATIVE guard (hole conjugation, ground-state-at-zero,
# ordering, continuity). A symmetric edit across a conjugate pair, or a global
# constant shift, is INVISIBLE to these. Documented, not accepted silently.
#
# What is left is exactly the d5 DOUBLET manifold. d5 is the one configuration
# whose free-ion table cannot be written as a list of linear-plus-square-root
# expressions: it carries 2D three times, so those three energies are the roots
# of a cubic. Pinning them needs the elementary symmetric functions of the
# triple rather than a closed form per level, which is a different oracle from
# the one TestFreeIonRacahClosedForms implements.
# Empty: every one of the 42 solver blocks now has an absolute-value oracle.
# Kept as a declared, typed mapping rather than deleted, so that a future block
# without a value oracle has an honest place to be recorded instead of being
# quietly omitted from the inventory.
RELATIVE_ONLY: dict[int, set[str]] = {}


class TestOracleInventoryIsComplete:
    """Every solver block must be classified. Adding one forces a decision."""

    @pytest.mark.parametrize("d_count", ALL_D)
    def test_every_block_is_classified(self, d_count: int) -> None:
        classified = ABSOLUTE_ORACLE.get(d_count, set()) | RELATIVE_ONLY.get(
            d_count,
            set(),
        )
        actual = state_methods(d_count)
        unclassified = actual - classified
        assert not unclassified, (
            f"d{d_count} has solver blocks with no recorded oracle class: "
            f"{sorted(unclassified)}. Add an absolute oracle for them in "
            "test_matrices_invariants.py and list them in ABSOLUTE_ORACLE, or "
            "record them in RELATIVE_ONLY to accept the gap explicitly."
        )

    @pytest.mark.parametrize("d_count", ALL_D)
    def test_inventory_names_no_phantom_blocks(self, d_count: int) -> None:
        """A rename must not leave a stale entry claiming coverage that is gone."""
        recorded = ABSOLUTE_ORACLE.get(d_count, set()) | RELATIVE_ONLY.get(
            d_count,
            set(),
        )
        phantom = recorded - state_methods(d_count)
        assert not phantom, f"d{d_count} inventory names missing methods: {sorted(phantom)}"


class TestKnownOracleGaps:
    """Pin the CURRENT gap so it cannot silently widen.

    These assertions are deliberately inverted: they assert that a gap EXISTS.
    Closing a gap fails the test, which is the point -- it forces the inventory
    above to be updated in the same commit, rather than the improvement being
    lost.
    """

    def test_no_block_lacks_an_absolute_oracle(self) -> None:
        """The gap is closed: all 42 blocks are pinned by value, not by relation.

        d4, d6 and d7 were once entirely unpinned, and d5's doublets outlasted
        them because 2D occurs three times there -- which turned out to be a
        quadratic PAIR plus a separate singleton 2D', not a cubic triple, so
        Racah's table covers them like any other term.

        If a new block is ever added without a value oracle, record it in
        RELATIVE_ONLY and invert this assertion in the same commit. Do not
        delete the test: an empty RELATIVE_ONLY is a claim worth defending.
        """
        assert RELATIVE_ONLY == {}, (
            f"blocks lost their absolute oracle: {RELATIVE_ONLY}. Either restore "
            "the oracle or record the gap here deliberately."
        )

    def test_every_one_of_the_forty_two_blocks_is_pinned(self) -> None:
        """Recorded as a count so coverage stays visible in the suite itself.

        It was 15 of 42 when this module was written -- the 27 unpinned were
        almost exactly the spin-forbidden manifolds, which is where the two
        surviving mutations lived. d3/d4/d6/d7 closed first, then d5.
        """
        pinned = sum(len(v) for v in ABSOLUTE_ORACLE.values())
        unpinned = sum(len(v) for v in RELATIVE_ONLY.values())
        total = sum(len(state_methods(d)) for d in ALL_D)
        assert (pinned, unpinned, total) == (42, 0, 42), (
            f"oracle coverage moved to {pinned} absolute / {unpinned} relative-only "
            f"of {total}; update this assertion and the inventory together."
        )
