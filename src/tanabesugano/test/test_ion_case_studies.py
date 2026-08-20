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

import re

from dataclasses import dataclass
from typing import Literal
from typing import get_args

import pytest

from tanabesugano.mcp._compute import closed_form_dq_b
from tanabesugano.mcp._compute import compute_point
from tanabesugano.mcp._compute import fit_spectrum
from tanabesugano.mcp._compute import reference_ground_term
from tanabesugano.mcp._compute import transition_candidates
from tanabesugano.mcp._defaults import DEFAULTS


PublishedQuantity = Literal["Dq", "10Dq", "Delta_o", "unknown"]
Estimator = Literal["closed_form", "least_squares", "unknown"]
SourceTier = Literal["primary", "textbook", "secondary"]
Outcome = Literal["fit", "warns", "raises"]
SpinState = Literal["high", "low"]

FREE_PARAMETERS = 2  # Dq and B; C is held fixed
CLOSED_FORM_CONFIGS = (3, 8)  # the only d-counts where nu1 == 10Dq exactly
DIAGRAM_ERROR_CONFIGS = (5, 6)  # Hormann & Shaw; see R1 in the module docstring
NU1_NORMALISATION_TOL = 0.01


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

    def __post_init__(self) -> None:
        """Reject an inadmissible fixture at import time."""
        self._check_vocabulary()
        self._check_provenance()
        self._check_outcome_shape()
        self._check_dq_normalisation()

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

    def test_fit_recovers_literature_parameters(self) -> None:
        fx = self.FIXTURE
        fit = fit_spectrum(2, self.BANDS)
        assert fit.ground_term == "3_T_1"
        assert fit.Dq == fx.tol_Dq.approx(fx.published_Dq_cm1)  # measured 1854.1
        assert fx.tol_B.approx(fx.published_B_cm1) == fit.B  # measured 649.4

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
        dq, b = closed_form_dq_b(fx.d_count, list(fx.bands_cm1))
        assert dq == fx.closed_form_tol_Dq.approx(fx.published_Dq_cm1), fx.label
        assert b == fx.closed_form_tol_B.approx(fx.published_B_cm1), fx.label

    @pytest.mark.parametrize("fx", CHROMIUM_III_CASES, ids=_ids(CHROMIUM_III_CASES))
    def test_least_squares_agrees_with_literature(self, fx: IonFixture) -> None:
        fit = fit_spectrum(fx.d_count, list(fx.bands_cm1))
        assert fit.ground_term == "4_A_2", fx.label
        assert fit.Dq == fx.tol_Dq.approx(fx.published_Dq_cm1), f"{fx.label} Dq={fit.Dq}"
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
