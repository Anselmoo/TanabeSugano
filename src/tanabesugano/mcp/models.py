"""Pydantic response models for the TanabeSugano MCP server."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel
from pydantic import Field

from tanabesugano.mcp._compute import ParameterProvenance


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


class FitMinimum(BaseModel):
    """One distinct minimum the fit's search converged to; all energies in cm^-1."""

    Dq: float = Field(description="Dq at this minimum (cm^-1).")
    B: float = Field(description="Racah B at this minimum (cm^-1).")
    C: float = Field(description="Racah C at this minimum (cm^-1).")
    objective_cm1: float = Field(
        description="Fit objective at this minimum (cm^-1 RMSE, label penalties included).",
    )
    source: Literal["held", "free_c"] = Field(
        default="held",
        description=(
            "'held': a minimum at the reported C. 'free_c': a minimum of a refit with C "
            "free, listed when holding the default C hid it; its C is fitted, not the "
            "reported one."
        ),
    )
    lowest_rmse: bool = Field(
        default=False,
        description=(
            "True on the one entry of minima with the lowest objective_cm1 (cm^-1); "
            "on a tie, the held entry. A fact about the fit, not a recommendation."
        ),
    )


class BandAssignment(BaseModel):
    """The level one observed band was fitted to, in caller order; energies in cm^-1."""

    observed_cm1: float = Field(description="The band as given (cm^-1).")
    computed_cm1: float = Field(
        description="Energy of the assigned level above the ground (cm^-1)."
    )
    residual_cm1: float = Field(description="computed_cm1 - observed_cm1.")
    level_uid: str = Field(description="Machine key of the assigned level, e.g. '3_T_1#1'.")
    label: str = Field(
        description="Transition by free-ion parentage, e.g. '³A₂g → ³T₁g(P)' (display only).",
    )


class FitResult(BaseModel):
    """Result of fitting a spectrum to find Dq and B parameters; all energies in cm^-1."""

    d_count: int
    fitted_Dq: float = Field(description="Optimized ligand field parameter (cm^-1).")
    fitted_B: float = Field(description="Optimized Racah B parameter (cm^-1).")
    fitted_C: float = Field(
        description=(
            "Racah C: held (C_source 'given' or 'default') or fitted ('fitted'); when "
            "C_source is 'undetermined' it is one of c_candidates, for display."
        ),
    )
    c_is_default: bool = Field(
        default=True,
        description=(
            "True when fitted_C came from the per-configuration defaults rather "
            "than from the caller. False when C was fitted (c_fitted). Bookkeeping "
            "only -- see c_constrained for whether the value means anything."
        ),
    )
    Dq_source: ParameterProvenance = Field(
        default="fitted",
        description="Where fitted_Dq comes from: 'fitted', or 'undetermined' when tied minima disagree on it.",
    )
    B_source: ParameterProvenance = Field(
        default="fitted",
        description="Where fitted_B comes from: 'fitted', or 'undetermined' when tied minima disagree on it.",
    )
    C_source: ParameterProvenance = Field(
        default="default",
        description=(
            "Where fitted_C comes from: 'given' by the caller, the per-configuration "
            "'default', 'fitted', or 'undetermined' (tied minima disagree; see "
            "c_candidates and c_range)."
        ),
    )
    c_fitted: bool = Field(
        default=False, description="True when C was a free parameter of the fit."
    )
    c_candidates: list[FitMinimum] = Field(
        default_factory=list,
        description="When C is undetermined: the tied minima, each a complete (Dq, B, C).",
    )
    c_range: tuple[float, float] | None = Field(
        default=None,
        description="When C is undetermined: (lowest, highest) C among c_candidates (cm^-1).",
    )
    minima: list[FitMinimum] = Field(
        default_factory=list,
        description=(
            "Every distinct minimum the search reached, the returned one first, then "
            "any free-C minima (source 'free_c', at their own fitted C). Lists what the "
            "search found, not necessarily every minimum that exists."
        ),
    )
    band_assignments: list[BandAssignment] = Field(
        default_factory=list,
        description="Per observed band, in the order given: the level the fit assigned it.",
    )
    assumptions: list[str] = Field(
        default_factory=list,
        description=(
            "What the fit took for granted rather than determined, e.g. that every band is "
            "spin-allowed when no band is labelled and include_spin_forbidden is False. Not "
            "a warning: it does not depend on the result."
        ),
    )
    Dq_estimator: Literal["least_squares"] = Field(
        default="least_squares",
        description="How fitted_Dq was obtained: least squares over every fitted band.",
    )
    Dq_nu1: float | None = Field(
        default=None,
        description=(
            "d3 and d8 only: nu1/10, the other Dq estimator (nu1 = 10Dq exactly for these "
            "ions), reported beside fitted_Dq, never instead of it. nu1 is the band labelled "
            "4_T_2 / 3_T_2, or without labels the lowest band, assumed spin-allowed. None "
            "where nu1 is not a band; Dq_nu1_reason says why."
        ),
    )
    Dq_nu1_reason: str | None = Field(
        default=None,
        description=(
            "Why Dq_nu1 is None, or, when it is set, that the two Dq estimators differ by "
            "more than the larger of the RMSE and half the last printed digit of nu1. A "
            "report, not a warning."
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
    predicted_peaks_cm1: list[float] = Field(
        description=(
            "Every computed transition at the fitted point (spin-forbidden included), "
            "not only the assigned ones; band_assignments says which band took which."
        ),
    )
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
