"""Test suite for nephelauxetic analysis (ts_nephelauxetic tool).

Documents the bond-covalency interpretation pattern:
- Problem: A fitted Racah B is just a number; its chemical meaning (covalency) is hidden.
- Insight: β = B(complex) / B(free ion) measures d-electron cloud expansion → covalency.
- Validation: Real Ni(II) complexes spanning the ionic→covalent range.
"""

from __future__ import annotations

import pytest

from tanabesugano.mcp._compute import nephelauxetic_analysis
from tanabesugano.mcp._defaults import FREE_ION_RACAH_B
from tanabesugano.mcp._defaults import ION_BY_D_COUNT


class TestNephelauxeticBasics:
    """Core math: β = B(complex) / B(free ion)."""

    def test_returns_expected_keys(self) -> None:
        """Result dict carries the documented fields."""
        result = nephelauxetic_analysis(8, 890.0, "Ni2+")
        assert set(result) == {
            "ion",
            "free_ion_B",
            "beta",
            "covalency",
            "suggested_ligands",
            "interpretation",
        }

    def test_beta_is_ratio_of_b_values(self) -> None:
        """β must equal fitted_B / free_ion_B exactly."""
        result = nephelauxetic_analysis(8, 890.0, "Ni2+")
        expected_beta = 890.0 / FREE_ION_RACAH_B["Ni2+"]
        assert result["beta"] == pytest.approx(expected_beta)

    def test_free_ion_b_equals_b_makes_beta_one(self) -> None:
        """A complex B equal to the free-ion B → β = 1.0 (fully ionic)."""
        free_b = FREE_ION_RACAH_B["Ni2+"]
        result = nephelauxetic_analysis(8, free_b, "Ni2+")
        assert result["beta"] == pytest.approx(1.0)
        assert result["covalency"] == "essentially ionic"

    def test_default_ion_when_none(self) -> None:
        """Omitting ion uses the first tabulated ion for the d_count."""
        result = nephelauxetic_analysis(8, 890.0, ion=None)
        assert result["ion"] == ION_BY_D_COUNT[8][0]


class TestCovalencyClassification:
    """β maps to qualitative covalency labels across the full range."""

    @pytest.mark.parametrize(
        ("beta_target", "expected_label"),
        [
            (0.98, "essentially ionic"),
            (0.90, "weakly covalent"),
            (0.78, "moderately covalent"),
            (0.62, "strongly covalent"),
            (0.50, "very strongly covalent"),
        ],
    )
    def test_covalency_bands(self, beta_target: float, expected_label: str) -> None:
        """Each β band yields the documented covalency label."""
        free_b = FREE_ION_RACAH_B["Ni2+"]
        complex_b = beta_target * free_b
        result = nephelauxetic_analysis(8, complex_b, "Ni2+")
        assert result["covalency"] == expected_label

    def test_lower_beta_is_more_covalent(self) -> None:
        """Monotonicity: smaller β never maps to a less-covalent label."""
        labels_in_order = [
            "essentially ionic",
            "weakly covalent",
            "moderately covalent",
            "strongly covalent",
            "very strongly covalent",
        ]
        free_b = FREE_ION_RACAH_B["Ni2+"]
        seen_indices = []
        for beta in [0.99, 0.90, 0.80, 0.65, 0.50]:
            result = nephelauxetic_analysis(8, beta * free_b, "Ni2+")
            seen_indices.append(labels_in_order.index(result["covalency"]))
        assert seen_indices == sorted(seen_indices), "Covalency not monotonic in β"


class TestRealComplexes:
    """Validate against documented Ni(II) complexes spanning ionic→covalent."""

    def test_ni_aqua_is_weakly_covalent(self) -> None:
        """[Ni(H₂O)₆]²⁺: B ≈ 890 cm⁻¹ → β ≈ 0.85, water is weak-field/ionic end."""
        result = nephelauxetic_analysis(8, 890.0, "Ni2+")
        assert 0.80 < result["beta"] < 0.90
        # Water should appear among the suggested ligands (ionic end of series)
        assert "H2O" in result["suggested_ligands"]

    def test_ni_chloride_is_strongly_covalent(self) -> None:
        """[NiCl₄]²⁻-like: low B ≈ 685 cm⁻¹ → β ≈ 0.66, covalent halide end."""
        result = nephelauxetic_analysis(8, 685.0, "Ni2+")
        assert result["beta"] < 0.70
        assert result["covalency"] in {"strongly covalent", "very strongly covalent"}

    def test_covalent_complex_suggests_heavy_halides(self) -> None:
        """Strongly covalent β should point at the heavy-halide end of the series."""
        result = nephelauxetic_analysis(8, 650.0, "Ni2+")
        heavy = {"Br-", "I-", "N3-"}
        assert heavy & set(result["suggested_ligands"]), (
            f"Expected heavy halides, got {result['suggested_ligands']}"
        )


class TestIonHandling:
    """Free-ion table lookups and validation."""

    def test_all_d_counts_have_at_least_one_ion(self) -> None:
        """Every supported d_count (2-8) maps to at least one tabulated ion."""
        for d in range(2, 9):
            assert ION_BY_D_COUNT.get(d), f"d{d} has no tabulated ion"
            for ion in ION_BY_D_COUNT[d]:
                assert ion in FREE_ION_RACAH_B, f"{ion} missing from FREE_ION_RACAH_B"

    def test_unknown_ion_raises(self) -> None:
        """An ion not in the table raises ValueError."""
        with pytest.raises(ValueError, match="Unknown ion"):
            nephelauxetic_analysis(8, 890.0, "Xx99+")

    def test_unsupported_d_count_raises(self) -> None:
        """A d_count with no tabulated ions raises ValueError."""
        with pytest.raises(ValueError, match="free ions"):
            nephelauxetic_analysis(1, 890.0)

    def test_non_positive_b_raises(self) -> None:
        """A non-positive fitted_B raises ValueError."""
        with pytest.raises(ValueError, match="must be positive"):
            nephelauxetic_analysis(8, -5.0, "Ni2+")

    def test_fe3_d5_analysis(self) -> None:
        """d5 Fe³⁺ (free-ion B = 1015) interprets sensibly."""
        result = nephelauxetic_analysis(5, 800.0, "Fe3+")
        assert result["ion"] == "Fe3+"
        assert result["free_ion_B"] == 1015.0
        assert result["beta"] == pytest.approx(800.0 / 1015.0)


class TestInterpretationString:
    """The human-readable interpretation is well-formed."""

    def test_interpretation_mentions_beta_and_ion(self) -> None:
        """Interpretation text references β value and the ion."""
        result = nephelauxetic_analysis(8, 890.0, "Ni2+")
        text = result["interpretation"]
        assert "beta" in text
        assert "Ni2+" in text
        assert "%" in text  # reports cloud expansion percentage

    def test_interpretation_includes_ligands_when_available(self) -> None:
        """When ligands are suggested, they appear in the interpretation."""
        result = nephelauxetic_analysis(8, 890.0, "Ni2+")
        if result["suggested_ligands"]:
            assert "Consistent with ligands" in result["interpretation"]


class TestPipelineWithFitSpectrum:
    """Document the fit → interpret pipeline (the whole point of this feature)."""

    def test_fit_then_interpret(self) -> None:
        """A B from fit_spectrum flows straight into nephelauxetic_analysis.

        This is the headline workflow: measure spectrum → fit B → learn covalency.
        """
        from tanabesugano.mcp._compute import fit_spectrum

        # [Ni(H2O)6]2+ literature bands. The previous fixture ([11957, 22697,
        # 50000]) was not reproducible by any d8 spin-allowed triple -- it was
        # produced by the old fitter, which scored a "perfect" fit by silently
        # discarding peaks it could not match.
        observed = [8500.0, 13800.0, 25300.0]
        fit = fit_spectrum(8, observed)

        # Feed the fitted B straight into the interpreter
        result = nephelauxetic_analysis(8, fit.B, "Ni2+")

        assert 0.0 < result["beta"] <= 1.5
        assert result["covalency"]
        assert result["interpretation"]
