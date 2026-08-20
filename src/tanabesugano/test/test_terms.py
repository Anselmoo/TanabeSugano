"""The term-symbol vocabulary is a closed set, and must be typed as one.

Four defects in this package traced to term symbols being plain strings:

  * free-ion notation ("3F") and octahedral keys ("3_T_1") flowed through the
    same `str` type, so a parser handed the wrong vocabulary returned 0 and
    silently disabled spin-allowed filtering in four tools;
  * "1_T_3" was written for d2/d8 -- there is no T3 irrep in Oh;
  * "5_E_1" was written for d4/d6 -- Eg carries no subscript;
  * the permissive term regex accepted all of the above, which is *why* the
    typos survived review, tests and linting for the life of the project.

`TermKey` closes the set: a typo is an AttributeError at import time, with no
type checker required. `FreeIonTerm` is deliberately a SEPARATE type so the two
vocabularies can no longer be confused.
"""

from __future__ import annotations

import pytest

from tanabesugano.mcp._compute import compute_point
from tanabesugano.mcp._defaults import DEFAULTS
from tanabesugano.terms import FreeIonTerm
from tanabesugano.terms import TermKey
from tanabesugano.terms import parse_term_key


def solver_key_union() -> set[str]:
    """Every term key any solver actually emits -- the specification."""
    union: set[str] = set()
    for d_count in range(2, 9):
        cfg = DEFAULTS[d_count]
        union |= set(
            compute_point(
                d_count,
                1000.0,
                float(cfg["default_B"]),
                float(cfg["default_C"]),
            ),
        )
    return union


class TestTermKeyMatchesReality:
    def test_enum_exactly_covers_the_solver_output(self) -> None:
        """Drift guard: the enum and the solvers must never disagree.

        A new term in matrices.py without a TermKey member fails here, and a
        stale member left behind after a rename fails here too.
        """
        assert {k.value for k in TermKey} == solver_key_union()

    def test_termkey_is_a_str(self) -> None:
        """StrEnum IS str -- so json, pydantic, f-strings and == work unchanged.

        This is what makes the migration free: no adapter code at any boundary.
        """
        assert isinstance(TermKey.TRIPLET_A_2, str)
        assert TermKey.TRIPLET_A_2 == "3_A_2"
        assert f"{TermKey.TRIPLET_A_2}" == "3_A_2"

    def test_json_round_trip_needs_no_adapter(self) -> None:
        import json

        payload = {TermKey.TRIPLET_A_2: [0.0], TermKey.TRIPLET_T_2: [8500.0]}
        assert json.loads(json.dumps(payload)) == {"3_A_2": [0.0], "3_T_2": [8500.0]}

    @pytest.mark.parametrize("typo", ["SINGLET_T_3", "QUINTET_E_1", "TRIPLET_B_2"])
    def test_a_typo_is_an_attribute_error(self, typo: str) -> None:
        """The whole point: caught with NO tooling, at attribute-access time."""
        with pytest.raises(AttributeError):
            getattr(TermKey, typo)


class TestVocabulariesCannotBeConfused:
    def test_free_ion_terms_are_a_distinct_type(self) -> None:
        assert not isinstance(FreeIonTerm.F, TermKey)
        assert FreeIonTerm.F.value not in {k.value for k in TermKey}

    def test_free_ion_covers_the_defaults_table(self) -> None:
        """Every DEFAULTS ground_term must be expressible as a FreeIonTerm."""
        spelled = {str(DEFAULTS[d]["ground_term"])[-1] for d in range(2, 9)}
        assert spelled <= {t.value for t in FreeIonTerm}


class TestParserRejectsInvalidForms:
    """The permissive regex is what let 1_T_3 and 5_E_1 survive."""

    @pytest.mark.parametrize("key", sorted({k.value for k in TermKey}))
    def test_accepts_every_real_key(self, key: str) -> None:
        assert parse_term_key(key) is not None

    @pytest.mark.parametrize(
        "bad",
        [
            "1_T_3",  # no T3 irrep in Oh
            "5_E_1",  # Eg carries no subscript
            "9_B_2",  # B irrep does not occur here; multiplicity 9 impossible
            "1_T_9",  # no such subscript
            "0_A_1",  # multiplicity is 2S+1 >= 1
            "3F",  # free-ion notation
            "6S",
            "",
        ],
    )
    def test_rejects_invalid_forms(self, bad: str) -> None:
        assert parse_term_key(bad) is None
