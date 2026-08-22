"""Typed level structure for a d^n term manifold.

Replaces the bare ``dict[TermKey, ndarray]`` that ``matrices.dN.solver()``
returns. The dict cannot express the assignment problem: for d8 it maps
``3_T_1`` to a two-element array, so both nu2 and nu3 come out labelled
``3_A_2->3_T_1`` when a chemist needs ``3T1g(F)`` and ``3T1g(P)``.

Two measured invariants make the typed form sound (see test_levels.py):

* within a term block the levels stay ascending for every Dq -- 0 violations
  over 120 Dq points x every block, d2..d8. That is the non-crossing rule for
  same-symmetry states, so the multiplet INDEX is a stable identity, not an
  accident of sort order.
* ``(term, index)`` is unique for all seven configurations.

So **uniqueness rests on (term, index) and never needs parentage**. Parentage
adds chemical meaning on top.

Parentage is DERIVED, never declared. At Dq = 0 the octahedral field vanishes,
so every level descending from the same free-ion term is degenerate; grouping
the zero-field spectrum by energy recovers the parentage with no lookup table to
drift out of sync. A declared table would be checked against the solver that
produced it -- the tautology this project has already hit three times.

Known limit, surfaced rather than hidden: for d3/d7 the terms 2H and 2P are both
at 9B+3C (Racah's accidental d3 degeneracy), so energy grouping yields 7 groups
where 8 free-ion terms exist. Uniqueness is unaffected.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from functools import lru_cache
from typing import TYPE_CHECKING

import numpy as np

from tanabesugano.terms import Irrep
from tanabesugano.terms import TermKey


if TYPE_CHECKING:
    from collections.abc import Mapping
    from collections.abc import Sequence


# Degeneracy of each Mulliken irrep in Oh. Group theory, not measurement.
IRREP_DIMENSION: dict[Irrep, int] = {Irrep.A: 1, Irrep.E: 2, Irrep.T: 3}

# A 3d shell offers 5 orbitals x 2 spins.
SPIN_ORBITALS = 10

# Ordinal suffixes indexing the MULTIPLET: 3_T_1(a) is the lowest 3_T_1 level,
# 3_T_1(b) the next. Deliberately NOT keyed on parentage -- a free-ion term can
# feed the same irrep more than once (d4 3_T_1 has parent ranks [1,1,2,3,4,11,12]),
# so a parentage-keyed label collides. The multiplet index is verified unique.
_SUFFIXES = "abcdefghijklmnopqrstuvwxyz"

# Zero-field energies within this tolerance count as one free-ion term.
_DEGENERACY_TOL_CM1 = 1e-4


def _math_body(term: TermKey) -> str:
    """Return the mathtext for a term with its ``$`` delimiters stripped.

    Delegates the entire term grammar to :mod:`plot_style`, which owns the one
    regex all three renderings share. This module must never grow a second copy
    of it -- two spellings of the same term is exactly the drift that put
    ``5_E_1`` and ``1_T_3`` into the codebase for years.
    """
    from tanabesugano import plot_style  # deferred: pulls matplotlib

    return plot_style.term_to_mathtext(term.value).strip("$")


@dataclass(frozen=True)
class Level:
    """One eigenvalue of one term block, with everything needed to name it."""

    term: TermKey
    index: int
    """Position within the multiplet. Stable: same-symmetry levels do not cross."""
    energy_cm1: float
    """Absolute energy relative to the ground level. E/B is a view, not storage."""
    parent_rank: int | None = None
    """Which free-ion term this level descends from, ordered by zero-field energy.

    ``None`` when parentage was not derived. Deriving it costs an extra
    zero-field solve, which callers holding a states dict they already computed
    (see :meth:`LevelSet.from_states`) have no reason to pay for. Optional is
    honest here: parentage is chemical annotation and plays no part in identity,
    which is ``(term, index)``.
    """
    parent_candidates: tuple[str, ...] = ()
    """Free-ion term symbols this level could descend from, e.g. ``("3P",)``.

    Usually one. More than one where an accidental degeneracy makes the answer
    genuinely undecidable from energy plus irrep: d3/d7 place 2H and 2P at the
    same 9B+3C for every (B, C), and the three 2T_1 levels there could belong to
    either. Reporting both is the honest answer; see
    :func:`tanabesugano.free_ion.parent_candidates`.

    Empty when parentage was not derived at all -- :meth:`LevelSet.from_states`
    does not pay for the extra zero-field solve.
    """
    multiplet_size: int = 1
    """How many levels this level's term block holds. Drives ordinal suppression.

    Required for rendering, not for identity: ``(term, index)`` alone is the
    key. It exists because a lone ``3_A_2`` must print as ``3A2g``, not
    ``3A2g(a)`` -- see :attr:`label`.
    """

    @property
    def multiplicity(self) -> int:
        """2S+1, derived from the term -- never stored, so it cannot disagree."""
        return self.term.multiplicity

    @property
    def irrep(self) -> Irrep:
        """Mulliken irreducible-representation symbol, derived from the term."""
        return self.term.irrep

    @property
    def degeneracy(self) -> int:
        """(2S+1) x dim(Gamma): how many microstates this level accounts for."""
        return self.multiplicity * IRREP_DIMENSION[self.irrep]

    @property
    def ordinal(self) -> str:
        """``(a)``, ``(b)``, ... -- or ``""`` when the term has only one level.

        Suppressed for single-level terms because that is how the literature
        writes them: Lever, LibreTexts and the textbooks print 3T2g plainly and
        disambiguate only where they must. 23 of the 65 terms across d2..d8 are
        single-level, so always printing ``(a)`` would add a notation a
        published figure would then have to explain.

        Keyed on ``index``, not ``parent_rank``: parentage is not injective
        within a term block, since one free-ion term can feed the same irrep
        twice. ``(term, index)`` is verified unique for every configuration.
        """
        if self.multiplet_size <= 1:
            return ""
        return f"({_SUFFIXES[self.index]})"

    @property
    def uid(self) -> str:
        """``3_T_1#1`` -- the machine key. Always carries the index.

        Use this, never :attr:`label`, whenever a string has to round-trip
        back to a level: as a CSV column, a dict key, or a plot-series id.
        """
        return f"{self.term.value}#{self.index}"

    @property
    def label(self) -> str:
        """``3_T_1(b)``, or plain ``3_A_2`` for a single-level term.

        Human-facing, in the raw solver-key spelling. **Not an identity key** --
        the ordinal is suppressed for single-level terms, so this is a display
        string. Identity is ``(term, index)``; the string form of it is
        :attr:`uid`.
        """
        return f"{self.term.value}{self.ordinal}"

    @property
    def ascii(self) -> str:
        """``3T1g(b)`` -- pure ASCII, for logs, CSV cells and dumb terminals."""
        from tanabesugano import plot_style  # deferred: pulls matplotlib

        return f"{plot_style.term_to_ascii(self.term.value)}{self.ordinal}"

    @property
    def unicode(self) -> str:
        """``³T₁g(b)`` -- for Prefab tables, chart labels and chat output."""
        from tanabesugano import plot_style  # deferred: pulls matplotlib

        return f"{plot_style.term_to_unicode(self.term.value)}{self.ordinal}"

    @property
    def latex(self) -> str:
        """``$^{3}T_{1g}(b)$`` -- matplotlib mathtext, also valid LaTeX math."""
        return f"${_math_body(self.term)}{self.ordinal}$"

    @property
    def parent_symbol(self) -> str | None:
        """``"3P"`` when the free-ion parent is unique, else ``None``.

        ``None`` covers two different situations on purpose, and callers that
        care can tell them apart via :attr:`parent_candidates`: an empty tuple
        means parentage was never derived, several entries mean it was derived
        and came back genuinely ambiguous. What this never does is pick one.
        """
        if len(self.parent_candidates) == 1:
            return self.parent_candidates[0]
        return None

    @property
    def parent_suffix(self) -> str:
        """``(P)`` -- the free-ion disambiguator, or the positional one as fallback.

        Empty for a single-level term, exactly as :attr:`ordinal` is: a term
        holding one level needs no disambiguator and the literature prints it
        plain. Falls back to :attr:`ordinal` when the parent is not unique, so a
        label is always printable and never silently drops its disambiguator.
        """
        if self.multiplet_size <= 1:
            return ""
        symbol = self.parent_symbol
        if symbol is None:
            return self.ordinal
        # The multiplicity is already carried by the octahedral term, so the
        # suffix takes only the orbital letter: 3T_1(P), not 3T_1(3P).
        return f"({symbol[1:]})"

    @property
    def parent_unicode(self) -> str:
        """``³T₁g(P)`` -- for chat, Chart.js labels and Prefab tables.

        The counterpart of :attr:`unicode`, which uses the positional ordinal.
        Chart.js renders no mathtext, so an inline chart needs this rather than
        :attr:`parent_latex`.
        """
        from tanabesugano import plot_style  # deferred: pulls matplotlib

        return f"{plot_style.term_to_unicode(self.term.value)}{self.parent_suffix}"

    @property
    def parent_plotly(self) -> str:
        """``<sup>3</sup>T<sub>1g</sub>(P)`` -- plotly markup with parentage.

        The plotly rung of the same ladder as :attr:`parent_unicode` (Chart.js,
        Prefab, chat) and :attr:`parent_latex` (matplotlib). Plotly.js typesets
        a small HTML subset in trace names and hover text, so a legend can carry
        a real raised multiplicity instead of a pre-composed Unicode digit.

        Inert everywhere else: hand this to matplotlib or a CSV cell and the
        tags print verbatim. See :func:`tanabesugano.plot_style.term_to_plotly`.
        """
        from tanabesugano import plot_style  # deferred: pulls matplotlib

        return f"{plot_style.term_to_plotly(self.term.value)}{self.parent_suffix}"

    @property
    def parent_label_display(self) -> str:
        """``3_T_1(P)`` -- :attr:`label` with free-ion parentage instead of (a)/(b)."""
        return f"{self.term.value}{self.parent_suffix}"

    @property
    def parent_latex(self) -> str:
        """``$^{3}T_{1g}(P)$`` -- mathtext with parentage, for figure labels.

        The counterpart of :attr:`latex`, which uses the positional ordinal. Use
        this one for anything a reader will compare against the literature.
        """
        return f"${_math_body(self.term)}{self.parent_suffix}$"

    @property
    def parent_label(self) -> str:
        """Which zero-field free-ion group this level descends from.

        Chemical annotation, NOT an identifier -- see :attr:`label`. For d8 the
        two 3_T_1 levels carry different parents (3F and 3P, split by exactly
        15B at zero field); for d4 several share one.

        Says so plainly when parentage was never derived, rather than printing
        a plausible-looking ``<-None``.
        """
        if self.parent_rank is None:
            return f"{self.term.value}<-?"
        return f"{self.term.value}<-{self.parent_rank}"

    def energy_over_b(self, b: float) -> float:
        """E/B, the usual Tanabe-Sugano ordinate. A view over ``energy_cm1``."""
        if b <= 0:
            msg = f"B must be positive to form E/B; got {b}"
            raise ValueError(msg)
        return self.energy_cm1 / b


@dataclass(frozen=True)
class LevelSet:
    """The complete term manifold of one d^n configuration at one (Dq, B, C)."""

    d_count: int
    Dq: float
    B: float
    C: float
    levels: tuple[Level, ...] = field(default_factory=tuple)
    free_ion_group_count: int = 0

    @classmethod
    def solve(
        cls,
        d_count: int,
        dq: float,
        b: float | None = None,
        c: float | None = None,
    ) -> LevelSet:
        """Solve the configuration and attach derived parentage."""
        from tanabesugano.mcp._compute import compute_point
        from tanabesugano.mcp._defaults import DEFAULTS

        cfg = DEFAULTS[d_count]
        b = float(cfg["default_B"]) if b is None else float(b)
        c = float(cfg["default_C"]) if c is None else float(c)

        parents, parent_symbols, group_count = _derive_parentage(d_count, b, c)
        states = compute_point(d_count, dq, b, c)
        ground = min(float(e) for v in states.values() for e in v)

        levels = [
            Level(
                term=TermKey(key),
                index=i,
                energy_cm1=float(energy) - ground,
                parent_rank=parents[TermKey(key)][i],
                parent_candidates=parent_symbols[TermKey(key)][i],
                multiplet_size=len(values),
            )
            for key, values in states.items()
            for i, energy in enumerate(values)
        ]
        return cls(
            d_count=d_count,
            Dq=float(dq),
            B=b,
            C=c,
            levels=tuple(sorted(levels, key=lambda lv: (lv.energy_cm1, lv.term.value, lv.index))),
            free_ion_group_count=group_count,
        )

    @classmethod
    def from_states(
        cls,
        states: Mapping[str, Sequence[float]],
        *,
        d_count: int = 0,
        dq: float = 0.0,
        b: float = 0.0,
        c: float = 0.0,
    ) -> LevelSet:
        """Wrap an already-computed states dict. Parentage is NOT derived.

        For callers that hold the output of ``solver()`` / ``compute_point``
        and need naming, not chemistry -- above all the fitting objective,
        which evaluates thousands of points and must not pay for a second
        zero-field solve at each one. ``parent_rank`` is left ``None``; use
        :meth:`solve` when parentage matters.

        The ``(Dq, B, C)`` that produced ``states`` are accepted for the record
        and default to zero, because a caller like ``transition_candidates``
        genuinely does not know them.
        """
        ground = min(float(e) for v in states.values() for e in v)
        levels = [
            Level(
                term=TermKey(key),
                index=i,
                energy_cm1=float(energy) - ground,
                multiplet_size=len(values),
            )
            for key, values in states.items()
            for i, energy in enumerate(values)
        ]
        return cls(
            d_count=d_count,
            Dq=float(dq),
            B=float(b),
            C=float(c),
            levels=tuple(sorted(levels, key=lambda lv: (lv.energy_cm1, lv.term.value, lv.index))),
        )

    # -- declared contents -------------------------------------------------
    @property
    def electron_count(self) -> int:
        """d-electron count. Alias of ``d_count`` reading better at call sites."""
        return self.d_count

    @property
    def level_count(self) -> int:
        """How many levels the manifold holds.

        Not the term count: a term may contribute several levels, which is the
        whole reason :class:`LevelSet` exists at all.
        """
        return len(self.levels)

    @property
    def terms(self) -> tuple[TermKey, ...]:
        """Terms present, in first-appearance order by energy."""
        seen: dict[TermKey, None] = {}
        for lv in self.levels:
            seen.setdefault(lv.term, None)
        return tuple(seen)

    @property
    def total_degeneracy(self) -> int:
        """Must equal C(10, n) -- see test_completeness.py."""
        return sum(lv.degeneracy for lv in self.levels)

    @property
    def ground(self) -> Level:
        """Lowest-lying level. Levels are stored energy-sorted, so this is [0].

        Energies are referenced to the ground level, so ``ground.energy_cm1``
        is 0.0 by construction.
        """
        return self.levels[0]

    def as_dict(self) -> dict[TermKey, np.ndarray]:
        """Term -> ascending eigenvalues, for numeric consumers.

        Plot-series builders and sweeps want arrays keyed by term and have no
        use for per-level naming. This is a view, not the storage: anything that
        NAMES a level or a transition must use the Level API, or it reintroduces
        the ambiguity where a multiplet collapses to one label.
        """
        out: dict[TermKey, list[float]] = {}
        for lv in sorted(self.levels, key=lambda x: (x.term.value, x.index)):
            out.setdefault(lv.term, []).append(lv.energy_cm1)
        return {term: np.asarray(v, dtype=float) for term, v in out.items()}

    def for_term(self, term: TermKey | str) -> tuple[Level, ...]:
        """Every level of one term, in multiplet order.

        Accepts the string spelling as well as the enum member. ``TermKey`` is
        a ``StrEnum`` specifically so it *is* a ``str`` at every boundary, but
        this compared with ``is``, which is False for a plain string even
        though ``==`` is True -- so ``for_term("3_T_1")`` returned an empty
        tuple and no error. Silent emptiness is the failure mode this package
        keeps re-learning; an unknown term still returns ``()``, but a known
        one spelled as a string no longer does.
        """
        return tuple(lv for lv in self.levels if lv.term == term)

    def spin_allowed(self) -> tuple[Level, ...]:
        """Levels reachable from the ground term without a spin flip."""
        mult = self.ground.multiplicity
        return tuple(lv for lv in self.levels if lv.multiplicity == mult and lv.energy_cm1 > 0)

    def display_labels(self, renderer: str = "unicode") -> dict[str, str]:
        """Map every :attr:`Level.uid` to a label no two levels share.

        Parentage is the right vocabulary for a figure -- ``(F)``/``(P)`` is
        what the literature prints, ``(a)``/``(b)`` is this package's internal
        spelling. But parentage is **not injective**: one free-ion term can feed
        the same irrep twice, so d4, d5 and d6 each hold two pairs of levels
        whose ``parent_*`` labels are byte-identical (d6: two ``3T1g(H)``, two
        ``1T2g(I)``). ``parent_suffix`` only falls back to the ordinal when the
        *parent* is ambiguous, which is a different situation and does not cover
        this one.

        Printing two curves with the same name is fine in a table, where a uid
        column sits beside it, and not fine on a figure where the label IS the
        identification. So the colliding pair -- and only the colliding pair --
        gets the ordinal folded in: ``3T1g(H,a)``, ``3T1g(H,b)``. Every
        non-colliding label is left exactly as :attr:`Level.parent_unicode` and
        friends produce it, so the common case gains no notation to explain.

        Both figure renderers call this rather than formatting labels
        themselves; that is the only reason they cannot drift apart.

        Args:
            renderer: ``"unicode"`` (Chart.js, chat), ``"plotly"`` (plotly
                markup), ``"latex"`` (matplotlib mathtext) or ``"ascii"``.

        Returns:
            ``{uid: label}`` for every level in the set.

        """
        from tanabesugano import plot_style  # deferred: pulls matplotlib

        bodies = {
            "ascii": plot_style.term_to_ascii,
            "unicode": plot_style.term_to_unicode,
            "plotly": plot_style.term_to_plotly,
            "latex": lambda t: _math_body(TermKey(t)),
        }
        if renderer not in bodies:
            msg = f"unknown renderer {renderer!r}; choose one of {sorted(bodies)}"
            raise ValueError(msg)

        counts: dict[tuple[TermKey, str], int] = {}
        for lv in self.levels:
            key = (lv.term, lv.parent_suffix)
            counts[key] = counts.get(key, 0) + 1

        labels: dict[str, str] = {}
        for lv in self.levels:
            suffix = lv.parent_suffix
            if counts[(lv.term, suffix)] > 1:
                # Always of the form "(X)" here: an empty suffix means a
                # single-level term, which cannot collide with anything.
                suffix = f"{suffix[:-1]},{_SUFFIXES[lv.index]})"
            body = bodies[renderer](lv.term.value)
            labels[lv.uid] = f"${body}{suffix}$" if renderer == "latex" else f"{body}{suffix}"
        return labels

    def transition_label(self, excited: Level) -> str:
        """``3_A_2→3_T_1(b)`` -- an unambiguous band assignment.

        Both sides carry their ordinal, because both sides can need one: the
        headline d7 band is written 4T1g(F) → 4T1g(P) precisely because the
        ground and the excited state share a term symbol. For a single-level
        ground term like d8's 3A2g the ordinal is suppressed and this reads
        exactly as it always did.
        """
        return f"{self.ground.label}→{excited.label}"

    def transition_ascii(self, excited: Level) -> str:
        """``3A2g -> 3T1g(b)`` -- pure ASCII band assignment."""
        return f"{self.ground.ascii} -> {excited.ascii}"

    def transition_unicode(self, excited: Level) -> str:
        """``³A₂g → ³T₁g(b)`` -- for Prefab tables and chat output."""
        return f"{self.ground.unicode} → {excited.unicode}"

    def transition_latex(self, excited: Level) -> str:
        r"""``$^{3}A_{2g} \rightarrow {}^{3}T_{1g}(b)$`` -- a figure caption.

        The excited term gets an explicit empty base ``{}`` before its
        superscript: without it ``\rightarrow^{3}`` sets the 3 *above the
        arrow* instead of on the term.
        """
        ground = f"{_math_body(self.ground.term)}{self.ground.ordinal}"
        excited_body = f"{{}}{_math_body(excited.term)}{excited.ordinal}"
        return f"${ground} \\rightarrow {excited_body}$"


@lru_cache(maxsize=128)
def _derive_parentage(
    d_count: int,
    b: float,
    c: float,
) -> tuple[dict[TermKey, tuple[int, ...]], dict[TermKey, tuple[tuple[str, ...], ...]], int]:
    """Map each level to its free-ion parent by zero-field degeneracy grouping.

    Returns ``(ranks, candidate_symbols, group_count)``. The rank is positional
    -- which zero-field group, ordered by energy -- and was always available.
    The symbols name the actual free-ion term, which is what the literature
    prints, and are matched on energy AND spin multiplicity AND irrep: a level
    cannot descend from a term whose Oh reduction does not contain its irrep.

    That third filter earns its place. d3/d7 put 2H and 2P at the same
    9B + 3C, so energy alone would call all five levels there ambiguous. 2P
    reduces to T_1 only, so the 2E and 2T_2 levels resolve to 2H outright and
    only the three 2T_1 remain genuinely undecidable.

    Cached: parentage depends only on (d_count, B, C), never on Dq, so a sweep
    of N Dq points pays for the extra zero-field solve exactly once instead of
    N times. Without this a 1000-point diagram would cost ~3x the raw solver.
    """
    from tanabesugano.free_ion import free_ion_levels
    from tanabesugano.free_ion import parent_candidates
    from tanabesugano.mcp._compute import compute_point

    zero = compute_point(d_count, 0.0, b, c)
    energies = sorted({float(e) for v in zero.values() for e in v})

    groups: list[float] = []
    for energy in energies:
        if not groups or abs(energy - groups[-1]) > _DEGENERACY_TOL_CM1:
            groups.append(energy)

    free_ion = free_ion_levels(d_count, b, c)
    ranks: dict[TermKey, tuple[int, ...]] = {}
    symbols: dict[TermKey, tuple[tuple[str, ...], ...]] = {}
    for key, values in zero.items():
        term = TermKey(key)
        ranks[term] = tuple(int(np.argmin([abs(float(e) - g) for g in groups])) for e in values)
        symbols[term] = tuple(
            tuple(t.symbol for t in parent_candidates(float(e), key, free_ion)) for e in values
        )
    return ranks, symbols, len(groups)
