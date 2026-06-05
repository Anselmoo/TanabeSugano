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
    r_squared: float = Field(description="Goodness of fit (R² metric, 0-1 is typical).")
    rmse_cm1: float = Field(description="Root-mean-square error in cm^-1.")
    observed_peaks_cm1: list[float] = Field(description="Input observed peak positions.")
    predicted_peaks_cm1: list[float] = Field(description="Predicted peaks from fitted model.")
    peak_assignments: list[SpectrumPeak] = Field(description="Detailed transition assignments.")


class ComputeError(BaseModel):
    """Structured error so agents can recover instead of crashing."""

    error: str
