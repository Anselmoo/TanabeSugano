"""The term-key vocabulary must be uniform across d2..d8.

Two divergences existed, each affecting exactly two configurations while the
other five used the correct form:

* ``1_T_3`` (d2, d8) -- there is no T3 irrep in Oh. The producing method is
  ``T_1_2_states()``, i.e. T with multiplicity 1 and subscript 2, and d4/d6 key
  that same method's output correctly as ``1_T_2``. Consequence: d2 and d8 had
  no ``1_T_2`` key at all, so any lookup for it silently missed them.
* ``1_E_1`` / ``3_E_1`` / ``5_E_1`` (d4, d6) -- Eg carries no subscript in Oh,
  and each multiplicity appears only once, so the trailing index is meaningless.
  d2/d5/d8 correctly emit ``1_E`` / ``2_E`` / ``4_E``. Consequence: a lookup for
  ``"5_E"`` on d4 found nothing.

Both were artifacts of the ``E_<mult>_<n>_states`` / ``T_<mult>_<n>_states``
method naming leaking into the public keys.
"""

from __future__ import annotations

import pytest

from tanabesugano import matrices
from tanabesugano.mcp._compute import compute_point
from tanabesugano.mcp._defaults import DEFAULTS
from tanabesugano.terms import TermKey


ALL_D = tuple(range(2, 9))


def keys_for(d_count: int) -> set[str]:
    cfg = DEFAULTS[d_count]
    return set(
        compute_point(
            d_count,
            1000.0,
            float(cfg["default_B"]),
            float(cfg["default_C"]),
        ),
    )


@pytest.mark.parametrize("d_count", ALL_D)
def test_no_t3_irrep(d_count: int) -> None:
    """Oh has T1 and T2 only -- a T3 key cannot be right."""
    offenders = {k for k in keys_for(d_count) if k.split("_")[1:2] == ["T"] and k.endswith("_3")}
    assert not offenders, f"d{d_count} emits non-existent T3 terms: {sorted(offenders)}"


@pytest.mark.parametrize("d_count", [2, 8])
def test_d2_d8_have_a_singlet_t2(d_count: int) -> None:
    """T_1_2_states() output must be keyed 1_T_2, as d4/d6 already do."""
    assert "1_T_2" in keys_for(d_count)


@pytest.mark.parametrize("d_count", ALL_D)
def test_e_terms_carry_no_subscript(d_count: int) -> None:
    """Eg has no subscript in Oh, and each multiplicity occurs once per config."""
    offenders = {
        k for k in keys_for(d_count) if k.split("_")[1:2] == ["E"] and len(k.split("_")) > 2
    }
    assert not offenders, f"d{d_count} emits indexed E terms: {sorted(offenders)}"


@pytest.mark.parametrize("d_count", [4, 6])
def test_d4_d6_high_spin_ground_term_is_plain_e(d_count: int) -> None:
    """The d4 high-spin ground term is 5Eg -- reachable as '5_E'."""
    assert "5_E" in keys_for(d_count)


def test_vocabulary_is_consistent_across_configurations() -> None:
    """No irrep symbol may be spelled two different ways across the family."""
    spellings: dict[tuple[str, str], set[str]] = {}
    for d_count in ALL_D:
        for key in keys_for(d_count):
            parts = key.split("_")
            if len(parts) < 2:
                continue
            spellings.setdefault((parts[0], parts[1]), set()).add(key)
    inconsistent = {
        symbol: sorted(forms)
        for symbol, forms in spellings.items()
        if len({len(f.split("_")) for f in forms}) > 1
    }
    assert not inconsistent, f"same irrep spelled inconsistently: {inconsistent}"


# --------------------------------------------------------------------------
# The DECLARED vocabulary, not just the emitted one.
# --------------------------------------------------------------------------


def test_every_solver_declares_termkey_keys() -> None:
    """``solver()`` must annotate its keys as ``TermKey``, not ``str``.

    Eight signatures said ``dict[str, ...]`` while returning ``TermKey`` keys.
    Nothing caught the earlier ``dict[str, ...]`` because ``TermKey`` is a
    ``StrEnum`` and therefore *is* a ``str``: the annotation was technically
    satisfied and completely uninformative, which is how it survived the
    vocabulary rename above.

    ``solver()`` now returns a ``LevelSet``. A bare mapping cannot express a
    multiplet -- it collapses d8's two 3_T_1 levels onto one key -- so the
    return type is the typed manifold, and ``LevelSet.as_dict()`` is the
    explicit view for numeric consumers that only want arrays.
    """
    from typing import get_type_hints

    from tanabesugano import matrices
    from tanabesugano.levels import LevelSet

    wrong: dict[str, object] = {}
    for d_count in ALL_D:
        returns = get_type_hints(getattr(matrices, f"d{d_count}").solver)["return"]
        if returns is not LevelSet:
            wrong[f"d{d_count}"] = returns
    # The abstract base declares the same contract its subclasses implement.
    base_returns = get_type_hints(matrices.LigandFieldTheory.solver)["return"]
    if base_returns is not LevelSet:
        wrong["LigandFieldTheory"] = base_returns

    assert not wrong, f"solver() does not declare LevelSet in: {wrong}"


@pytest.mark.parametrize("d_count", ALL_D)
def test_solver_keys_are_actually_termkey_instances(d_count: int) -> None:
    """What the annotation above is required to describe."""
    cfg = DEFAULTS[d_count]
    solver = getattr(matrices, f"d{d_count}")(
        Dq=1000.0,
        B=float(cfg["default_B"]),
        C=float(cfg["default_C"]),
    )
    for key in solver.solver().as_dict():
        assert isinstance(key, TermKey), f"d{d_count} emitted a bare str key {key!r}"
