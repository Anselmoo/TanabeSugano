"""Numeric ts_* tools: listing, single-point compute, swept diagrams."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tanabesugano import __version__
from tanabesugano.mcp._compute import SUPPORTED_D_COUNTS
from tanabesugano.mcp._compute import compute_point
from tanabesugano.mcp._compute import fit_spectrum
from tanabesugano.mcp._compute import nephelauxetic_analysis
from tanabesugano.mcp._compute import sweep_dq
from tanabesugano.mcp._defaults import DEFAULTS
from tanabesugano.mcp._inputs import D_COUNT_LITERAL
from tanabesugano.mcp.models import ComputeError
from tanabesugano.mcp.models import ComputeResult
from tanabesugano.mcp.models import DiagramPoint
from tanabesugano.mcp.models import DiagramResult
from tanabesugano.mcp.models import FitResult
from tanabesugano.mcp.models import NephelauxeticResult
from tanabesugano.mcp.models import SpectrumPeak
from tanabesugano.mcp.models import SupportedConfig
from tanabesugano.mcp.tools._shared import READONLY
from tanabesugano.mcp.tools._shared import TS_META
from tanabesugano.mcp.tools._shared import resolve_bc


if TYPE_CHECKING:
    from fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    """Register the numeric ts_* tools."""

    @mcp.tool(
        name="ts_supported_configs",
        title="Supported d-configurations",
        version=__version__,
        tags={"tanabesugano", "metadata"},
        annotations=READONLY,
        meta=TS_META,
    )
    def ts_supported_configs() -> list[SupportedConfig]:
        """List the d-electron configurations supported by TanabeSugano (d2-d8)."""
        return [
            SupportedConfig(
                d_count=d,
                ground_term=DEFAULTS[d]["ground_term"],
                matrix_size=DEFAULTS[d]["matrix_size"],
                default_B=DEFAULTS[d]["default_B"],
                default_C=DEFAULTS[d]["default_C"],
            )
            for d in SUPPORTED_D_COUNTS
        ]

    @mcp.tool(
        name="ts_compute",
        title="Compute one Tanabe-Sugano point",
        version=__version__,
        tags={"tanabesugano", "compute"},
        annotations=READONLY,
        meta=TS_META,
    )
    def ts_compute(
        d_count: D_COUNT_LITERAL,  # type: ignore[valid-type]
        Dq: float,
        B: float | None = None,
        C: float | None = None,
    ) -> ComputeResult | ComputeError:
        """Solve the d^n ligand-field Hamiltonian at one (Dq, B, C) point.

        Returns the eigenvalues grouped by spectroscopic term symbol.

        Args:
            d_count: d-electron count (constrained to 2..8 via the input schema).
            Dq: Crystal-field strength in cm^-1.
            B: Racah B parameter (cm^-1). Defaults to the per-configuration value.
            C: Racah C parameter (cm^-1). Defaults to the per-configuration value.

        """
        b_val, c_val = resolve_bc(d_count, B, C)
        if b_val <= 0:
            return ComputeError(error=f"Racah B must be positive, got {b_val}")
        try:
            terms = compute_point(d_count, Dq, b_val, c_val)
        except (ValueError, RuntimeError) as exc:
            return ComputeError(error=str(exc))
        return ComputeResult(d_count=d_count, Dq=Dq, B=b_val, C=c_val, terms=terms)

    @mcp.tool(
        name="ts_diagram",
        title="Compute a Tanabe-Sugano diagram",
        version=__version__,
        tags={"tanabesugano", "compute", "diagram"},
        annotations=READONLY,
        meta=TS_META,
    )
    def ts_diagram(
        d_count: D_COUNT_LITERAL,  # type: ignore[valid-type]
        dq_min: float = 0.0,
        dq_max: float = 1500.0,
        steps: int = 60,
        B: float | None = None,
        C: float | None = None,
    ) -> DiagramResult | ComputeError:
        """Sweep Dq and return all term eigenvalues per point.

        Args:
            d_count: d-electron count (2..8).
            dq_min: Lower Dq bound of the sweep (cm^-1).
            dq_max: Upper Dq bound of the sweep (cm^-1); 0..1500 covers the
                typical octahedral crystal-field strength region.
            steps: Number of sample points (>=2).
            B: Optional Racah B; defaults to the per-configuration value.
            C: Optional Racah C; defaults to the per-configuration value.

        """
        b_val, c_val = resolve_bc(d_count, B, C)
        if b_val <= 0:
            return ComputeError(error=f"Racah B must be positive, got {b_val}")
        try:
            dq_values, points = sweep_dq(d_count, dq_min, dq_max, steps, b_val, c_val)
        except ValueError as exc:
            return ComputeError(error=str(exc))
        return DiagramResult(
            d_count=d_count,
            B=b_val,
            C=c_val,
            dq_min=dq_min,
            dq_max=dq_max,
            steps=steps,
            points=[
                DiagramPoint(
                    Dq=float(dq),
                    delta_over_B=float(dq * 10.0 / b_val) if b_val else 0.0,
                    terms=pt,
                )
                for dq, pt in zip(dq_values, points, strict=True)
            ],
        )

    @mcp.tool(
        name="ts_fit_spectrum",
        title="Fit observed absorption bands to extract Dq and B parameters",
        version=__version__,
        tags={"tanabesugano", "compute", "fit", "spectroscopy"},
        annotations=READONLY,
        meta=TS_META,
    )
    def ts_fit_spectrum(
        d_count: D_COUNT_LITERAL,  # type: ignore[valid-type]
        observed_peaks_cm1: list[float],
        C: float | None = None,
    ) -> FitResult | ComputeError:
        """Fit observed UV-Vis absorption bands to determine Dq and B parameters.

        Given a list of absorption peak positions measured in the lab (in cm^-1),
        this tool performs a least-squares optimization to find the crystal-field
        strength (Dq) and Racah B parameter that best reproduce the observed
        spectrum.

        Args:
            d_count: d-electron count (2..8).
            observed_peaks_cm1: List of observed transition energies in cm^-1.
                Typically in the range 10000-40000 cm^-1 for visible/near-UV regions.
            C: Optional Racah C parameter (cm^-1). If not provided, uses the
                default value for the given d_count.

        Returns:
            FitResult containing the optimized Dq, B, quality metrics, and
            predicted peak assignments.

        Example:
            Fitting a d8 (Ni2+) complex with three observed bands:
            ts_fit_spectrum(d_count=8, observed_peaks_cm1=[8000, 13000, 25000])

        """
        if not observed_peaks_cm1:
            return ComputeError(error="At least one observed peak required")
        if len(observed_peaks_cm1) > 50:
            return ComputeError(error="Too many peaks (max 50); filter or summarize")

        try:
            fitted_dq, fitted_b, fitted_c, rmse, transitions = fit_spectrum(
                d_count,
                observed_peaks_cm1,
                C=C,
            )
        except (ValueError, RuntimeError) as exc:
            return ComputeError(error=f"Fitting failed: {exc!s}")

        predicted_energies = [t[0] for t in transitions]
        peak_assignments = [
            SpectrumPeak(energy_cm1=t[0], assignment=t[1], intensity=1.0) for t in transitions
        ]

        r_squared = 1.0 - (rmse**2 / max(1.0, sum(e**2 for e in observed_peaks_cm1)))
        return FitResult(
            d_count=d_count,
            fitted_Dq=fitted_dq,
            fitted_B=fitted_b,
            fitted_C=fitted_c,
            r_squared=max(0.0, r_squared),
            rmse_cm1=rmse,
            observed_peaks_cm1=observed_peaks_cm1,
            predicted_peaks_cm1=predicted_energies,
            peak_assignments=peak_assignments,
        )

    @mcp.tool(
        name="ts_nephelauxetic",
        title="Interpret a fitted Racah B as metal-ligand bond covalency",
        version=__version__,
        tags={"tanabesugano", "interpret", "covalency", "spectroscopy"},
        annotations=READONLY,
        meta=TS_META,
    )
    def ts_nephelauxetic(
        d_count: D_COUNT_LITERAL,  # type: ignore[valid-type]
        fitted_B: float,
        ion: str | None = None,
    ) -> NephelauxeticResult | ComputeError:
        """Interpret a fitted Racah B as metal-ligand bond covalency.

        Computes the nephelauxetic ratio β = B(complex) / B(free ion) — the
        classic spectroscopic measure of how far the d-electron cloud has
        expanded onto the ligands. β near 1.0 means an essentially ionic bond;
        β well below 1.0 means increasing covalent character. The ratio also
        places the ligand on the nephelauxetic series.

        Pairs naturally with ts_fit_spectrum: fit a spectrum to get B, then feed
        that B here to learn what kind of bond produced it.

        Args:
            d_count: d-electron count (2..8); selects the free-ion table.
            fitted_B: Racah B of the complex (cm^-1), e.g. from ts_fit_spectrum.
            ion: Free-ion label such as "Ni2+". If omitted, the first ion
                tabulated for the d_count is used.

        Returns:
            NephelauxeticResult with β, a covalency label, suggested ligand
            classes, and a human-readable interpretation.

        Example:
            A d8 Ni2+ complex fitted to B = 890 cm^-1:
            ts_nephelauxetic(d_count=8, fitted_B=890, ion="Ni2+")
            → β ≈ 0.85 (weakly covalent; consistent with H2O / NH3).

        """
        if fitted_B <= 0:
            return ComputeError(error=f"fitted_B must be positive, got {fitted_B}")

        try:
            result = nephelauxetic_analysis(d_count, fitted_B, ion=ion)
        except (ValueError, KeyError) as exc:
            return ComputeError(error=f"Nephelauxetic analysis failed: {exc!s}")

        return NephelauxeticResult(
            ion=str(result["ion"]),
            free_ion_B=float(result["free_ion_B"]),  # type: ignore[arg-type]
            complex_B=fitted_B,
            beta=float(result["beta"]),  # type: ignore[arg-type]
            covalency=str(result["covalency"]),
            suggested_ligands=list(result["suggested_ligands"]),  # type: ignore[arg-type]
            interpretation=str(result["interpretation"]),
        )
