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


class ComputeError(BaseModel):
    """Structured error so agents can recover instead of crashing."""

    error: str
