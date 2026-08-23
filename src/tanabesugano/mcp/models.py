"""Pydantic response models for the TanabeSugano MCP server."""

from __future__ import annotations

from pydantic import BaseModel
from pydantic import Field


class SupportedConfig(BaseModel):
    """Metadata for a supported d-electron configuration."""

    d_count: int = Field(description="Number of d-electrons (2-8).")
    ground_term: str = Field(description="Spectroscopic ground-state term symbol.")
    matrix_size: int = Field(description="Sum of term-symbol matrix block dimensions.")
    default_B: float = Field(description="Default Racah B (cm^-1).")
    default_C: float = Field(description="Default Racah C (cm^-1).")


class ComputeResult(BaseModel):
    """Eigenvalue result for a single (Dq, B, C) point."""

    d_count: int
    Dq: float
    B: float
    C: float
    terms: dict[str, list[float]] = Field(
        description="Term symbol -> eigenvalues in wavenumbers (cm^-1).",
    )


class DiagramPoint(BaseModel):
    """One point of a Tanabe-Sugano diagram sweep."""

    Dq: float
    delta_over_B: float = Field(description="10*Dq/B (classical TS x-axis).")
    terms: dict[str, list[float]]


class DiagramResult(BaseModel):
    """A swept Tanabe-Sugano diagram across Dq."""

    d_count: int
    B: float
    C: float
    dq_min: float
    dq_max: float
    steps: int
    points: list[DiagramPoint]


class SpectrumPeak(BaseModel):
    """One transition energy in a fitted spectrum."""

    energy_cm1: float = Field(description="Transition energy in cm^-1.")
    assignment: str = Field(description="Ground state → excited state term assignment.")
    intensity: float = Field(description="Relative intensity (0-1).")


class FitResult(BaseModel):
    """Result of fitting a spectrum to find Dq and B parameters."""

    d_count: int
    fitted_Dq: float = Field(description="Optimized ligand field parameter (cm^-1).")
    fitted_B: float = Field(description="Optimized Racah B parameter (cm^-1).")
    fitted_C: float = Field(description="Racah C parameter used (typically fixed or default).")
    c_is_default: bool = Field(
        default=True,
        description=(
            "True when fitted_C came from the per-configuration defaults rather "
            "than from the caller. Bookkeeping only -- see c_constrained for "
            "whether the value means anything."
        ),
    )
    c_constrained: bool = Field(
        default=False,
        description=(
            "True when the observed bands could actually pin Racah C -- i.e. the "
            "fitted manifold's band energies move when C moves. False means "
            "fitted_C is an assumption carried through the fit, not a result of "
            "it, and must not be reported as a fitted quantity. Typically False "
            "for spin-allowed fits of d2/d3/d8, and for d4-d7 below the spin "
            "crossover; True for spin-forbidden fits and above the crossover."
        ),
    )
    r_squared: float | None = Field(
        default=None,
        description=(
            "Coefficient of determination against the variance of the observed "
            "peaks. None when it is undefined (a single peak, or zero variance)."
        ),
    )
    rmse_cm1: float = Field(description="Root-mean-square error in cm^-1.")
    observed_peaks_cm1: list[float] = Field(description="Input observed peak positions.")
    predicted_peaks_cm1: list[float] = Field(description="Predicted peaks from fitted model.")
    peak_assignments: list[SpectrumPeak] = Field(description="Detailed transition assignments.")
    ground_term: str = Field(
        default="",
        description="Octahedral ground term the fit is referenced to, e.g. '3_A_2'.",
    )
    spin_state: str = Field(
        default="high",
        description="Spin regime the fit was pinned to: 'high', 'low' or 'auto'.",
    )
    residuals_cm1: list[float] = Field(
        default_factory=list,
        description="Signed predicted-minus-observed residual per input peak (cm^-1).",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Non-fatal caveats, e.g. a parameter pinned at a search bound.",
    )


class NephelauxeticResult(BaseModel):
    """Bond-covalency interpretation of a fitted Racah B via the nephelauxetic ratio."""

    ion: str = Field(description="Free-ion label, e.g. 'Ni2+'.")
    free_ion_B: float = Field(description="Tabulated free-ion Racah B (cm^-1).")
    complex_B: float = Field(description="Racah B of the complex (cm^-1).")
    beta: float = Field(description="Nephelauxetic ratio β = B(complex) / B(free ion).")
    covalency: str = Field(description="Qualitative bond covalency label.")
    suggested_ligands: list[str] = Field(
        description="Ligands whose cloud expansion matches the observed β.",
    )
    interpretation: str = Field(description="Human-readable chemical interpretation.")


class ComputeError(BaseModel):
    """Structured error so agents can recover instead of crashing."""

    error: str
