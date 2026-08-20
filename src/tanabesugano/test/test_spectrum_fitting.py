"""Test suite for spectrum fitting (ts_fit_spectrum / _compute.fit_spectrum).

Validation strategy, in descending order of durability:

1. **Analytic identities** -- exact, need no external data, can never go stale.
   nu1 = 10Dq for d3/d8; B = (nu3 + nu2 - 3*nu1)/15 for d3/d8.
2. **Synthetic round-trips** -- generate bands from the forward model at a known
   (Dq, B) and require exact recovery. Tests the fitter against the *verified*
   forward model rather than against a second copy of the optimizer.
3. **Literature fixtures** -- real complexes with published Dq and B. Weakest of
   the three, because published values carry convention and provenance risk
   (Dq vs 10Dq, differing free-ion B0), so tolerances here are deliberately loose.

Every numeric tolerance below was measured against this implementation, not
estimated. Where a value looks surprising there is a comment explaining why.
"""

from __future__ import annotations

import numpy as np
import pytest

from tanabesugano.mcp._compute import closed_form_dq_b
from tanabesugano.mcp._compute import compute_point
from tanabesugano.mcp._compute import fit_spectrum
from tanabesugano.mcp._compute import ground_term
from tanabesugano.mcp._compute import peak_rmse
from tanabesugano.mcp._compute import reference_ground_term
from tanabesugano.mcp._compute import term_multiplicity
from tanabesugano.mcp._compute import transition_candidates
from tanabesugano.mcp._defaults import DEFAULTS
from tanabesugano.mcp._defaults import HIGH_SPIN_GROUND_TERM


# [Ni(H2O)6]2+ -- the classic d8 worked example.
NI_AQUA_BANDS = [8500.0, 13800.0, 25300.0]


def forward_spin_allowed_peaks(d_count: int, dq: float, b: float) -> list[float]:
    """Spin-allowed transition energies from the forward model at a known point."""
    c = float(DEFAULTS[d_count]["default_C"])
    _ground, candidates = transition_candidates(compute_point(d_count, dq, b, c))
    return [energy for energy, _assignment, _allowed in candidates]


def rmse_at(d_count: int, dq: float, b: float, observed: list[float]) -> float:
    """RMSE the model achieves at a specific (Dq, B) -- for comparing estimators."""
    predicted = forward_spin_allowed_peaks(d_count, dq, b)
    return peak_rmse(np.asarray(observed), np.asarray(predicted))


class TestSpectrumFittingBasics:
    """Shape and sanity of the returned fit."""

    def test_fit_returns_populated_result(self) -> None:
        fit = fit_spectrum(8, NI_AQUA_BANDS)
        assert fit.Dq > 0
        assert fit.B > 0
        assert fit.C > 0
        assert fit.rmse_cm1 >= 0
        assert fit.transitions
        assert len(fit.residuals_cm1) == len(NI_AQUA_BANDS)

    def test_fitted_parameters_in_physical_range(self) -> None:
        fit = fit_spectrum(8, NI_AQUA_BANDS)
        assert 500 < fit.Dq < 30000, f"Dq={fit.Dq} outside typical range"
        assert 100 < fit.B < 2000, f"B={fit.B} outside typical range"

    def test_transitions_are_labelled_and_sorted(self) -> None:
        fit = fit_spectrum(8, NI_AQUA_BANDS)
        energies = [e for e, _a, _s in fit.transitions]
        assert energies == sorted(energies)
        for energy, assignment, spin_allowed in fit.transitions:
            assert energy > 0
            assert "→" in assignment
            assert isinstance(spin_allowed, bool)

    def test_assignments_name_the_real_ground_term(self) -> None:
        """Every assignment must start from the true ground term.

        Regression guard: the label used to come from next(iter(dict.keys())),
        i.e. dict insertion order, which named the wrong term for all seven
        configurations -- '1_A_1' for d8, whose ground term is '3_A_2'.
        """
        fit = fit_spectrum(8, NI_AQUA_BANDS)
        assert fit.ground_term == "3_A_2"
        for _energy, assignment, _allowed in fit.transitions:
            assert assignment.startswith("3_A_2→"), assignment


class TestAssignmentsAreUnambiguous:
    """Two bands may share a term symbol; they must not share a label.

    The whole point of the Level structure. A ``dict[TermKey, ndarray]`` maps
    d8 ``3_T_1`` to a TWO-element array, so nu2 and nu3 both came back as
    ``3_A_2->3_T_1`` and a chemist could not tell which band was which.

    Uniqueness here is DERIVED, not measured: ``(term, index)`` is already
    proven unique for every configuration (test_levels.py), so a label built
    from it must be unique too. The count 2 is group theory -- d8 has exactly
    two 3T1g levels, from the 3F and 3P free-ion parents.
    """

    def test_the_two_d8_triplet_t1_bands_are_distinguishable(self) -> None:
        fit = fit_spectrum(8, NI_AQUA_BANDS)
        t1 = [a for _e, a, _s in fit.transitions if a.startswith("3_A_2→3_T_1")]
        assert len(t1) == 2, f"expected two 3T1g bands, got {t1}"
        assert t1[0] != t1[1], f"nu2 and nu3 still carry the same label: {t1}"

    @pytest.mark.parametrize("d_count", [2, 3, 4, 6, 7, 8])
    def test_no_two_transitions_share_a_label(self, d_count: int) -> None:
        """Every configuration, spin-forbidden bands included."""
        c = float(DEFAULTS[d_count]["default_C"])
        b = float(DEFAULTS[d_count]["default_B"])
        _ground, candidates = transition_candidates(
            compute_point(d_count, 1000.0, b, c),
            spin_allowed_only=False,
        )
        labels = [a for _e, a, _s in candidates]
        duplicates = {a for a in labels if labels.count(a) > 1}
        assert not duplicates, f"d{d_count} reuses {sorted(duplicates)}"

    def test_a_single_level_term_keeps_a_bare_label(self) -> None:
        """3T2g is the only 3T2g in d8 -- an ordinal there would be noise."""
        _ground, candidates = transition_candidates(
            compute_point(8, 850.0, 907.0, float(DEFAULTS[8]["default_C"])),
        )
        labels = [a for _e, a, _s in candidates]
        assert "3_A_2→3_T_2" in labels, labels


class TestAnalyticIdentities:
    """Exact identities. No external reference data required."""

    @pytest.mark.parametrize(("d_count", "excited"), [(3, "4_T_2"), (8, "3_T_2")])
    @pytest.mark.parametrize("b", [600.0, 900.0, 1200.0])
    def test_nu1_equals_10dq(self, d_count: int, excited: str, b: float) -> None:
        """nu1 = 10Dq exactly for d3/d8, independent of B and C."""
        dq = 777.0
        terms = compute_point(d_count, dq, b, float(DEFAULTS[d_count]["default_C"]))
        _key, ground_energy = ground_term(terms)
        assert float(terms[excited][0]) - ground_energy == pytest.approx(10 * dq, abs=1e-6)

    @pytest.mark.parametrize(("d_count", "dq", "b"), [(8, 850.0, 907.0), (3, 1740.0, 760.0)])
    def test_closed_form_recovers_b(self, d_count: int, dq: float, b: float) -> None:
        """B = (nu3 + nu2 - 3*nu1)/15 is exact for d3/d8."""
        peaks = forward_spin_allowed_peaks(d_count, dq, b)
        recovered_dq, recovered_b = closed_form_dq_b(d_count, peaks)
        assert recovered_dq == pytest.approx(dq, abs=1e-6)
        assert recovered_b == pytest.approx(b, abs=1e-6)

    @pytest.mark.parametrize("d_count", [2, 4, 5, 6, 7])
    def test_closed_form_rejects_degenerate_ground_terms(self, d_count: int) -> None:
        """Only d3/d8 have nu1 = 10Dq; T1g/T2g/Eg ground terms do not."""
        with pytest.raises(ValueError, match="only valid for d3 and d8"):
            closed_form_dq_b(d_count, [10000.0, 20000.0, 30000.0])

    @pytest.mark.parametrize("d_count", sorted(HIGH_SPIN_GROUND_TERM))
    def test_dynamic_ground_term_matches_table(self, d_count: int) -> None:
        """The per-point derivation must agree with the independent oracle table."""
        derived = reference_ground_term(
            d_count,
            float(DEFAULTS[d_count]["default_B"]),
            float(DEFAULTS[d_count]["default_C"]),
            "high",
        )
        assert derived == HIGH_SPIN_GROUND_TERM[d_count]


class TestSyntheticRoundTrip:
    """Peaks generated by the forward model must be recovered exactly."""

    @pytest.mark.parametrize(
        ("d_count", "dq", "b"),
        [(8, 850.0, 907.0), (3, 1740.0, 760.0), (2, 1860.0, 660.0), (7, 970.0, 825.0)],
    )
    def test_round_trip(self, d_count: int, dq: float, b: float) -> None:
        peaks = forward_spin_allowed_peaks(d_count, dq, b)
        fit = fit_spectrum(d_count, peaks)
        assert fit.Dq == pytest.approx(dq, abs=1.0)
        assert pytest.approx(b, abs=1.0) == fit.B
        assert fit.rmse_cm1 < 1.0
        assert fit.ground_term == HIGH_SPIN_GROUND_TERM[d_count]

    @pytest.mark.parametrize(
        ("d_count", "dq", "b"),
        [(8, 850.0, 907.0), (3, 1740.0, 760.0), (2, 1860.0, 660.0), (7, 970.0, 825.0)],
    )
    @pytest.mark.parametrize("displacement", [1.30, 0.75])
    def test_round_trip_survives_a_displaced_seed(
        self,
        d_count: int,
        dq: float,
        b: float,
        displacement: float,
    ) -> None:
        """Recovery must come from the OPTIMIZER, not from the seed.

        For d3/d8 the seed is `closed_form_dq_b`, which on synthetic peaks IS
        the exact answer -- so a plain round-trip can pass even with a broken
        objective, and did under the historical broken metric. Displacing the
        search box breaks that tautology: only a working objective can still
        land on the truth. This is the same failure mode as the original
        test_nickel_aqua_complex, which asserted the hardcoded seed (5000, 600);
        here it had migrated from the test into production.
        """
        peaks = forward_spin_allowed_peaks(d_count, dq, b)
        fit = fit_spectrum(
            d_count,
            peaks,
            dq_bounds=(0.2 * dq * displacement, 5.0 * dq * displacement),
        )
        assert fit.Dq == pytest.approx(dq, abs=1.0)  # measured error <= 0.001
        assert pytest.approx(b, abs=1.0) == fit.B


class TestEstimatorSemantics:
    """How the two estimators relate. Their agreement with LITERATURE values is
    asserted once, in test_ion_case_studies.py -- not re-claimed here.
    """

    def test_the_two_estimators_disagree_on_real_data(self) -> None:
        """Closed form and least-squares are different estimators, both correct.

        The closed form honours nu1 exactly and pushes all error into nu2/nu3;
        least-squares redistributes it. They coincide only when the observed
        bands are mutually consistent with a single (Dq, B), which real spectra
        are not. Asserted as a RELATIONSHIP so it stays true if the literature
        values are ever re-sourced.
        """
        closed_dq, closed_b = closed_form_dq_b(8, NI_AQUA_BANDS)
        fit = fit_spectrum(8, NI_AQUA_BANDS)
        assert pytest.approx(closed_b, abs=1.0) != fit.B
        # ...and least-squares must be the better one BY ITS OWN metric.
        assert fit.rmse_cm1 < rmse_at(8, closed_dq, closed_b, NI_AQUA_BANDS)

    def test_the_two_estimators_agree_on_consistent_data(self) -> None:
        """On peaks generated FROM the model they must coincide exactly.

        This is the control for the test above: the disagreement is a property
        of real data, not of the estimators.
        """
        peaks = forward_spin_allowed_peaks(8, 850.0, 907.0)
        closed_dq, closed_b = closed_form_dq_b(8, peaks)
        fit = fit_spectrum(8, peaks)
        assert closed_dq == pytest.approx(fit.Dq, abs=1.0)
        assert closed_b == pytest.approx(fit.B, abs=1.0)

    def test_nickel_aqua_least_squares(self) -> None:
        """Least-squares lands at (833.5, 947.0), NOT the published pair.

        That is correct, not a defect. The three published bands are not mutually
        consistent with any single (Dq, B): the closed form honours nu1 exactly
        and pushes all error into nu2/nu3, while least-squares redistributes it.
        Measured: (850, 907) scores rmse 249.4 here, (833.5, 947.0) scores 118.8.
        Do NOT "fix" this by biasing the fitter -- both estimators are asserted.
        """
        fit = fit_spectrum(8, NI_AQUA_BANDS)
        assert fit.ground_term == "3_A_2"
        assert 825 < fit.Dq < 875, f"Dq={fit.Dq}"  # measured 833.5
        assert 900 < fit.B < 990, f"B={fit.B}"  # measured 947.0
        assert max(abs(r) for r in fit.residuals_cm1) < 350  # measured 165/122/13
        assert fit.rmse_cm1 < 200  # measured 118.8
        # The least-squares point must beat the closed-form point on RMSE.
        assert fit.rmse_cm1 < rmse_at(8, 850.0, 907.0, NI_AQUA_BANDS)

    def test_nu1_is_10dq_for_the_fitted_result(self) -> None:
        fit = fit_spectrum(8, NI_AQUA_BANDS)
        nu1 = min(e for e, _a, allowed in fit.transitions if allowed)
        assert nu1 == pytest.approx(10 * fit.Dq, abs=1.0)


class TestIllPosedInputsRaise:
    """The fitter must fail loudly rather than return a sentinel."""

    def test_empty_peaks_list_raises(self) -> None:
        with pytest.raises(ValueError, match="at least one observed peak"):
            fit_spectrum(8, [])

    def test_non_positive_peak_raises(self) -> None:
        with pytest.raises(ValueError, match="must all be positive"):
            fit_spectrum(8, [-100.0, 8000.0])

    def test_unsupported_d_count_raises(self) -> None:
        with pytest.raises((ValueError, KeyError)):
            fit_spectrum(1, [10000.0, 20000.0])

    @pytest.mark.parametrize(
        ("d_count", "bands"),
        [(4, [21000.0, 25000.0]), (6, [10400.0, 16000.0])],
    )
    def test_under_determined_fit_raises(self, d_count: int, bands: list[float]) -> None:
        """High-spin d4/d6 have exactly ONE spin-allowed band (= 10Dq).

        B is formally unidentifiable, so any fit with 2+ peaks is ill-posed.
        """
        with pytest.raises(ValueError, match="under-determined"):
            fit_spectrum(d_count, bands)

    def test_no_low_spin_runaway(self) -> None:
        """The fit must never cross the spin crossover to reach a denser manifold."""
        fit = fit_spectrum(5, [18800.0, 23100.0, 24900.0], include_spin_forbidden=True)
        assert fit.ground_term != "2_T_2"


class TestObjectiveFunctionGuards:
    """Direct regression guards on the two defects that made the old fitter lie."""

    def test_unmatched_peaks_are_not_free(self) -> None:
        """Ignoring an observed peak must cost RMSE.

        The old metric only accumulated error for peaks within 500 cm^-1 AND
        divided by that matched count, so "match one peak, drop the rest" scored
        an unbeatable 0.0. Verified: fit_spectrum(8, [22222, 14286]) used to
        return rmse=0.0 by matching 14286 to a spin-forbidden 1_E singlet.
        """
        rmse = peak_rmse(np.array([14286.0, 22222.0]), np.array([14286.0]))
        assert rmse > 5000, f"unmatched peak was free: rmse={rmse}"

    def test_objective_is_not_flat_across_parameter_space(self) -> None:
        """Two different (Dq, B) must give different residuals.

        The old objective returned a constant 1e6 sentinel wherever nothing
        matched, so Nelder-Mead terminated with success=True on a flat plateau
        without ever moving off its seed.
        """
        a = rmse_at(8, 800.0, 900.0, NI_AQUA_BANDS)
        b = rmse_at(8, 850.0, 950.0, NI_AQUA_BANDS)
        assert a != b

    def test_multiplicity_rejects_free_ion_notation(self) -> None:
        """'3F' is free-ion notation and has no octahedral multiplicity.

        Returning 0 here (the old behaviour) silently disabled spin-allowed
        filtering in four separate tools.
        """
        for free_ion in ("3F", "6S", "5D"):
            with pytest.raises(ValueError, match="not an octahedral term key"):
                term_multiplicity(free_ion)

    @pytest.mark.parametrize(
        ("key", "expected"),
        [("3_T_1", 3), ("5_E", 5), ("1_E", 1), ("6_A_1", 6)],
    )
    def test_multiplicity_parses_octahedral_keys(self, key: str, expected: int) -> None:
        assert term_multiplicity(key) == expected


class TestCustomRacahC:
    def test_custom_c_is_passed_through(self) -> None:
        custom_c = 4500.0
        fit = fit_spectrum(8, NI_AQUA_BANDS, C=custom_c)
        assert custom_c == fit.C

    def test_d8_spin_allowed_manifold_is_c_independent(self) -> None:
        """A genuine property of d8, not a bug: C does not move the triplets.

        This is why a "does C change the fit?" assertion is vacuous for d8 --
        it must be made on a configuration whose spin-allowed terms mix singlets.
        """
        first = forward_spin_allowed_peaks(8, 850.0, 907.0)
        c_terms = compute_point(8, 850.0, 907.0, 3800.0)
        _g, candidates = transition_candidates(c_terms)
        assert [e for e, _a, _s in candidates] == pytest.approx(first)


class TestIntegrationWithMCPTool:
    """The MCP wrapper must surface the fit, and convert failures to ComputeError."""

    def test_tool_returns_fit_result(self) -> None:
        from tanabesugano.mcp.models import FitResult
        from tanabesugano.mcp.server import create_server

        create_server()  # registration side effects only
        fit = fit_spectrum(8, NI_AQUA_BANDS)
        result = FitResult(
            d_count=8,
            fitted_Dq=fit.Dq,
            fitted_B=fit.B,
            fitted_C=fit.C,
            r_squared=0.99,
            rmse_cm1=fit.rmse_cm1,
            observed_peaks_cm1=NI_AQUA_BANDS,
            predicted_peaks_cm1=[e for e, _a, _s in fit.transitions],
            peak_assignments=[],
            ground_term=fit.ground_term,
        )
        assert result.ground_term == "3_A_2"
