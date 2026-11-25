"""Ion case studies: one classic 3d-row ion per fitting regime.

These are chosen so that together they span the behaviour space of the fitter.
Each ion isolates a different regime, and the regime -- not the element -- is
what is being tested:

    V(III)   d2, 3T1g ground   closed form must REFUSE (nu1 != 10Dq)
    Cr(III)  d3, 4A2g ground   closed form is EXACT
    Mn(II)   d5, 6A1g ground   NOT FITTABLE -- correct behaviour is to raise
    Co(III)  d6, low-spin      only fittable in the low-spin regime
    Ni(II)   d8, 3A2g ground   closed form is EXACT

MODULE BOUNDARY -- one claim, one place, one tolerance.
This module OWNS every comparison against a published (Dq, B). Asserting the
same fixture in two modules at two tolerances means the looser one masks what
the tighter one catches, so the fitter-mechanics module deliberately holds none.

    test_matrices_invariants.py  exact analytic identities (no external data)
    test_spectrum_fitting.py     fitter mechanics, estimator semantics, guards,
                                 synthetic round-trips
    test_ion_case_studies.py     THIS FILE -- literature fixtures, by regime
    test_term_key_vocabulary.py  term-key spelling

ADMISSIBILITY. A literature fixture is a record, not a row in a parametrize
list: prose in a docstring is unqueryable and drifts from the values beside it.
Every field of ``IonFixture`` below exists because something went wrong without
it, and ``__post_init__`` refuses an inadmissible record at import time. The
fields are documented on the dataclass; the traps they close are:

    published_quantity  Dq vs 10Dq vs Delta_o -- the factor-of-10 trap
    estimator           closed-form and least-squares legitimately disagree
    degrees_of_freedom  DOF = 0 means rmse ~ 0 BY CONSTRUCTION, not by quality
    expected_outcome    some systems must RAISE; that is the correct answer
    source, source_tier where the numbers came from, and how far from primary
    tolerance_reason    mandatory: WHY this bound, not merely what it is

R1 -- no d5 or d6 fixture may be validated against a published Tanabe-Sugano
DIAGRAM. The published d5/d6 diagrams carry a propagated error (Hormann & Shaw,
J. Chem. Educ. 1987, 64, 918), so such a test validates the error. Enforced at
construction: a d5/d6 fixture with expected_outcome "fit" is rejected unless its
source_tier is "primary" (i.e. directly reported band energies, not parameters
read off a diagram). The low-spin d6 case below is admissible under that rule
precisely because it compares against no published (Dq, B) at all.

Regime map, measured from the solver (spin-allowed transitions from the ground
term); this is the specification the cases below are drawn from:

    d   HS ground  n_HS   LS ground  n_LS   consequence
    2   3_T_1         3   3_T_1         3   fittable
    3   4_A_2         3   4_A_2         3   fittable, closed form exact
    4   5_E           1   3_T_1        17   HS: B unidentifiable
    5   6_A_1         0   2_T_2        31   HS: nothing spin-allowed at all
    6   5_T_2         1   1_A_1        22   HS: B unidentifiable; LS: fittable
    7   4_T_1         3   2_E          15   fittable
    8   3_A_2         3   3_A_2         3   fittable, closed form exact
"""

from __future__ import annotations

import csv
import os
import re
import subprocess
import sys

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Literal
from typing import get_args

import numpy as np
import pytest

from scipy.optimize import fsolve

from tanabesugano.mcp._compute import closed_form_dq_b
from tanabesugano.mcp._compute import compute_point
from tanabesugano.mcp._compute import fit_spectrum
from tanabesugano.mcp._compute import reference_ground_term
from tanabesugano.mcp._compute import transition_candidates
from tanabesugano.mcp._defaults import DEFAULTS
from tanabesugano.test._determinant_oracle import relative_term_levels
from tanabesugano.test._oracle_search import oracle_global_min
from tanabesugano.test._oracle_search import oracle_rmse


if TYPE_CHECKING:
    from collections.abc import Callable


PublishedQuantity = Literal["Dq", "10Dq", "Delta_o", "unknown"]
Estimator = Literal["closed_form", "least_squares", "unknown"]
SourceTier = Literal["primary", "textbook", "secondary"]
Outcome = Literal["fit", "warns", "raises"]
SpinState = Literal["high", "low"]

FREE_PARAMETERS = 2  # Dq and B; C is held fixed
CLOSED_FORM_CONFIGS = (3, 8)  # the only d-counts where nu1 == 10Dq exactly
DIAGRAM_ERROR_CONFIGS = (5, 6)  # Hormann & Shaw; see R1 in the module docstring
NU1_NORMALISATION_TOL = 0.01
NU1_LABEL = {3: "4_T_2", 8: "3_T_2"}
"""The band that is nu1 == 10Dq, for the configurations where that holds exactly."""


@dataclass(frozen=True, slots=True)
class Tolerance:
    """A comparison bound, tagged with whether it is relative or absolute.

    ``kind`` is kept explicit rather than inferred: an absolute bound on a
    quantity whose published value IS the closed form is a different claim from
    a relative bound absorbing estimator disagreement, and the two must not be
    silently interchangeable.
    """

    kind: Literal["rel", "abs"]
    value: float

    def approx(self, expected: float) -> object:
        """Return ``pytest.approx(expected)`` carrying this bound."""
        return pytest.approx(expected, **{self.kind: self.value})


@dataclass(frozen=True, slots=True)
class IonFixture:
    """One literature case, admissible only if every field is supplied.

    No field has a default. That is the point: a fixture is inadmissible unless
    every field is present, so "I did not think about provenance" cannot be
    spelled the same way as "provenance is Dq, stated by the source".

    published_Dq_cm1 / published_B_cm1 are ALREADY NORMALISED to Dq; the raw
    quantity the source printed is recorded in ``published_quantity``, and for
    d3/d8 the normalisation is checked arithmetically against nu1 == 10Dq.
    """

    label: str
    d_count: int
    spin_state: SpinState
    geometry: str
    bands_cm1: tuple[float, ...]
    source: str
    source_tier: SourceTier
    published_quantity: PublishedQuantity
    published_Dq_cm1: float | None
    published_B_cm1: float | None
    published_C_cm1: float | None
    estimator: Estimator
    degrees_of_freedom: int
    expected_outcome: Outcome
    expected_match: str | None
    tol_Dq: Tolerance | None
    tol_B: Tolerance | None
    max_rmse_cm1: float | None
    closed_form_tol_Dq: Tolerance | None
    closed_form_tol_B: Tolerance | None
    tolerance_reason: str
    band_labels: tuple[str, ...] | None
    include_spin_forbidden: bool

    def __post_init__(self) -> None:
        """Reject an inadmissible fixture at import time."""
        self._check_vocabulary()
        self._check_provenance()
        self._check_outcome_shape()
        self._check_labels()
        self._check_dq_normalisation()

    def _check_labels(self) -> None:
        """One label per band; a spin-forbidden fit is only ever run labelled."""
        if self.band_labels is not None and len(self.band_labels) != len(self.bands_cm1):
            msg = (
                f"{self.label}: {len(self.band_labels)} band_labels for "
                f"{len(self.bands_cm1)} bands -- one label per band"
            )
            raise ValueError(msg)
        if self.include_spin_forbidden and self.band_labels is None:
            msg = (
                f"{self.label}: include_spin_forbidden needs band_labels -- unlabelled, a "
                "spin-forbidden line can be read as any level"
            )
            raise ValueError(msg)

    def _check_vocabulary(self) -> None:
        for field, allowed in (
            ("published_quantity", get_args(PublishedQuantity)),
            ("estimator", get_args(Estimator)),
            ("source_tier", get_args(SourceTier)),
            ("expected_outcome", get_args(Outcome)),
            ("spin_state", get_args(SpinState)),
        ):
            value = getattr(self, field)
            if value not in allowed:
                msg = f"{self.label}: {field}={value!r} is not one of {allowed}"
                raise ValueError(msg)

    def _check_provenance(self) -> None:
        if not self.source.strip():
            msg = f"{self.label}: source is mandatory"
            raise ValueError(msg)
        if not self.tolerance_reason.strip():
            msg = f"{self.label}: tolerance_reason is mandatory -- say WHY this bound"
            raise ValueError(msg)
        expected_dof = len(self.bands_cm1) - FREE_PARAMETERS
        if self.degrees_of_freedom != expected_dof:
            msg = (
                f"{self.label}: degrees_of_freedom={self.degrees_of_freedom} but "
                f"{len(self.bands_cm1)} bands - {FREE_PARAMETERS} free "
                f"parameters = {expected_dof}"
            )
            raise ValueError(msg)

    def _check_outcome_shape(self) -> None:
        if self.expected_outcome == "raises":
            if self.expected_match is None:
                msg = f"{self.label}: a 'raises' fixture must name the expected message"
                raise ValueError(msg)
            return
        required = (
            self.published_Dq_cm1,
            self.published_B_cm1,
            self.tol_Dq,
            self.tol_B,
            self.max_rmse_cm1,
        )
        if any(item is None for item in required):
            msg = (
                f"{self.label}: a '{self.expected_outcome}' fixture needs "
                "published values and bounds"
            )
            raise ValueError(msg)
        if self.expected_outcome == "warns" and self.expected_match is None:
            msg = f"{self.label}: a 'warns' fixture must name the expected warning"
            raise ValueError(msg)
        if self.d_count in DIAGRAM_ERROR_CONFIGS and self.source_tier != "primary":
            msg = (
                f"{self.label}: R1 -- d{self.d_count} may not be validated against a published "
                "diagram (Hormann & Shaw, J. Chem. Educ. 1987, 64, 918). Admissible only with "
                "source_tier='primary' (directly reported band energies), or expected_outcome="
                "'raises'."
            )
            raise ValueError(msg)

    def _check_dq_normalisation(self) -> None:
        """Catch a 10Dq value pasted into the Dq field, for the configs that can.

        For a 4A2g (d3) or 3A2g (d8) ground term nu1 == 10Dq exactly, so the
        lowest band pins the normalisation independently of what the source
        happened to print. This is the factor-of-10 trap made mechanical.
        """
        if self.d_count not in CLOSED_FORM_CONFIGS or self.published_Dq_cm1 is None:
            return
        nu1 = min(self.bands_cm1)
        if self.band_labels is not None and NU1_LABEL[self.d_count] in self.band_labels:
            # A spin-forbidden line (d3 2E) can sit below nu1; the label says which is nu1.
            nu1 = self.bands_cm1[self.band_labels.index(NU1_LABEL[self.d_count])]
        if abs(10.0 * self.published_Dq_cm1 - nu1) / nu1 > NU1_NORMALISATION_TOL:
            msg = (
                f"{self.label}: published_Dq_cm1={self.published_Dq_cm1} implies "
                f"10Dq={10.0 * self.published_Dq_cm1} but nu1={nu1}; for d{self.d_count} "
                "nu1 == 10Dq exactly, so this value is not normalised to Dq"
            )
            raise ValueError(msg)


# ---------------------------------------------------------------------------
# The fixtures. Six carry published (Dq, B); two carry a required refusal.
#
# Numbers, bounds and band lists are unchanged from the parametrize lists that
# preceded this table -- only their provenance is now recorded beside them.
# ---------------------------------------------------------------------------

TEXTBOOK_PROVENANCE = "textbook worked example; primary source not recorded in this repo"

VANADIUM_III_AQUA = IonFixture(
    label="[V(H2O)6]3+",
    d_count=2,
    spin_state="high",
    geometry="Oh",
    band_labels=None,
    include_spin_forbidden=False,
    bands_cm1=(17200.0, 25600.0),
    source=TEXTBOOK_PROVENANCE,
    source_tier="textbook",
    # d2 has a 3T1g ground term, so nu1 != 10Dq and no arithmetic check on the
    # normalisation is available -- which is exactly why the field is stated.
    published_quantity="unknown",
    published_Dq_cm1=1860.0,
    published_B_cm1=665.0,
    published_C_cm1=None,
    estimator="unknown",
    degrees_of_freedom=0,
    expected_outcome="warns",
    expected_match="determined|degrees of freedom",
    tol_Dq=Tolerance("rel", 0.02),
    tol_B=Tolerance("rel", 0.05),
    max_rmse_cm1=1.0,
    closed_form_tol_Dq=None,  # the closed form must REFUSE d2; see the test below
    closed_form_tol_B=None,
    tolerance_reason=(
        "DOF = 0: two bands against two free parameters, so rmse ~ 0 BY CONSTRUCTION and "
        "carries no information about fit quality. max_rmse_cm1 pins that construction "
        "(Nelder-Mead stops at its own tolerance, so it is negligible rather than exactly "
        "zero), it is NOT a quality bound. Dq/B bounds measured: 1854.1 and 649.4."
    ),
)

CHROMIUM_III_AMMINE = IonFixture(
    label="[Cr(NH3)6]3+",
    d_count=3,
    spin_state="high",
    geometry="Oh",
    band_labels=None,
    include_spin_forbidden=False,
    bands_cm1=(21550.0, 28500.0, 46030.0),
    source=TEXTBOOK_PROVENANCE,
    source_tier="textbook",
    published_quantity="unknown",
    published_Dq_cm1=2155.0,
    published_B_cm1=661.0,
    published_C_cm1=None,
    # (nu2 + nu3 - 3 nu1)/15 = 658.7, not the published 661, so whatever the
    # source did it was not purely the closed form.
    estimator="unknown",
    degrees_of_freedom=1,
    expected_outcome="fit",
    expected_match=None,
    tol_Dq=Tolerance("rel", 0.02),
    tol_B=Tolerance("rel", 0.06),
    max_rmse_cm1=50.0,
    closed_form_tol_Dq=Tolerance("rel", 0.01),
    closed_form_tol_B=Tolerance("rel", 0.03),
    tolerance_reason=(
        "Closed-form Dq is tight because nu1 == 10Dq is exact for a 4A2g ground term; the "
        "closed-form B bound is looser because the published 661 is not itself the closed "
        "form (658.7). Least-squares measured (2155.8, 657.0), rmse 6.4."
    ),
)

CHROMIUM_III_AQUA = IonFixture(
    label="[Cr(H2O)6]3+",
    d_count=3,
    spin_state="high",
    geometry="Oh",
    band_labels=None,
    include_spin_forbidden=False,
    bands_cm1=(17000.0, 24000.0, 37000.0),
    source=TEXTBOOK_PROVENANCE,
    source_tier="textbook",
    published_quantity="unknown",
    published_Dq_cm1=1700.0,
    published_B_cm1=667.0,
    published_C_cm1=None,
    estimator="closed_form",  # (nu2 + nu3 - 3 nu1)/15 = 666.7 == the published 667
    degrees_of_freedom=1,
    expected_outcome="fit",
    expected_match=None,
    tol_Dq=Tolerance("rel", 0.02),
    tol_B=Tolerance("rel", 0.06),
    max_rmse_cm1=300.0,
    closed_form_tol_Dq=Tolerance("rel", 0.01),
    closed_form_tol_B=Tolerance("rel", 0.03),
    tolerance_reason=(
        "Least-squares measured (1683.5, 698.8), rmse 215.5. The 300 cm^-1 bound records that "
        "a single (Dq, B) describes these rounded band maxima poorly -- it is a measured "
        "property of the system, not a target loosened until the test passed."
    ),
)

CHROMIUM_III_MGO = IonFixture(
    label="MgO:Cr3+",
    d_count=3,
    spin_state="high",
    geometry="Oh",
    band_labels=None,
    include_spin_forbidden=False,
    bands_cm1=(16155.0, 22124.0, 35336.0),
    source="Brik, Z. Naturforsch. 60a, 437 (2005), quoting Powell (1998)",
    source_tier="secondary",
    # The worked example for this field: the source states explicitly that 1615
    # is Dq and NOT 10Dq, and 10 x 1615 = 16150 ~ the quoted 16155 4T2g band.
    published_quantity="Dq",
    published_Dq_cm1=1615.0,
    published_B_cm1=586.0,
    published_C_cm1=3249.0,  # non-default, unlike the other two Cr cases
    estimator="unknown",
    degrees_of_freedom=1,
    expected_outcome="fit",
    expected_match=None,
    tol_Dq=Tolerance("rel", 0.02),
    tol_B=Tolerance("rel", 0.06),
    max_rmse_cm1=150.0,
    closed_form_tol_Dq=Tolerance("rel", 0.01),
    closed_form_tol_B=Tolerance("rel", 0.03),
    tolerance_reason=(
        "Secondary source, and the published C = 3249 differs from the package default that "
        "the fit actually uses, which shifts B -- so the B bounds absorb a genuine model "
        "difference, not fitter noise. Least-squares measured (1624.8, 580.1), rmse 88.4."
    ),
)

NICKEL_II_AQUA = IonFixture(
    label="[Ni(H2O)6]2+",
    d_count=8,
    spin_state="high",
    geometry="Oh",
    band_labels=None,
    include_spin_forbidden=False,
    bands_cm1=(8500.0, 13800.0, 25300.0),
    source=(
        "band maxima: Chemistry LibreTexts / Doc Brown; reference parameters: Lever, "
        "Inorganic Electronic Spectroscopy, 2nd ed. (1984). See assets/uvvis/README.md."
    ),
    source_tier="textbook",
    published_quantity="unknown",
    published_Dq_cm1=850.0,
    published_B_cm1=907.0,
    published_C_cm1=None,
    # NON-NEGOTIABLE: (850, 907) is the CLOSED FORM, B = (25300 + 13800 - 3*8500)/15
    # = 906.67. Least-squares gives (833.5, 947.0) with a LOWER rmse. Both are
    # correct; they answer different questions.
    estimator="closed_form",
    degrees_of_freedom=1,
    expected_outcome="fit",
    expected_match=None,
    tol_Dq=Tolerance("rel", 0.03),
    tol_B=Tolerance("rel", 0.06),
    max_rmse_cm1=200.0,
    closed_form_tol_Dq=Tolerance("abs", 1.0),
    closed_form_tol_B=Tolerance("abs", 1.0),
    tolerance_reason=(
        "The published pair IS the closed form, so the closed-form bound is exact to 1 cm^-1. "
        "The least-squares bounds are relative and looser because least squares legitimately "
        "disagrees -- measured (833.5, 947.0), rmse 118.8. A naive fixture asserting 907 to "
        "1 cm^-1 against the least-squares result would FAIL a correct implementation."
    ),
)

NICKEL_II_AMMINE = IonFixture(
    label="[Ni(NH3)6]2+",
    d_count=8,
    spin_state="high",
    geometry="Oh",
    band_labels=None,
    include_spin_forbidden=False,
    bands_cm1=(10750.0, 17500.0, 28200.0),
    source=TEXTBOOK_PROVENANCE,
    source_tier="textbook",
    published_quantity="unknown",
    published_Dq_cm1=1075.0,
    published_B_cm1=897.0,
    published_C_cm1=None,
    estimator="closed_form",  # (28200 + 17500 - 3*10750)/15 = 896.7 == the published 897
    degrees_of_freedom=1,
    expected_outcome="fit",
    expected_match=None,
    tol_Dq=Tolerance("rel", 0.03),
    tol_B=Tolerance("rel", 0.06),
    max_rmse_cm1=150.0,
    closed_form_tol_Dq=Tolerance("abs", 1.0),
    closed_form_tol_B=Tolerance("abs", 1.0),
    tolerance_reason=(
        "Closed form again exact by construction (896.7), hence the 1 cm^-1 bound. "
        "Least-squares measured (1086.5, 867.7), rmse 97.8."
    ),
)

MANGANESE_II_AQUA = IonFixture(
    label="[Mn(H2O)6]2+",
    d_count=5,
    spin_state="high",
    geometry="Oh",
    band_labels=None,
    include_spin_forbidden=False,
    bands_cm1=(18800.0, 23100.0, 24900.0, 28000.0, 29700.0),
    source=TEXTBOOK_PROVENANCE,
    source_tier="textbook",
    published_quantity="unknown",
    published_Dq_cm1=None,
    published_B_cm1=None,
    published_C_cm1=None,
    estimator="unknown",
    degrees_of_freedom=3,
    expected_outcome="raises",
    expected_match="no spin-allowed d-d transitions",
    tol_Dq=None,
    tol_B=None,
    max_rmse_cm1=None,
    closed_form_tol_Dq=None,
    closed_form_tol_B=None,
    tolerance_reason=(
        "Not applicable: the correct answer is refusal, not a number. High-spin d5 has ZERO "
        "spin-allowed d-d transitions from 6A1g, so degrees_of_freedom is arithmetic only and "
        "means nothing here. Admissible under R1 because it asserts a refusal, not a diagram."
    ),
)

COBALT_III_AMMINE_HIGH_SPIN = IonFixture(
    label="[Co(NH3)6]3+ (high-spin regime)",
    d_count=6,
    spin_state="high",
    geometry="Oh",
    band_labels=None,
    include_spin_forbidden=False,
    bands_cm1=(21100.0, 29500.0),
    source=TEXTBOOK_PROVENANCE,
    source_tier="textbook",
    published_quantity="unknown",
    published_Dq_cm1=None,
    published_B_cm1=None,
    published_C_cm1=None,
    estimator="unknown",
    degrees_of_freedom=0,
    expected_outcome="raises",
    expected_match="under-determined|only 1 spin-allowed",
    tol_Dq=None,
    tol_B=None,
    max_rmse_cm1=None,
    closed_form_tol_Dq=None,
    closed_form_tol_B=None,
    tolerance_reason=(
        "Not applicable: high-spin d6 has exactly ONE spin-allowed band (= 10Dq), so B is "
        "unidentifiable and two peaks over-determine the system. Admissible under R1 because "
        "it asserts a refusal, not a comparison against a published d6 diagram."
    ),
)

#: Fixtures carrying a published (Dq, B) that this module compares against.
FIXTURES = (
    VANADIUM_III_AQUA,
    CHROMIUM_III_AMMINE,
    CHROMIUM_III_AQUA,
    CHROMIUM_III_MGO,
    NICKEL_II_AQUA,
    NICKEL_II_AMMINE,
)

#: Fixtures whose correct outcome is a structured refusal.
REFUSAL_FIXTURES = (MANGANESE_II_AQUA, COBALT_III_AMMINE_HIGH_SPIN)

CHROMIUM_III_CASES = (CHROMIUM_III_AMMINE, CHROMIUM_III_AQUA, CHROMIUM_III_MGO)
NICKEL_II_CASES = (NICKEL_II_AQUA, NICKEL_II_AMMINE)


def _ids(fixtures: tuple[IonFixture, ...]) -> list[str]:
    return [fx.label for fx in fixtures]


class TestFixtureAdmissibility:
    """The guards on IonFixture itself -- each one closes a trap that was hit.

    These are deliberately tests of the GUARD, not of the table: a loop over
    six admissible records would stay green if the guard were deleted, which is
    the tautology this module exists to avoid.
    """

    BASE = {
        "label": "probe",
        "d_count": 3,
        "spin_state": "high",
        "geometry": "Oh",
        "band_labels": None,
        "include_spin_forbidden": False,
        "bands_cm1": (17000.0, 24000.0, 37000.0),
        "source": "probe",
        "source_tier": "textbook",
        "published_quantity": "Dq",
        "published_Dq_cm1": 1700.0,
        "published_B_cm1": 667.0,
        "published_C_cm1": None,
        "estimator": "closed_form",
        "degrees_of_freedom": 1,
        "expected_outcome": "fit",
        "expected_match": None,
        "tol_Dq": Tolerance("rel", 0.02),
        "tol_B": Tolerance("rel", 0.06),
        "max_rmse_cm1": 300.0,
        "closed_form_tol_Dq": Tolerance("rel", 0.01),
        "closed_form_tol_B": Tolerance("rel", 0.03),
        "tolerance_reason": "probe",
    }

    def test_the_probe_itself_is_admissible(self) -> None:
        """Guard the guard: every rejection below must be caused by its own edit."""
        assert IonFixture(**self.BASE).label == "probe"

    def test_ten_dq_in_the_dq_field_is_rejected(self) -> None:
        """The factor-of-10 trap: 17000 is 10Dq, Dq is 1700."""
        with pytest.raises(ValueError, match="not normalised to Dq"):
            IonFixture(**{**self.BASE, "published_Dq_cm1": 17000.0})

    def test_missing_tolerance_reason_is_rejected(self) -> None:
        """A bound with no stated reason is a bound nobody can review."""
        with pytest.raises(ValueError, match="tolerance_reason is mandatory"):
            IonFixture(**{**self.BASE, "tolerance_reason": "   "})

    def test_degrees_of_freedom_must_match_the_band_count(self) -> None:
        """DOF is stated so a reader sees it, and checked so it cannot drift."""
        with pytest.raises(ValueError, match="degrees_of_freedom"):
            IonFixture(**{**self.BASE, "degrees_of_freedom": 3})

    def test_unknown_vocabulary_is_rejected(self) -> None:
        """Literal annotations are not enforced at runtime; this check is."""
        with pytest.raises(ValueError, match="published_quantity"):
            IonFixture(**{**self.BASE, "published_quantity": "delta"})

    @pytest.mark.parametrize("d_count", DIAGRAM_ERROR_CONFIGS)
    def test_r1_rejects_a_published_d5_or_d6_fit(self, d_count: int) -> None:
        """R1: the published d5/d6 diagrams carry a propagated error.

        Hormann & Shaw, J. Chem. Educ. 1987, 64, 918. Fitting against a value
        read off one of those diagrams validates the error, so a non-primary
        d5/d6 fixture with expected_outcome 'fit' must not exist.
        """
        with pytest.raises(ValueError, match="R1"):
            IonFixture(**{**self.BASE, "d_count": d_count})

    def test_band_labels_must_match_the_band_count(self) -> None:
        """One label per band, or the labels pair with the wrong bands.

        Observed red (95529fa): ``TypeError: IonFixture.__init__() got an unexpected
        keyword argument 'band_labels'``.
        """
        with pytest.raises(ValueError, match="band_labels"):
            IonFixture(**{**self.BASE, "band_labels": ("4_T_2", "4_T_1")})

    def test_spin_forbidden_needs_labels(self) -> None:
        """A spin-forbidden fit is only run labelled (the MCP surface's own rule).

        Observed red (95529fa): ``TypeError: ... unexpected keyword argument
        'include_spin_forbidden'``.
        """
        with pytest.raises(ValueError, match="include_spin_forbidden"):
            IonFixture(**{**self.BASE, "include_spin_forbidden": True})

    def test_labelled_nu1_is_found_by_label_not_by_minimum(self) -> None:
        """d3 with the 2E line below nu1: the normalisation reads the labelled 4T2.

        Observed red (95529fa): ``TypeError: ... unexpected keyword argument
        'band_labels'``; before labels, min(bands) = 2E made it ``not normalised to Dq``.
        """
        fx = IonFixture(
            **{
                **self.BASE,
                "bands_cm1": (17000.0, 24000.0, 37000.0, 14800.0),
                "degrees_of_freedom": 2,
                "band_labels": ("4_T_2", "4_T_1", "4_T_1", "2_E"),
                "include_spin_forbidden": True,
            }
        )
        assert fx.published_Dq_cm1 == 1700.0

    def test_r1_admits_a_refusal_for_the_same_configurations(self) -> None:
        """The escape hatch R1 names: a d5/d6 fixture that asserts a refusal."""
        assert {fx.d_count for fx in REFUSAL_FIXTURES} == set(DIAGRAM_ERROR_CONFIGS)
        assert all(fx.expected_outcome == "raises" for fx in REFUSAL_FIXTURES)


class TestVanadiumIII:
    """d2, 3T1g ground -- the NEGATIVE example: the closed form must refuse."""

    FIXTURE = VANADIUM_III_AQUA
    BANDS = list(FIXTURE.bands_cm1)

    def test_closed_form_refuses_degenerate_ground_term(self) -> None:
        with pytest.raises(ValueError, match="only valid for d3 and d8"):
            closed_form_dq_b(2, [*self.BANDS, 35000.0])

    def test_nu1_is_not_10dq_for_a_t1g_ground_term(self) -> None:
        """The reason the closed form cannot apply, stated as a measurement."""
        fx = self.FIXTURE
        c = float(DEFAULTS[2]["default_C"])
        _ground, candidates = transition_candidates(
            compute_point(2, fx.published_Dq_cm1, fx.published_B_cm1, c),
        )
        nu1 = candidates[0][0]
        assert abs(nu1 / 10.0 - fx.published_Dq_cm1) > 100.0, "nu1/10 must NOT recover Dq for d2"

    def test_fit_lands_in_the_t1g_ground_term(self) -> None:
        """The fit runs in the 3T1g regime; its (Dq, B) are no longer graded.

        Plan F, F4: the published 1860/665 are Figgis & Hitchman's values read off a TS
        diagram (graphical), which have no a-priori tolerance. This test used to assert
        them at 2 % / 5 % (measured 1854.1, 649.4); the distance is now reported by
        ``test_comparison_only_reports_delta``.
        """
        fx = self.FIXTURE
        assert graded_quantities(fx) == ()
        fit = fit_spectrum(2, self.BANDS)
        assert fit.ground_term == "3_T_1"

    def test_exactly_determined_fit_is_flagged(self) -> None:
        """2 bands and 2 free parameters => rmse == 0 carries NO information.

        Without a warning a caller reads rmse=0.0 as a perfect fit when it is
        only an exactly-determined system. The residual cannot be evidence of
        quality unless n_observed exceeds the number of free parameters.
        """
        fx = self.FIXTURE
        assert fx.degrees_of_freedom == 0
        assert fx.expected_outcome == "warns"
        fit = fit_spectrum(2, self.BANDS)
        # Negligible, not exactly zero: Nelder-Mead stops at its own tolerance.
        # The point is that it is negligible BY CONSTRUCTION, not by fit quality.
        assert fit.rmse_cm1 < fx.max_rmse_cm1
        assert any(re.search(fx.expected_match, w) for w in fit.warnings), (
            f"exactly-determined fit was not flagged; warnings={fit.warnings}"
        )


class TestChromiumIII:
    """d3, 4A2g ground -- the closed form is exact, across three complexes."""

    @pytest.mark.parametrize("fx", CHROMIUM_III_CASES, ids=_ids(CHROMIUM_III_CASES))
    def test_closed_form_reproduces_literature(self, fx: IonFixture) -> None:
        """B only where it is graded: [Cr(NH3)6]3+'s B is graphical (COMPARISON_ONLY)."""
        dq, b = closed_form_dq_b(fx.d_count, list(fx.bands_cm1))
        assert dq == fx.closed_form_tol_Dq.approx(fx.published_Dq_cm1), fx.label
        if "B" in graded_quantities(fx):
            assert b == fx.closed_form_tol_B.approx(fx.published_B_cm1), fx.label

    @pytest.mark.parametrize("fx", CHROMIUM_III_CASES, ids=_ids(CHROMIUM_III_CASES))
    def test_least_squares_agrees_with_literature(self, fx: IonFixture) -> None:
        fit = fit_spectrum(fx.d_count, list(fx.bands_cm1))
        assert fit.ground_term == "4_A_2", fx.label
        assert fit.Dq == fx.tol_Dq.approx(fx.published_Dq_cm1), f"{fx.label} Dq={fit.Dq}"
        if "B" in graded_quantities(fx):
            assert fx.tol_B.approx(fx.published_B_cm1) == fit.B, f"{fx.label} B={fit.B}"
        assert fit.rmse_cm1 < fx.max_rmse_cm1, f"{fx.label} rmse={fit.rmse_cm1}"

    def test_spectrochemical_series_ordering(self) -> None:
        """NH3 is a stronger field ligand than H2O."""
        ammine = fit_spectrum(3, list(CHROMIUM_III_AMMINE.bands_cm1))
        aqua = fit_spectrum(3, list(CHROMIUM_III_AQUA.bands_cm1))
        assert ammine.Dq > aqua.Dq


class TestManganeseII:
    """d5, 6A1g ground -- NOT FITTABLE. Correct behaviour is a structured error."""

    FIXTURE = MANGANESE_II_AQUA
    BANDS = list(FIXTURE.bands_cm1)

    def test_high_spin_d5_has_no_spin_allowed_transitions(self) -> None:
        """Why Mn(II) salts are pale pink: every d-d band is spin-forbidden."""
        _ground, candidates = transition_candidates(
            compute_point(5, 800.0, 860.0, 3850.0),
        )
        assert candidates == []

    def test_fit_refuses_rather_than_guessing(self) -> None:
        with pytest.raises(ValueError, match=self.FIXTURE.expected_match):
            fit_spectrum(5, self.BANDS)

    def test_escape_hatch_is_named_in_the_error(self) -> None:
        """An error must tell the caller what to do next."""
        with pytest.raises(ValueError, match="include_spin_forbidden"):
            fit_spectrum(5, self.BANDS)

    def test_escape_hatch_stays_in_the_high_spin_regime(self) -> None:
        """Must not drift into the 31-line-deep low-spin manifold to fake a fit."""
        fit = fit_spectrum(5, self.BANDS, include_spin_forbidden=True)
        assert fit.ground_term == "6_A_1"


class TestCobaltIII:
    """d6 -- fittable ONLY in the low-spin regime.

    [Co(NH3)6]3+ is a canonical Tanabe-Sugano teaching example: low-spin d6 with
    two spin-allowed bands 1A1g -> 1T1g and 1A1g -> 1T2g. High-spin d6 has a
    single spin-allowed band (= 10Dq), so B is unidentifiable there.

    The low-spin case is not in FIXTURES because it compares against no
    published (Dq, B) at all -- which is precisely what makes it admissible
    under R1, since a published d6 diagram never enters the assertion.
    """

    FIXTURE = COBALT_III_AMMINE_HIGH_SPIN
    BANDS = list(FIXTURE.bands_cm1)

    def test_high_spin_d6_is_under_determined(self) -> None:
        with pytest.raises(ValueError, match=self.FIXTURE.expected_match):
            fit_spectrum(6, self.BANDS, spin_state="high")

    def test_low_spin_d6_is_fittable(self) -> None:
        """Regression: the feasibility check counted candidates at the SEED.

        For these bands the seed lies below the spin crossover (Dq ~ 2110, where
        d6 is still high-spin), while the error reported the low-spin reference
        term's name. A perfectly valid low-spin fit was refused.
        """
        fit = fit_spectrum(6, self.BANDS, spin_state="low")
        assert fit.ground_term == "1_A_1"
        assert fit.Dq > 2000.0
        assert fit.B > 0.0

    def test_low_spin_reference_has_many_candidates(self) -> None:
        """Sanity: the low-spin manifold is rich, so the refusal was not physical."""
        b = float(DEFAULTS[6]["default_B"])
        c = float(DEFAULTS[6]["default_C"])
        assert reference_ground_term(6, b, c, "low") == "1_A_1"
        _ground, candidates = transition_candidates(compute_point(6, 3000.0, b, c))
        assert len(candidates) > 10


class TestNickelII:
    """d8, 3A2g ground -- closed form exact; the reference worked example."""

    @pytest.mark.parametrize("fx", NICKEL_II_CASES, ids=_ids(NICKEL_II_CASES))
    def test_closed_form_reproduces_literature(self, fx: IonFixture) -> None:
        """The published pair IS the closed form, not a least-squares fit.

        For [Ni(H2O)6]2+: B = (25300 + 13800 - 3*8500)/15 = 906.67.
        """
        assert fx.estimator == "closed_form"
        dq, b = closed_form_dq_b(fx.d_count, list(fx.bands_cm1))
        assert dq == fx.closed_form_tol_Dq.approx(fx.published_Dq_cm1), fx.label
        assert b == fx.closed_form_tol_B.approx(fx.published_B_cm1), fx.label

    @pytest.mark.parametrize("fx", NICKEL_II_CASES, ids=_ids(NICKEL_II_CASES))
    def test_least_squares_agrees_with_literature(self, fx: IonFixture) -> None:
        fit = fit_spectrum(fx.d_count, list(fx.bands_cm1))
        assert fit.ground_term == "3_A_2", fx.label
        assert fit.Dq == fx.tol_Dq.approx(fx.published_Dq_cm1), f"{fx.label} Dq={fit.Dq}"
        assert fx.tol_B.approx(fx.published_B_cm1) == fit.B, f"{fx.label} B={fit.B}"
        assert fit.rmse_cm1 < fx.max_rmse_cm1, f"{fx.label} rmse={fit.rmse_cm1}"

    def test_spectrochemical_series_ordering(self) -> None:
        """NH3 is a stronger field ligand than H2O."""
        ammine = fit_spectrum(8, list(NICKEL_II_AMMINE.bands_cm1))
        aqua = fit_spectrum(8, list(NICKEL_II_AQUA.bands_cm1))
        assert ammine.Dq > aqua.Dq


# ---------------------------------------------------------------------------
# JCE 2023: García Rojas & Pérez Torres, J. Chem. Educ. 2023, 100, 251-258.
#
# Read from the committed tables (audit/jce2023/), never retyped: Table 1 gives
# the bands with their printed assignments, Table 2 the parameters. Only the
# "reported" columns are used -- the "graphical" ones were read off a TS diagram
# (R1). The primaries (the paper's refs 1-39) are not resolved here, so every
# record is source_tier="secondary" with estimator="unknown".
#
# Graded forward first: the oracle's bands at the published (Dq, B, C) are
# compared with Table 1. A source that does not reproduce its own bands is a
# finding about the source, not about the fitter, and gets no inverse fixture.
# Only the self-consistent sources are then fitted, at tolerances propagated
# from the band uncertainty through the oracle's Jacobian -- set before any fit
# ran, never read off one.
# ---------------------------------------------------------------------------


JCE_DIR = Path(
    os.environ.get(
        "TANABESUGANO_JCE_DIR", Path(__file__).resolve().parents[3] / "audit" / "jce2023"
    )
)
"""The JCE audit tables. Not shipped in the wheel; the env var points a test at a missing one."""
JCE_SKIP = pytest.mark.skipif(
    not JCE_DIR.exists(), reason="audit/jce2023 is not shipped in the wheel"
)
SourceStatus = Literal["observed", "calc", "CT", "graphical", "assumed", "unverified"]
UNGRADABLE_STATUS = ("calc", "CT", "unverified")
"""A value with one of these statuses in the original is never graded against."""
PRIMARY_QUANTITY = re.compile(r"band:\d_[A-Z](_\d)?#\d+|Dq|B|C")
JCE_SOURCE = (
    "García Rojas & Pérez Torres, J. Chem. Educ. 2023, 100, 251-258, Tables 1-2 "
    "(reported columns); primary refs not resolved"
)
BAND_SIGMA = 0.01
"""1-sigma uncertainty of a quoted band maximum, relative: d-d bands run 2000-4000 cm^-1
wide and their maxima are rarely located better than about 1 % (the scale behind
``BAND_RESOLUTION_CM1`` = 100 cm^-1 at a ~10 000 cm^-1 band)."""
APPROX_BAND_SIGMA = 0.03
"""The same for a band the source marks as approximate (a shoulder or an estimate)."""
COVERAGE = 2.0
"""Tolerances and the forward consistency test are 2-sigma."""
RATIO_ROUNDING = 0.0005
"""Table 2 prints Dq/B and C/B to three decimals; their rounding, relative, in quadrature."""
B_GRADE_LIMIT = 0.05
"""Above this propagated 2-sigma, B is not determined by the bands and is not graded."""
HUND_MULTIPLICITY = {2: 3, 3: 4, 4: 5, 7: 4, 8: 3}
"""High-spin ground multiplicity; an oracle ground below it means the source is low-spin."""


@dataclass(frozen=True, slots=True)
class PrimarySource:
    """One value as the original paper (a JCE 2023 reference) reports it."""

    system: str
    quantity: str
    """``band:<term>#<index>`` (0-based, as ``JceRecord.levels``), ``Dq``, ``B`` or ``C``."""
    value: float | None
    unit: str
    ref: str
    """The reference number in ``jce2023_references.csv``; books have no DOI, so this is the key."""
    doi: str
    page_or_table: str
    status: SourceStatus
    note: str


def _read_jce_csv(name: str) -> list[dict[str, str]]:
    with (JCE_DIR / name).open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def primary_sources() -> tuple[PrimarySource, ...]:
    """Every row of ``audit/jce2023/primary_sources.csv`` (from SOURCE-CHECK.md)."""
    statuses: tuple[SourceStatus, ...] = get_args(SourceStatus)
    out: list[PrimarySource] = []
    for row in _read_jce_csv("primary_sources.csv"):
        status = next((s for s in statuses if s == row["status"]), None)
        if status is None:
            msg = f"{row['system']} {row['quantity']}: unknown status {row['status']!r}"
            raise ValueError(msg)
        out.append(
            PrimarySource(
                system=row["system"],
                quantity=row["quantity"],
                value=float(row["value"]) if row["value"] else None,
                unit=row["unit"],
                ref=row["ref"],
                doi=row["doi"],
                page_or_table=row["page_or_table"],
                status=status,
                note=row["note"],
            )
        )
    return tuple(out)


def _band_quantity(band: dict[str, str]) -> str:
    """A Table 1 row's band as a ``primary_sources.csv`` quantity, ``band:3_T_1#1``."""
    key = _jce_term_key(band["multiplicity"], band["irrep"])
    return f"band:{key}#{int(band['ordinal'] or 1) - 1}"


def _jce_term_key(multiplicity: str, irrep: str) -> str:
    """Table 1's (3, T2) -> ``3_T_2``; (1, E) -> ``1_E``."""
    return "_".join([multiplicity, irrep[0], *([irrep[1:]] if len(irrep) > 1 else [])])


def oracle_level(d_count: int, dq: float, b: float, c: float, key: str, index: int) -> float:
    """Energy above the ground level of the ``index``-th level of ``key``, from the oracle."""
    return float(sorted(relative_term_levels(d_count, dq, b, c)[key])[index])


def oracle_jacobian(
    d_count: int, dq: float, b: float, c: float, levels: tuple[tuple[str, int], ...]
) -> np.ndarray:
    """d(level energy) / d(Dq, B) at fixed C, central differences on the oracle only."""
    step = 1.0
    rows = []
    for key, index in levels:
        d_dq = oracle_level(d_count, dq + step, b, c, key, index) - oracle_level(
            d_count, dq - step, b, c, key, index
        )
        d_b = oracle_level(d_count, dq, b + step, c, key, index) - oracle_level(
            d_count, dq, b - step, c, key, index
        )
        rows.append((d_dq / (2 * step), d_b / (2 * step)))
    return np.array(rows)


@dataclass(frozen=True, slots=True)
class JceRecord:
    """One JCE system with one band set: its spin-allowed bands, or all of them."""

    record_id: str
    system: str
    d_count: int
    spin_state: SpinState
    Dq: float
    B: float
    C: float
    bands_cm1: tuple[float, ...]
    levels: tuple[tuple[str, int], ...]
    approx: tuple[bool, ...]
    spin_forbidden: bool
    source_file: Literal["jce2023_table1_bands.csv", "primary_sources.csv"]
    """``primary_sources.csv`` when any value was replaced, or any band dropped, from it."""

    @property
    def sigmas(self) -> np.ndarray:
        """1-sigma of each band, in cm^-1."""
        rel = [APPROX_BAND_SIGMA if a else BAND_SIGMA for a in self.approx]
        return np.array(rel) * np.array(self.bands_cm1)

    def values(self) -> tuple[tuple[str, float], ...]:
        """Every value the record uses, keyed as ``primary_sources.csv`` keys it."""
        bands = tuple(
            (f"band:{key}#{index}", value)
            for (key, index), value in zip(self.levels, self.bands_cm1, strict=True)
        )
        return (*bands, ("Dq", self.Dq), ("B", self.B), ("C", self.C))

    @property
    def labels(self) -> tuple[str, ...]:
        """Bare term keys, as ``fit_spectrum(band_labels=...)`` takes them."""
        return tuple(key for key, _index in self.levels)


def jce_records() -> tuple[JceRecord, ...]:
    """Every admissible JCE record: d != 5, 6 with reported Dq, Dq/B and C/B.

    The selection reads Table 2 only, never a fit or an audit verdict. Each system
    gives a spin-allowed record and, when Table 1 lists a spin-forbidden band, an
    "all" record with every band.

    Where ``primary_sources.csv`` has a row for a system and quantity, the original
    wins: its value replaces the printed one, and a band it reports as ``calc``, ``CT``
    or ``unverified`` is dropped. Without the audit directory (a wheel) there are none.
    """
    if not JCE_DIR.exists():
        return ()
    params = _read_jce_csv("jce2023_table2_parameters.csv")
    bands = _read_jce_csv("jce2023_table1_bands.csv")
    primary = {(p.system, p.quantity): p for p in primary_sources()}
    out: list[JceRecord] = []
    for row in params:
        if not (row["Dq_cm1"] and row["Dq_over_B_reported"] and row["C_over_B_reported"]):
            continue
        rows = [b for b in bands if b["system"] == row["system"]]
        d_count = int(rows[0]["block"][1]) if rows else 0
        if not rows or d_count in DIAGRAM_ERROR_CONFIGS:
            continue
        dq = float(row["Dq_cm1"])
        b_val = dq / float(row["Dq_over_B_reported"])
        c_val = float(row["C_over_B_reported"]) * b_val
        printed = {"Dq": dq, "B": b_val, "C": c_val}
        chosen_params = {
            q: _primary_value(primary, row["system"], q, v) for q, v in printed.items()
        }
        dq, b_val, c_val = (chosen_params[q] for q in ("Dq", "B", "C"))
        params_changed = chosen_params != printed
        ground = min(
            (
                (float(min(v)), k)
                for k, v in relative_term_levels(d_count, dq, b_val, c_val).items()
            ),
        )[1]
        ground_mult = ground.split("_", 1)[0]
        spin: SpinState = "low" if int(ground_mult) < HUND_MULTIPLICITY[d_count] else "high"
        # (value, level, approx, read from primary_sources.csv); a dropped band keeps value None.
        entries: list[tuple[float | None, tuple[str, int], bool, bool]] = []
        for b in rows:
            level = (_jce_term_key(b["multiplicity"], b["irrep"]), int(b["ordinal"] or 1) - 1)
            printed_band = float(b["wavenumber_cm1"])
            src = primary.get((row["system"], _band_quantity(b)))
            if src is not None and src.status in UNGRADABLE_STATUS:
                entries.append((None, level, False, True))
                continue
            value = _primary_value(primary, row["system"], _band_quantity(b), printed_band)
            entries.append((value, level, b["approx"] == "True", value != printed_band))
        allowed = [e for e in entries if e[1][0].split("_", 1)[0] == ground_mult]
        variants = [("allowed", allowed, False)]
        if any(e[0] is not None for e in entries if e not in allowed):
            variants.append(("all", entries, True))
        for tag, chosen, sf in variants:
            kept = [(v, lvl, ap) for v, lvl, ap, _ in chosen if v is not None]
            from_primary = params_changed or any(e[3] for e in chosen)
            out.append(
                JceRecord(
                    record_id=f"{row['system']} [{tag}]",
                    system=row["system"],
                    d_count=d_count,
                    spin_state=spin,
                    Dq=dq,
                    B=b_val,
                    C=c_val,
                    bands_cm1=tuple(v for v, _, _ in kept),
                    levels=tuple(lvl for _, lvl, _ in kept),
                    approx=tuple(ap for _, _, ap in kept),
                    spin_forbidden=sf,
                    source_file="primary_sources.csv"
                    if from_primary
                    else "jce2023_table1_bands.csv",
                )
            )
    return tuple(out)


def _primary_value(
    primary: dict[tuple[str, str], PrimarySource], system: str, quantity: str, printed: float
) -> float:
    """The original's value where it reports one this record may use, else the printed one."""
    src = primary.get((system, quantity))
    if src is None or src.value is None or src.status in UNGRADABLE_STATUS:
        return printed
    return src.value


def forward_consistent(record: JceRecord) -> bool:
    """Does the source reproduce every one of its bands within 2-sigma at its own parameters?"""
    computed = np.array(
        [
            oracle_level(record.d_count, record.Dq, record.B, record.C, key, index)
            for key, index in record.levels
        ]
    )
    return bool(np.all(np.abs(computed - np.array(record.bands_cm1)) <= COVERAGE * record.sigmas))


SELF_CONSISTENT = frozenset(
    {
        "[Cr(H2O)6]3+ [allowed]",
        "[Cr(H2O)6]3+ [all]",
        "KZnClSO4·3H2O:Cr3+ [allowed]",
        "Al2O3:Cr3+ [allowed]",
        "Al2O3:Cr3+ [all]",
        "K3Cr(CN)6 [allowed]",
        "[Mn(CN)6]3- [allowed]",
        "[Mn(CN)6]3- [all]",
        "AgCl:Ni2+ [allowed]",
        "MgO:Ni2+ [allowed]",
        "LiGa5O8:Ni2+ [allowed]",
        "LiGa5O8:Ni2+ [all]",
    }
)
"""The records whose source reproduces its own bands within 2-sigma, from the oracle only.

Pinned from the forward check before any inverse fit was run. Outside it: Al2O3:V3+
(nu1, nu2 at -2.8 and -2.6 sigma), the four d7 Co(II) sources (a band off by 4-12
sigma; CoSiF6 now on the original's observed 4A2 and 4T1(P), its 4A2 at +11.8), [Ni(H2O)6]2+
(nu2 +6 sigma), and the "all" records of KZnClSO4:Cr3+, K3Cr(CN)6 and AgCl:Ni2+ (their
spin-forbidden line at +6.3, -4.6 and -2.4 sigma: C/B does not fit it).

Re-pinned in plan F Task 4, when records began reading ``primary_sources.csv``, from the
same forward check: 13 -> 12. MgO:Ni2+ [all] no longer exists -- its only spin-forbidden
band, 1E ~13670, is not a separate observed band in the original. K3Cr(CN)6 [all] moved
from -7.6 to -4.6 sigma on the original's C = 2800 and stays outside."""


def oracle_tolerances(record: JceRecord) -> tuple[float, float]:
    """2-sigma relative (Dq, B) bounds from the band sigmas through the oracle Jacobian.

    C is held at the published value, as the inverse fit holds it. Rounding of the
    published Dq (to 1 cm^-1) and of Dq/B (to 1e-3) is added in quadrature.
    """
    jac = oracle_jacobian(record.d_count, record.Dq, record.B, record.C, record.levels)
    weighted = jac / record.sigmas[:, None]
    sd = np.sqrt(np.diag(np.linalg.inv(weighted.T @ weighted)))
    tol_dq = float(np.hypot(COVERAGE * sd[0] / record.Dq, 0.5 / record.Dq))
    tol_b = float(np.hypot(COVERAGE * sd[1] / record.B, RATIO_ROUNDING))
    return tol_dq, tol_b


def jce_fixture(record: JceRecord) -> IonFixture:
    """The inverse record, with every outcome and bound fixed by rule before any fit.

    DOF <= 0 -> "warns" (the fit is exactly determined and must say so); otherwise
    "fit". The rmse bound is 2-sigma of the band uncertainty. Construction applies
    every IonFixture guard, the 1 % nu1 == 10Dq normalisation included.
    """
    tol_dq, tol_b = oracle_tolerances(record)
    dof = len(record.bands_cm1) - FREE_PARAMETERS
    rms_sigma = float(np.sqrt(np.mean(record.sigmas**2)))
    b_note = (
        "B is graded"
        if tol_b <= B_GRADE_LIMIT
        else f"B is NOT graded: {100 * tol_b:.1f} % > {100 * B_GRADE_LIMIT:.0f} %, these bands "
        "do not determine it"
    )
    return IonFixture(
        label=f"JCE2023 {record.record_id}",
        d_count=record.d_count,
        spin_state=record.spin_state,
        geometry="Oh",
        band_labels=record.labels,
        include_spin_forbidden=record.spin_forbidden,
        bands_cm1=record.bands_cm1,
        source=JCE_SOURCE,
        source_tier="secondary",
        published_quantity="Dq",
        published_Dq_cm1=record.Dq,
        published_B_cm1=record.B,
        published_C_cm1=record.C,
        estimator="unknown",
        degrees_of_freedom=dof,
        expected_outcome="warns" if dof <= 0 else "fit",
        expected_match="determined|degrees of freedom" if dof <= 0 else None,
        tol_Dq=Tolerance("rel", tol_dq),
        tol_B=Tolerance("rel", tol_b),
        max_rmse_cm1=COVERAGE * rms_sigma,
        closed_form_tol_Dq=None,
        closed_form_tol_B=None,
        tolerance_reason=(
            f"Propagated, not measured: band sigma {100 * BAND_SIGMA:.0f} % "
            f"({100 * APPROX_BAND_SIGMA:.0f} % if approximate) through the oracle Jacobian "
            f"at the published (Dq, B, C), 2-sigma: Dq {100 * tol_dq:.2f} %, "
            f"B {100 * tol_b:.2f} %; {b_note}. A separate source claim from any other "
            "record of the same ion."
        ),
    )


JCE_SOURCE_ERRATA: dict[str, str] = {
    "[Mn(CN)6]3- [allowed]": (
        "Alexander & Gray 1968 (JCE ref 29) assign 31100 cm^-1 to charge transfer "
        "(t1u -> t2g), not to 3E; without it one band is left for two parameters"
    ),
    "[Mn(CN)6]3- [all]": (
        "as [allowed]: 31100 cm^-1 is charge transfer in the original; what is left is "
        "two bands for two parameters, and JCE's (Dq, B, C) were derived with the CT band in"
    ),
}
"""Self-consistent records whose band set the original paper contradicts: no inverse fixture.

From a check of the JCE tables against 18 of the 40 originals (2026-11-25). A source
can reproduce its own numbers (forward) and still pair a band with the wrong level;
fitting it would certify the mispairing. Since plan F Task 4 the record drops the CT band
(``primary_sources.csv`` marks it ``CT``), so the erratum now names what is left. K3Cr(CN)6
[allowed] stays: it reads the original's C = 2800 (C/B 5.77, not JCE's 5.563), and its d3
quartet bands do not depend on C."""


def _jce_inverse() -> tuple[tuple[IonFixture, ...], dict[str, str]]:
    """Inverse records for the self-consistent sources, and those the nu1 guard refuses."""
    built: list[IonFixture] = []
    refused: dict[str, str] = {}
    for record in jce_records():
        if record.record_id not in SELF_CONSISTENT or record.record_id in JCE_SOURCE_ERRATA:
            continue
        try:
            built.append(jce_fixture(record))
        except ValueError as exc:
            if "not normalised to Dq" not in str(exc):
                raise
            refused[record.record_id] = str(exc)
    return tuple(built), refused


JCE_FIXTURES, JCE_UNNORMALISED = _jce_inverse()

COMPARISON_SOURCES: dict[str, tuple[str, str]] = {
    "[V(H2O)6]3+": ("[V(H2O)6]3+", "Dq"),
    "[Cr(NH3)6]3+": ("[Cr(NH3)6]3+", "B"),
    "JCE2023 [Cr(H2O)6]3+ [allowed]": ("[Cr(H2O)6]3+", "Dq"),
    "JCE2023 [Cr(H2O)6]3+ [all]": ("[Cr(H2O)6]3+", "Dq"),
    "JCE2023 MgO:Ni2+ [allowed]": ("MgO:Ni2+", "Dq"),
    "JCE2023 CoCl2 [allowed]": ("CoCl2", "Dq"),
    "JCE2023 KCoF3 [allowed]": ("KCoF3", "Dq"),
    "JCE2023 CoSiF6·6H2O [allowed]": ("CoSiF6·6H2O", "Dq"),
    "JCE2023 [Ni(H2O)6]2+ [allowed]": ("[Ni(H2O)6]2+", "Dq"),
}
"""Fixture or record id -> the ``primary_sources.csv`` row that says why it is comparison-only.

Declared, not derived: ``test_no_graded_fixture_rests_on_a_graphical_value`` derives the
graphical and assumed values from the data and requires each to be declared here, and the
grading tests read only this. The keys hold in a wheel, where the CSV is absent."""


def _comparison_reason(system: str, quantity: str) -> str:
    if not JCE_DIR.exists():
        return f"{system} {quantity}: see audit/jce2023/primary_sources.csv (not shipped)"
    row = next(p for p in primary_sources() if (p.system, p.quantity) == (system, quantity))
    return f"{system} {quantity} {row.status}: {row.note}"


COMPARISON_ONLY: dict[str, str] = {
    key: _comparison_reason(*where) for key, where in COMPARISON_SOURCES.items()
}
"""Fixture or record id -> why its printed (Dq, B) are comparison-only, from the primary note.

A comparison-only id is never graded on its printed values; it reports its distance
(``test_comparison_only_reports_delta``). A literature fixture whose published Dq already
is nu1/10 of its own observed band keeps that Dq graded ([Cr(NH3)6]3+, 2155); its B is not.
[Ni(NH3)6]2+ (F1b) has no JCE record -- Table 2 prints no C/B for it -- so its F1b coverage
is the search test alone."""


def graded_quantities(fx: IonFixture) -> tuple[str, ...]:
    """Which of (Dq, B) a grading test may assert against this fixture's published values."""
    if fx.label not in COMPARISON_ONLY:
        return ("Dq", "B")
    return ("Dq",) if nu1_normalised(fx) else ()


F1B_SYSTEMS = (
    "[Cr(H2O)6]3+",
    "CoCl2",
    "KCoF3",
    "CoSiF6·6H2O",
    "[Ni(H2O)6]2+",
    "[Ni(NH3)6]2+",
)
"""The six JCE default-C rows the fit-path audit left silent (plan F, F1b): C does not move
their spin-allowed levels, the bands are assigned right, and the published point fits worse
than the fit does (F1b-mechanism.md)."""


def printed_allowed_bands(system: str) -> tuple[int, list[float]]:
    """d-count and the spin-allowed Table 1 bands of a system, as JCE printed them."""
    rows = [b for b in _read_jce_csv("jce2023_table1_bands.csv") if b["system"] == system]
    d_count = int(rows[0]["block"][1])
    mult = str(HUND_MULTIPLICITY[d_count])
    return d_count, sorted(float(b["wavenumber_cm1"]) for b in rows if b["multiplicity"] == mult)


def f1b_box(bands: list[float]) -> tuple[tuple[float, float], tuple[float, float]]:
    """The (Dq, B) box both the fit and the oracle search use: the default band span of Dq
    (0.5 % to 25 % of the highest band) and the default B bounds.

    Passed to the fit explicitly so the two search the same box. For these six band sets
    the band span contains the default seed span, so it is the box the audit rows used.
    """
    top = max(bands)
    return (0.005 * top, 0.25 * top), (200.0, 1500.0)


def graded_fixtures() -> tuple[IonFixture, ...]:
    """Every fixture graded against a published (Dq, B): the literature cases and JCE."""
    return (*(fx for fx in FIXTURES if fx.expected_outcome != "raises"), *JCE_FIXTURES)


def nu1_normalised(fx: IonFixture) -> bool:
    """Is a d3/d8 fixture's Dq exactly nu1/10 of its own nu1 band?"""
    if fx.d_count not in CLOSED_FORM_CONFIGS or fx.published_Dq_cm1 is None:
        return False
    nu1 = min(fx.bands_cm1)
    if fx.band_labels is not None and NU1_LABEL[fx.d_count] in fx.band_labels:
        nu1 = fx.bands_cm1[fx.band_labels.index(NU1_LABEL[fx.d_count])]
    return abs(fx.published_Dq_cm1 - nu1 / 10.0) <= 0.05


def fixture_primary_system(fx: IonFixture) -> str | None:
    """The JCE system whose original this fixture's values come from, if any.

    A JCE fixture names it. A literature fixture traces to one only when its label is a
    JCE system AND it carries every spin-allowed Table 1 band of that system (to 1 cm^-1):
    a label alone would tie the textbook [Cr(H2O)6]3+ (17000/24000/37000) to TS 1954.
    """
    if fx.label.startswith("JCE2023 "):
        return fx.label.removeprefix("JCE2023 ").rsplit(" [", 1)[0]
    rows = [b for b in _read_jce_csv("jce2023_table1_bands.csv") if b["system"] == fx.label]
    if not rows:
        return None
    _d, allowed = printed_allowed_bands(fx.label)
    if all(any(abs(a - b) <= 1.0 for b in fx.bands_cm1) for a in allowed):
        return fx.label
    return None


JCE_FINDINGS: dict[str, str] = {}
"""Inverse records that miss their a-priori bound: ``"E4-F<n>: <what, by how much>"``.

A miss is a finding about the fitter (the source already passed forward), so it is
recorded here as a strict xfail and never answered by widening a bound."""


@JCE_SKIP
class TestJce2023Oracle:
    """T1a checks of the JCE helpers themselves, against nu1 == 10Dq."""

    @pytest.mark.parametrize(("d_count", "key"), [(3, "4_T_2"), (8, "3_T_2")])
    def test_jacobian_of_nu1_is_ten_dq(self, d_count: int, key: str) -> None:
        """D nu1 / d Dq == 10 and d nu1 / d B == 0 exactly, for d3 and d8.

        Observed red (95529fa): ``NameError: name 'oracle_jacobian' is not defined``.
        """
        jac = oracle_jacobian(d_count, 1700.0, 700.0, 2800.0, ((key, 0),))
        assert jac[0][0] == pytest.approx(10.0, abs=1e-6)
        assert jac[0][1] == pytest.approx(0.0, abs=1e-6)

    @pytest.mark.parametrize("system", F1B_SYSTEMS)
    def test_f1b_search_reaches_oracle_minimum(self, system: str) -> None:
        """The fitter's point is as good as the oracle's global minimum over the same box.

        F1b: six JCE band sets whose published point fits worse than our fit. Before
        calling that a reference problem, the search itself is checked: a brute grid
        (1 % steps) over the fit's own (Dq, B) box, Hungarian assignment on the oracle's
        levels, least-squares polish -- no package code. Green on arrival: this is
        search coverage, not the red of a fix.

        Sensitivity (2937721): with ``fit_spectrum`` replaced by one returning the
        published point, KCoF3 fails with ``KCoF3: fit 582.9 > oracle minimum 41.1 + 1``.
        """
        d_count, bands = printed_allowed_bands(system)
        box = f1b_box(bands)
        fit = fit_spectrum(
            d_count, bands, None, spin_state="high", dq_bounds=box[0], b_bounds=box[1]
        )
        mult = HUND_MULTIPLICITY[d_count]
        at_fit = oracle_rmse(d_count, bands, fit.Dq, fit.B, fit.C, mult)
        best = oracle_global_min(d_count, bands, fit.C, box[0], box[1], mult)
        assert at_fit <= best.rmse_cm1 + 1.0, (
            f"{system}: fit {at_fit:.1f} > oracle minimum {best.rmse_cm1:.1f} + 1 "
            f"(at Dq {best.Dq:.1f}, B {best.B:.1f})"
        )

    def test_zno_td_no_so_value(self) -> None:
        """ZnO:Ni2+ (Td d8): the no-spin-orbit reference is (515.13, 790.09), oracle only.

        4400 -> 3T2 and 15500 -> 3T1(P) of d8 at -Dq, solved exactly; triplet levels of
        d8 do not depend on C. The published 405/795 assume ~900 cm^-1 of spin-orbit
        stabilisation and stay comparison-only. Green on arrival: it pins the reference
        a Td fit is graded against later.
        """

        def residual(x: np.ndarray) -> list[float]:
            levels = relative_term_levels(8, -x[0], x[1], 4.36 * x[1])
            return [min(levels["3_T_2"]) - 4400.0, sorted(levels["3_T_1"])[1] - 15500.0]

        dq, b = fsolve(residual, [405.0, 795.0])
        assert dq == pytest.approx(515.13, abs=0.05)
        assert b == pytest.approx(790.09, abs=0.05)
        status = {(p.system, p.quantity): p.status for p in primary_sources()}
        assert status[("ZnO:Ni2+", "Dq")] == "assumed"
        assert status[("ZnO:Ni2+", "B")] == "assumed"


@JCE_SKIP
class TestJce2023Source:
    """Forward: does each source reproduce its own bands at its own parameters?"""

    def test_self_consistent_sources_are_pinned(self) -> None:
        """The split is pinned from the oracle alone, before any inverse fit ran.

        Observed red (95529fa): ``NameError: name 'jce_records' is not defined``.
        """
        live = {r.record_id for r in jce_records() if forward_consistent(r)}
        assert live == SELF_CONSISTENT

    def test_primary_sources_schema(self) -> None:
        """Every row cites a reference of the paper, a place in it, a unit and a status.

        Books have no DOI, so a row is tied to ``jce2023_references.csv`` by its ``ref``
        number, and its DOI must then be that reference's DOI (empty for a book).

        Observed red (602efa2): ``NameError: name '_read_jce_csv' is not defined``; with the
        loader in and the CSV moved aside, ``FileNotFoundError: ... primary_sources.csv``.
        """
        refs = {r["ref"]: r for r in _read_jce_csv("jce2023_references.csv")}
        table1 = {
            (b["system"], _band_quantity(b)) for b in _read_jce_csv("jce2023_table1_bands.csv")
        }
        systems = {s for s, _ in table1} | {
            r["system"] for r in _read_jce_csv("jce2023_table2_parameters.csv")
        }
        rows = primary_sources()
        assert rows
        bad: list[str] = []
        for row in rows:
            where = f"{row.system} {row.quantity}"
            if row.ref not in refs:
                bad.append(f"{where}: ref {row.ref!r} is not in jce2023_references.csv")
            elif row.doi != refs[row.ref]["doi"]:
                bad.append(
                    f"{where}: doi {row.doi!r} is not ref {row.ref}'s {refs[row.ref]['doi']!r}"
                )
            if not (row.page_or_table and row.unit):
                bad.append(f"{where}: no page_or_table or unit")
            if row.status not in get_args(SourceStatus):
                bad.append(f"{where}: status {row.status!r}")
            if not PRIMARY_QUANTITY.fullmatch(row.quantity):
                bad.append(f"{where}: quantity is not band:<term>#<index>, Dq, B or C")
            if row.system not in systems:
                bad.append(f"{where}: system is in neither JCE table")
            elif row.quantity.startswith("band:") and (row.system, row.quantity) not in table1:
                bad.append(f"{where}: Table 1 lists no such band for this system")
            if row.value is None and row.status not in ("unverified", "assumed"):
                bad.append(f"{where}: no value, but status {row.status!r}")
        keys = [(r.system, r.quantity) for r in rows]
        bad.extend(f"{s} {q}: duplicated" for s, q in set(keys) if keys.count((s, q)) > 1)
        assert not bad, "\n".join(bad)

    def test_no_graded_fixture_rests_on_a_graphical_value(self) -> None:
        """A graded Dq or B is observed, or (d3/d8 Dq) nu1/10 of the observed band.

        A value its original read off a diagram (``graphical``) or derived under an
        assumption (``assumed``) has no a-priori tolerance, so it is comparison-only:
        the fixture must be in COMPARISON_ONLY. When a source's Dq is not observed, its
        B came from the same derivation and is not either.

        Observed red (2937721, B rows added, COMPARISON_ONLY empty): ``[V(H2O)6]3+ Dq:
        graphical``, ``[V(H2O)6]3+ B: graphical`` and ``[Cr(NH3)6]3+ B: graphical``.
        """
        primary = {(p.system, p.quantity): p for p in primary_sources()}
        bad: list[str] = []
        for fx in graded_fixtures():
            system = fixture_primary_system(fx)
            if system is None or fx.label in COMPARISON_ONLY:
                continue
            dq_src = primary.get((system, "Dq"))
            for quantity in ("Dq", "B"):
                src = primary.get((system, quantity))
                if quantity == "B" and (src is None or src.status == "observed"):
                    src = dq_src
                if src is None or src.status == "observed":
                    continue
                if quantity == "Dq" and nu1_normalised(fx):
                    continue
                bad.append(f"{fx.label} {quantity}: {src.status} ({src.note})")
        assert not bad, "\n".join(bad)

    def test_every_graded_record_uses_no_calc_or_unverified_value(self) -> None:
        """A graded record never rests on a value its original does not report as measured.

        Graded is SELF_CONSISTENT plus every inverse fixture. A value fails if its row in
        ``primary_sources.csv`` is ``calc``, ``CT`` or ``unverified``, or if the original
        prints a different number for it than the record uses.

        Observed red (602efa2, content red, loader in and records still on the printed
        values): ``K3Cr(CN)6 [allowed] C = 2670.08: the original prints 2800 (observed)``,
        ``[Mn(CN)6]3- [allowed] band:3_E#0 = 31100: CT``, the same for [all], and
        ``MgO:Ni2+ [all] band:1_E#0 = 13670: unverified``.
        """
        primary = {(p.system, p.quantity): p for p in primary_sources()}
        graded = SELF_CONSISTENT | {fx.label.removeprefix("JCE2023 ") for fx in JCE_FIXTURES}
        bad: list[str] = []
        for record in jce_records():
            if record.record_id not in graded:
                continue
            for quantity, value in record.values():
                src = primary.get((record.system, quantity))
                if src is None:
                    continue
                if src.status in UNGRADABLE_STATUS:
                    bad.append(
                        f"{record.record_id} {quantity} = {value:g}: {src.status} ({src.note})"
                    )
                elif src.value is not None and abs(value - src.value) > 0.5:
                    bad.append(
                        f"{record.record_id} {quantity} = {value:g}: the original prints "
                        f"{src.value:g} ({src.status})"
                    )
        assert not bad, "\n".join(bad)

    def test_module_collects_without_audit_dir(self, tmp_path: Path) -> None:
        """A wheel ships no audit/: the module still collects, and the JCE classes skip.

        Observed red (602efa2): collection error, ``FileNotFoundError: ...
        missing/jce2023_table2_parameters.csv`` raised at import by ``_jce_inverse()``.
        """
        env = {**os.environ, "TANABESUGANO_JCE_DIR": str(tmp_path / "missing")}
        module = str(Path(__file__).resolve())
        base = [sys.executable, "-m", "pytest", module, "-p", "no:cacheprovider", "-rs"]
        collected = subprocess.run(  # noqa: S603
            [*base, "--collect-only"], env=env, capture_output=True, text=True, check=False
        )
        assert collected.returncode == 0, collected.stdout[-2000:] + collected.stderr[-2000:]
        assert "TestVanadiumIII" in collected.stdout
        ran = subprocess.run(  # noqa: S603
            [*base, "-k", "Jce2023"], env=env, capture_output=True, text=True, check=False
        )
        assert ran.returncode == 0, ran.stdout[-2000:]
        assert "skipped" in ran.stdout
        assert "passed" not in ran.stdout, ran.stdout[-2000:]


@JCE_SKIP
class TestJce2023Inverse:
    """Inverse: the fitter recovers each self-consistent source within its oracle bound."""

    def test_unnormalised_sources_are_refused(self) -> None:
        """Self-consistent, but their Dq is more than 1 % off nu1/10: forward-only.

        The guard is the factor-of-10 trap, and it is not loosened to admit fixtures
        (plan E ruling R1). Since plan F all three are also COMPARISON_ONLY: their printed
        Dq is not observed. Grading their least-squares Dq against nu1/10 was tried and
        missed the a-priori bound on all three (1686.8, 1674.5 vs 1740; 816.0 vs 801) with
        rmse inside 2-sigma and the fit at the oracle's global minimum -- closed-form vs
        least-squares disagreement, not a fitter finding. nu1/10 grades the nu1/10
        estimator, which plan F's F3 reports.
        """
        assert set(JCE_UNNORMALISED) == {
            "[Cr(H2O)6]3+ [allowed]",
            "[Cr(H2O)6]3+ [all]",
            "MgO:Ni2+ [allowed]",
        }
        assert {f"JCE2023 {k}" for k in JCE_UNNORMALISED} <= set(COMPARISON_ONLY)

    def test_mgo_nu1_estimator_matches_the_original(self) -> None:
        """MgO:Ni2+'s nu1/10 = 801 is graded against the F3 nu1/10 report, not the LS Dq.

        Provenance: ref 24 (doi:10.1063/1.1732066, Section (d)) states the no-spin-orbit
        model gives nu1/10 = 801 (``primary_sources.csv``, the MgO:Ni2+ Dq note); the printed
        Dq 815 adds a predicted spin-orbit stabilisation and stays comparison-only. The
        tolerance is zero: nu1/10 is a band over ten, so any other value means the wrong
        band was taken for nu1. The least-squares Dq (816) is not graded here.

        Observed red (``_with_nu1`` mutated to return the fit unchanged):
        ``AssertionError: assert None == 801.0``.
        """
        (record,) = [r for r in jce_records() if r.record_id == "MgO:Ni2+ [allowed]"]
        note = next(
            p.note for p in primary_sources() if (p.system, p.quantity) == ("MgO:Ni2+", "Dq")
        )
        found = re.search(r"nu1/10 = (\d+)", note)
        assert found is not None, note
        printed = float(found.group(1))
        fit = fit_spectrum(
            record.d_count,
            list(record.bands_cm1),
            record.C,
            spin_state=record.spin_state,
            band_labels=list(record.labels),
        )
        assert fit.dq_nu1 == printed

    def test_errata_name_self_consistent_records(self) -> None:
        """An erratum only matters for a record the forward check would have admitted."""
        assert set(JCE_SOURCE_ERRATA) <= SELF_CONSISTENT
        assert not {fx.label for fx in JCE_FIXTURES} & {f"JCE2023 {k}" for k in JCE_SOURCE_ERRATA}
        ct = {p.system for p in primary_sources() if p.status == "CT"}
        assert {k.rsplit(" [", 1)[0] for k in JCE_SOURCE_ERRATA} <= ct

    def test_every_finding_is_numbered(self) -> None:
        """A strict xfail always names its finding, so a later fix that XPASSes is traced."""
        assert all(re.match(r"^E4-F\d+: ", reason) for reason in JCE_FINDINGS.values())
        assert set(JCE_FINDINGS) <= {fx.label for fx in JCE_FIXTURES}

    @pytest.mark.parametrize(
        "fx",
        [
            pytest.param(
                fx,
                id=fx.label,
                marks=[pytest.mark.xfail(strict=True, reason=JCE_FINDINGS[fx.label])]
                if fx.label in JCE_FINDINGS
                else [],
            )
            for fx in JCE_FIXTURES
        ],
    )
    def test_fit_within_oracle_tolerance(self, fx: IonFixture) -> None:
        """Dq (and B where determined) within the propagated 2-sigma, rmse within 2-sigma.

        Green on arrival (95529fa): a T3 coverage claim, not the red of a fix -- all nine
        records (seven after JCE_SOURCE_ERRATA) passed at the first run, so JCE_FINDINGS
        is empty. Sensitivity checked then: a published Dq moved by +3 % fails every
        record (on the assertion, or at construction through the nu1 == 10Dq guard).
        """
        fit = fit_spectrum(
            fx.d_count,
            list(fx.bands_cm1),
            fx.published_C_cm1,
            spin_state=fx.spin_state,
            include_spin_forbidden=fx.include_spin_forbidden,
            band_labels=list(fx.band_labels) if fx.band_labels is not None else None,
        )
        graded = graded_quantities(fx)
        if "Dq" in graded:
            assert fit.Dq == fx.tol_Dq.approx(fx.published_Dq_cm1), f"{fx.label} Dq={fit.Dq:.1f}"
        if "B" in graded and fx.tol_B.value <= B_GRADE_LIMIT:
            assert fx.tol_B.approx(fx.published_B_cm1) == fit.B, f"{fx.label} B={fit.B:.1f}"
        assert fit.rmse_cm1 < fx.max_rmse_cm1, f"{fx.label} rmse={fit.rmse_cm1:.1f}"
        if fx.expected_outcome == "warns":
            assert any(re.search(fx.expected_match or "", w) for w in fit.warnings), fit.warnings


def comparison_cases() -> list[tuple[str, IonFixture | JceRecord]]:
    """Every COMPARISON_ONLY id that exists here: literature fixtures always, JCE records
    only where the audit tables are present.
    """
    cases: list[tuple[str, IonFixture | JceRecord]] = [
        (fx.label, fx) for fx in FIXTURES if fx.label in COMPARISON_ONLY
    ]
    cases.extend(
        (f"JCE2023 {r.record_id}", r)
        for r in jce_records()
        if f"JCE2023 {r.record_id}" in COMPARISON_ONLY
    )
    return cases


class TestComparisonOnly:
    """Values with no a-priori tolerance: the fit runs, and the distance is reported."""

    def test_every_declared_id_exists_or_is_jce(self) -> None:
        """A COMPARISON_ONLY key names a fixture or a JCE record, never nothing."""
        known = {fx.label for fx in FIXTURES} | {f"JCE2023 {r.record_id}" for r in jce_records()}
        assert all(k in known or k.startswith("JCE2023 ") for k in COMPARISON_ONLY)
        if JCE_DIR.exists():
            assert set(COMPARISON_ONLY) <= known

    @pytest.mark.parametrize(
        ("case_id", "case"), [pytest.param(k, c, id=k) for k, c in comparison_cases()]
    )
    def test_comparison_only_reports_delta(
        self,
        case_id: str,
        case: IonFixture | JceRecord,
        record_property: Callable[[str, object], None],
    ) -> None:
        """Asserts only that the fit runs; the distance to the printed point is reported.

        The delta goes to ``record_property`` (junit XML) and the assertion-free log, not to
        a bound: a value read off a diagram or derived under an assumption has none.
        """
        if isinstance(case, IonFixture):
            d_count, bands, c = case.d_count, list(case.bands_cm1), case.published_C_cm1
            spin, labels, sf = case.spin_state, case.band_labels, case.include_spin_forbidden
            printed = (case.published_Dq_cm1, case.published_B_cm1)
        else:
            d_count, bands, c = case.d_count, list(case.bands_cm1), case.C
            spin, labels, sf = case.spin_state, case.labels, case.spin_forbidden
            printed = (case.Dq, case.B)
        fit = fit_spectrum(
            d_count,
            bands,
            c,
            spin_state=spin,
            include_spin_forbidden=sf,
            band_labels=list(labels) if labels is not None else None,
        )
        assert np.isfinite(fit.Dq)
        assert np.isfinite(fit.B)
        delta = {
            "Dq": None if printed[0] is None else round(fit.Dq - printed[0], 1),
            "B": None if printed[1] is None else round(fit.B - printed[1], 1),
            "reason": COMPARISON_ONLY[case_id],
        }
        record_property("comparison_delta", delta)
