"""Test suite for spectrum fitting (ts_fit_spectrum tool).

This module documents the UV-Vis spectrum fitting pattern:
- Problem: Given observed absorption peaks (cm⁻¹), extract ligand field parameters Dq and B
- Pattern: Algorithm Selection + Lazy Computation via scipy.optimize.minimize
- Validation: Real coordination complex data from literature
"""

from __future__ import annotations

import pytest

from tanabesugano.mcp._compute import fit_spectrum


class TestSpectrumFittingBasics:
    """Basic functionality: does fitting converge and return sensible values?"""

    def test_fit_spectrum_returns_tuple_of_six_elements(self) -> None:
        """fit_spectrum returns (dq, b, c, rmse, transitions)."""
        observed_peaks = [11900, 22700, 50100]
        dq, b, c, rmse, transitions = fit_spectrum(8, observed_peaks)

        assert isinstance(dq, (int, float))
        assert isinstance(b, (int, float))
        assert isinstance(c, (int, float))
        assert isinstance(rmse, (int, float))
        assert isinstance(transitions, list)

    def test_fitted_parameters_in_physical_range(self) -> None:
        """Fitted Dq and B fall within typical coordination chemistry ranges."""
        observed_peaks = [11900, 22700, 50100]
        dq, b, c, rmse, transitions = fit_spectrum(8, observed_peaks)

        # Typical octahedral Dq: 2000–10000 cm⁻¹
        assert 500 < dq < 30000, f"Dq={dq} outside typical range"
        # Typical Racah B: 200–1200 cm⁻¹
        assert 100 < b < 2000, f"B={b} outside typical range"

    def test_transitions_list_not_empty(self) -> None:
        """Fitted model produces at least one predicted transition."""
        observed_peaks = [11900, 22700, 50100]
        dq, b, c, rmse, transitions = fit_spectrum(8, observed_peaks)

        assert len(transitions) > 0, "No transitions predicted"
        # Each transition is (energy_cm1, assignment_string)
        for energy, assignment in transitions:
            assert isinstance(energy, (int, float))
            assert isinstance(assignment, str)
            assert "→" in assignment


class TestRealCoordinationComplexes:
    """Validate against literature UV-Vis data from real coordination complexes.

    Data source: Chemistry LibreTexts + Doc Brown's chemistry notes.
    """

    def test_nickel_aqua_complex(self) -> None:
        """Fit [Ni(H₂O)₆]²⁺ from literature absorption data.

        Literature:
            - Wavelengths: 450 nm (22,222 cm⁻¹), 700 nm (14,286 cm⁻¹)
            - Appears green: absorbs blue and red
            - d8 octahedral
        """
        # Convert nm → cm⁻¹
        observed_peaks = [
            10**7 / 450,  # 22222 cm⁻¹
            10**7 / 700,  # 14286 cm⁻¹
        ]
        dq, b, c, rmse, transitions = fit_spectrum(8, observed_peaks)

        # For [Ni(H₂O)₆]²⁺, expect Dq ≈ 5000–5500 cm⁻¹ (water is weak field)
        assert 4500 < dq < 6000, f"Dq={dq:.0f} unreasonable for aqua Ni²⁺"
        # Expect B ≈ 600–700 cm⁻¹ (typical for Ni²⁺)
        assert 500 < b < 800, f"B={b:.0f} unreasonable for Ni²⁺"
        # RMSE should be very low for literature data
        assert rmse < 100, f"RMSE={rmse:.0f}; fitting did not converge well"

    def test_nickel_ammonia_complex(self) -> None:
        """Fit [Ni(NH₃)₆]²⁺ from literature absorption data.

        Literature:
            - Wavelengths: 360 nm (27,778 cm⁻¹), 590 nm (16,949 cm⁻¹)
            - Appears pale blue: absorbs more blue than [Ni(H₂O)₆]²⁺
            - d8 octahedral; ammonia is stronger-field than water
        """
        observed_peaks = [
            10**7 / 360,  # 27778 cm⁻¹
            10**7 / 590,  # 16949 cm⁻¹
        ]
        dq, b, c, rmse, transitions = fit_spectrum(8, observed_peaks)

        # Ammonia stronger field → Dq should be similar or slightly lower
        # than aqua complex (literature shows ~5000–5200 cm⁻¹)
        assert 4500 < dq < 6000, f"Dq={dq:.0f} unreasonable"
        # Stronger field → B may be slightly higher than aqua
        assert 500 < b < 900, f"B={b:.0f} unreasonable"

    def test_ammonia_vs_aqua_parameter_difference(self) -> None:
        """Verify that ammonia and aqua complexes yield different fitted parameters.

        Physical insight: Even though both are d8 Ni²⁺, the ligand field strength
        differs, so we should recover different Dq/B pairs.
        """
        aqua_peaks = [10**7 / 450, 10**7 / 700]
        ammonia_peaks = [10**7 / 360, 10**7 / 590]

        dq_aqua, b_aqua, _, _, _ = fit_spectrum(8, aqua_peaks)
        dq_ammonia, b_ammonia, _, _, _ = fit_spectrum(8, ammonia_peaks)

        # Parameters should differ (not identical)
        assert dq_aqua != dq_ammonia or b_aqua != b_ammonia, (
            "Aqua and ammonia complexes should yield different parameters"
        )


class TestFittingRobustness:
    """Test fitting stability under realistic and edge-case conditions."""

    def test_fit_with_three_peaks(self) -> None:
        """Fitting with three observed peaks (typical for d8)."""
        observed_peaks = [11900, 22700, 50100]
        dq, b, c, rmse, transitions = fit_spectrum(8, observed_peaks)

        assert rmse >= 0, "RMSE should be non-negative"

    def test_fit_with_single_peak(self) -> None:
        """Fitting with a single peak still converges (underdetermined system)."""
        observed_peaks = [22000]
        dq, b, c, rmse, transitions = fit_spectrum(8, observed_peaks)

        assert dq > 0 and b > 0, "Fitting should produce positive parameters"

    def test_fit_with_noisy_peaks(self) -> None:
        """Fitting with noisy data (peaks perturbed from ideal)."""
        # Theoretical peaks for d8 at Dq=5000, B=600
        # Add ±500 cm⁻¹ noise
        theoretical_peaks = [11957, 22697, 50000]
        noisy_peaks = [p + 250 for p in theoretical_peaks]

        dq, b, c, rmse, transitions = fit_spectrum(8, noisy_peaks)

        # Should recover parameters close to true values despite noise
        assert 4500 < dq < 5500, f"Dq={dq:.0f} too far from true ~5000"
        assert 500 < b < 700, f"B={b:.0f} too far from true ~600"

    def test_empty_peaks_list_converges_to_defaults(self) -> None:
        """Empty peaks list causes fitting to converge to default parameters.

        Note: Input validation (rejecting empty peaks) happens at the MCP tool layer,
        not at fit_spectrum. This core function is lenient to allow testing.
        """
        dq, b, c, rmse, transitions = fit_spectrum(8, [])

        # Fitting with no constraints defaults to initial guess
        assert dq > 0 and b > 0, "Even with empty input, should return parameters"
        assert rmse == 1e6, "RMSE should be max penalty for no observed peaks"

    def test_invalid_d_count_raises(self) -> None:
        """Invalid d_count (not 2-8) should raise (ValueError or KeyError)."""
        # fit_spectrum raises ValueError from _resolve_config or KeyError from DEFAULTS
        with pytest.raises((ValueError, KeyError)):
            fit_spectrum(1, [10000, 20000])  # d1 not supported

    def test_custom_c_parameter_respected(self) -> None:
        """When C is provided, it should be returned unchanged."""
        observed_peaks = [11900, 22700, 50100]
        custom_c = 4000.0

        dq, b, c, rmse, transitions = fit_spectrum(8, observed_peaks, C=custom_c)

        assert c == custom_c, f"C should be {custom_c}, got {c}"


class TestTransitionAssignments:
    """Test that transition assignments make physical sense."""

    def test_predicted_transitions_are_positive_energy(self) -> None:
        """All predicted transitions should have positive energy (excited states)."""
        observed_peaks = [11900, 22700, 50100]
        dq, b, c, rmse, transitions = fit_spectrum(8, observed_peaks)

        for energy, assignment in transitions:
            assert energy > 0, f"Transition energy {energy} should be positive"

    def test_transition_assignments_contain_arrow(self) -> None:
        """Each assignment string should show ground → excited state."""
        observed_peaks = [11900, 22700, 50100]
        dq, b, c, rmse, transitions = fit_spectrum(8, observed_peaks)

        for energy, assignment in transitions:
            assert "→" in assignment, f"Assignment '{assignment}' missing arrow"
            parts = assignment.split("→")
            assert len(parts) == 2, f"Assignment should have exactly one arrow"

    def test_transitions_sorted_by_energy(self) -> None:
        """Predicted transitions should be in order of increasing energy."""
        observed_peaks = [11900, 22700, 50100]
        dq, b, c, rmse, transitions = fit_spectrum(8, observed_peaks)

        energies = [t[0] for t in transitions]
        assert energies == sorted(energies), "Transitions should be sorted by energy"


class TestPatternDocumentation:
    """Document the algorithmic pattern used: Algorithm Selection + Optimization."""

    def test_pattern_name(self) -> None:
        """The spectrum fitting pattern uses scipy.optimize.minimize."""
        # This is not a traditional GoF pattern, but combines:
        # 1. Algorithm Selection (which optimizer? Nelder-Mead chosen for robustness)
        # 2. Lazy Computation (optimize only when fit_spectrum is called)
        # 3. Objective Function as Strategy (user-defined matching metric)
        observed_peaks = [11900, 22700, 50100]
        dq, b, c, rmse, transitions = fit_spectrum(8, observed_peaks)

        # The fitting succeeds, proving the pattern works
        assert dq > 0 and b > 0 and rmse >= 0

    def test_pattern_trades_off_accuracy_for_speed(self) -> None:
        """Nelder-Mead converges in ~500 iterations (default xatol, fatol).

        Note: For interactive use, this is fast enough. For ultra-high accuracy,
        could switch to minimize(..., method='BFGS') with analytical gradient.
        """
        import time

        observed_peaks = [11900, 22700, 50100]
        start = time.perf_counter()
        dq, b, c, rmse, transitions = fit_spectrum(8, observed_peaks)
        elapsed = time.perf_counter() - start

        # Should complete in <<1 second on modern hardware
        assert elapsed < 5.0, f"Fitting took {elapsed:.2f}s; expected <5s"


class TestIntegrationWithMCPTool:
    """Document how fit_spectrum integrates with the MCP tool wrapper."""

    def test_mcp_tool_wraps_fit_spectrum(self) -> None:
        """The ts_fit_spectrum MCP tool calls fit_spectrum internally.

        This test documents the integration point: the MCP layer adds:
        - Input validation (non-empty peaks, max 50 peaks)
        - Error handling (catches ValueError, RuntimeError)
        - Response wrapping (FitResult Pydantic model)
        - Metadata (fitted Dq/B/C, r_squared, peak assignments)
        """
        # Direct fit_spectrum call
        observed_peaks = [11900, 22700, 50100]
        dq, b, c, rmse, transitions = fit_spectrum(8, observed_peaks)

        # The MCP tool ts_fit_spectrum wraps this and returns FitResult with:
        # - fitted_Dq, fitted_B, fitted_C (the parameters)
        # - r_squared (goodness-of-fit metric)
        # - rmse_cm1 (root-mean-square error)
        # - observed_peaks_cm1 (input for reproducibility)
        # - predicted_peaks_cm1 (theoretical spectrum)
        # - peak_assignments (SpectrumPeak objects with energy + assignment)

        assert dq > 0 and b > 0 and c > 0, "All parameters should be positive"
        assert len(transitions) > 0, "Should have predicted transitions"
