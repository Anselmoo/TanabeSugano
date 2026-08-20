"""Typed term-symbol vocabulary for octahedral ligand-field calculations.

Two vocabularies circulate in this package and are easy to confuse:

* **Octahedral term keys** -- ``3_T_1``, ``5_E`` -- produced by the ``dN.solver()``
  methods and used everywhere downstream. Closed set of 23 across d2..d8.
* **Free-ion term symbols** -- ``3F``, ``6S`` -- human-facing spectroscopic
  notation stored in ``DEFAULTS[d]["ground_term"]``.

They were both plain ``str``. A parser handed the wrong one returned ``0``
instead of raising, which silently disabled spin-allowed filtering across four
tools; and because the term regex was permissive, ``1_T_3`` (no T3 irrep exists
in Oh) and ``5_E_1`` (Eg carries no subscript) survived for the life of the
project. Typing them as two distinct closed enums makes both classes of mistake
impossible to write.

``TermKey`` is a :class:`enum.StrEnum`, so it *is* a ``str``: ``json.dumps``,
pydantic, f-strings, ``.split("_")`` and ``== "3_T_1"`` all work unchanged. No
adapter code is needed at any boundary, and no static type checker is required
for the main benefit -- a mistyped member is an ``AttributeError`` at the point
of use.

This module is stdlib-only by design: ``matrices.py`` and ``plot_style.py`` are
core CLI code and must not depend on pydantic, which ships in the optional
``[mcp]`` extra.
"""

from __future__ import annotations

import re

from enum import StrEnum


class Irrep(StrEnum):
    """Mulliken symbols that occur in the octahedral d^n term manifolds."""

    A = "A"
    E = "E"
    T = "T"


class FreeIonTerm(StrEnum):
    """Free-ion orbital term letters (the L part of a ``2S+1 L`` symbol).

    Deliberately a different type from :class:`TermKey`: passing one where the
    other is expected is the bug that disabled spin-allowed filtering in
    ``ts_reverse_fit_app``, ``ts_ratio_fit_app``, ``ts_spectrum_app`` and the
    reverse-fit table column.

    Runs S..I because the d-shell reaches L = 6: d5 carries a 2I term and
    d4/d6 carry 1I. Stopping at F (as this enum first did) would have made the
    free-ion tables in :mod:`tanabesugano.free_ion` unwritable.
    """

    S = "S"
    P = "P"
    D = "D"
    F = "F"
    G = "G"
    H = "H"
    I = "I"  # noqa: E741 - the spectroscopic letter, not an ambiguous variable name

    @property
    def orbital_L(self) -> int:
        """Total orbital angular momentum L, from the spectroscopic letter.

        S=0, P=1, D=2, F=3, then alphabetical skipping J. Used to size the
        octahedral reduction (sum of irrep dimensions must be 2L+1) and the
        free-ion degeneracy (2S+1)(2L+1).
        """
        return "SPDFGHI".index(self.value)


class TermKey(StrEnum):
    """Every octahedral term key emitted by the d2..d8 solvers.

    Closed set of 23. ``test_terms.py`` asserts this against what the solvers
    actually produce, so the enum cannot drift from reality in either direction.

    Naming: ``<MULTIPLICITY_WORD>_<IRREP>[_<SUBSCRIPT>]``. Eg terms carry no
    subscript, matching Oh convention -- writing ``QUINTET_E_1`` is an
    AttributeError, which is how the historical ``5_E_1`` defect is prevented.
    """

    # multiplicity 1 (singlets)
    SINGLET_A_1 = "1_A_1"
    SINGLET_A_2 = "1_A_2"
    SINGLET_E = "1_E"
    SINGLET_T_1 = "1_T_1"
    SINGLET_T_2 = "1_T_2"
    # multiplicity 2 (doublets)
    DOUBLET_A_1 = "2_A_1"
    DOUBLET_A_2 = "2_A_2"
    DOUBLET_E = "2_E"
    DOUBLET_T_1 = "2_T_1"
    DOUBLET_T_2 = "2_T_2"
    # multiplicity 3 (triplets)
    TRIPLET_A_1 = "3_A_1"
    TRIPLET_A_2 = "3_A_2"
    TRIPLET_E = "3_E"
    TRIPLET_T_1 = "3_T_1"
    TRIPLET_T_2 = "3_T_2"
    # multiplicity 4 (quartets)
    QUARTET_A_1 = "4_A_1"
    QUARTET_A_2 = "4_A_2"
    QUARTET_E = "4_E"
    QUARTET_T_1 = "4_T_1"
    QUARTET_T_2 = "4_T_2"
    # multiplicity 5 (quintets)
    QUINTET_E = "5_E"
    QUINTET_T_2 = "5_T_2"
    # multiplicity 6 (sextet)
    SEXTET_A_1 = "6_A_1"

    @property
    def multiplicity(self) -> int:
        """Spin multiplicity 2S+1."""
        return int(self.value.split("_", 1)[0])

    @property
    def irrep(self) -> Irrep:
        """Mulliken irreducible-representation symbol."""
        return Irrep(self.value.split("_")[1])

    @property
    def subscript(self) -> int | None:
        """Mulliken subscript, or None for E terms which carry none in Oh."""
        parts = self.value.split("_")
        # "<mult>_<irrep>" for E terms, "<mult>_<irrep>_<subscript>" otherwise.
        subscript_index = 2
        return int(parts[subscript_index]) if len(parts) > subscript_index else None


# Strict grammar. The previous pattern accepted `1_T_3`, `5_E_1`, `9_B_2`,
# `1_T_9` and `0_A_1` -- that permissiveness is why the two spelling defects
# were never caught. Encoded here: multiplicity 1..6; A and T take subscript
# 1 or 2; E takes none.
TERM_KEY_RE = re.compile(
    r"^(?P<mult>[1-6])_(?:(?P<at>[AT])_(?P<sub>[12])|(?P<e>E))(?:_(?P<parity>[gu]))?$",
)


def parse_term_key(term: str) -> TermKey | None:
    """Return the :class:`TermKey` for ``term``, or None if it is not a valid key.

    Validates against both the grammar and the closed set, so a
    grammatically-plausible but non-existent key (e.g. ``6_T_2``) is rejected too.
    """
    if not TERM_KEY_RE.match(term):
        return None
    try:
        return TermKey(term)
    except ValueError:
        return None
