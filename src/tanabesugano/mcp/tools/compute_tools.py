"""Numeric ts_* tools: listing, single-point compute, swept diagrams."""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Literal

from tanabesugano import __version__
from tanabesugano.mcp._compute import SUPPORTED_D_COUNTS
from tanabesugano.mcp._compute import fit_spectrum
from tanabesugano.mcp._compute import nephelauxetic_analysis
from tanabesugano.mcp._defaults import DEFAULTS
from tanabesugano.mcp._inputs import D_COUNT_LITERAL
from tanabesugano.mcp.models import BandAssignment
from tanabesugano.mcp.models import ComputeError
from tanabesugano.mcp.models import FitMinimum
from tanabesugano.mcp.models import FitResult
from tanabesugano.mcp.models import NephelauxeticResult
from tanabesugano.mcp.models import SpectrumPeak
from tanabesugano.mcp.models import SupportedConfig
from tanabesugano.mcp.tools._shared import READONLY
from tanabesugano.mcp.tools._shared import TS_META
from tanabesugano.script_export import labelled_bands


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

    # ts_compute and ts_diagram were removed: their raw nested-dict payloads
    # ({"4_T_1": [25248.48, 42994.43, ...]} or DiagramResult with hundreds
    # of points × hundreds of eigenvalues) were unusable without further
    # processing — Claude's "next steps" almost always devolved into
    # "save to CSV / render PNG" suggestions that the client cannot execute.
    # Replacements:
    #   * ts_compute_app      → sortable DataTable of eigenvalues at one point
    #   * ts_diagram_app      → full diagram with LineChart + Dq slider
    #   * ts_plot_view        → interactive Chart.js line plot
    #   * ts_plot_png         → matplotlib PNG fallback
    #   * ts_terms_table_data → machine-readable rows when an agent needs
    #                           the numbers (sorted, with multiplicity / E/B).

    @mcp.tool(
        name="ts_fit_spectrum",
        title="Fit observed absorption bands to extract Dq and B parameters",
        version=__version__,
        tags={"tanabesugano", "compute", "fit", "spectroscopy"},
        annotations=READONLY,
        meta=TS_META,
    )
    def ts_fit_spectrum(
        d_count: D_COUNT_LITERAL,
        observed_peaks_cm1: list[float],
        C: float | None = None,
        # Deliberately narrower than fit_spectrum's SpinState. "auto"
        # resolves the regime at a supplied Dq, and this tool has no Dq to
        # supply -- fit_spectrum raises "spin_state='auto' requires an
        # explicit Dq". Offering it here would advertise an option that
        # always fails.
        spin_state: Literal["high", "low"] = "high",
        include_spin_forbidden: bool = False,
        band_labels: list[str | list[str] | None] | None = None,
        fit_c: bool | None = None,
        dq_bounds: tuple[float, float] | None = None,
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
                default value for the given d_count. Note the spin-allowed
                manifold of d2 and d8 is independent of C.
            spin_state: Which side of the spin crossover to fit on. The fit is
                pinned to this regime and refuses solutions that cross it.
            include_spin_forbidden: Also fit against spin-forbidden transitions.
                Required for high-spin d5, whose d-d bands are all spin-forbidden.
            band_labels: Optional, one per peak in the order given: a term key
                ("4_T_1") or level uid ("4_T_1#1") naming the level the band is
                assigned to, a list of them for a band over near-degenerate levels
                (an either-or), or null for an unlabelled band. Labels steer the
                band assignment; a label naming no level is an error.
            fit_c: Fit Racah C as a free parameter. Default (null): fitted only when
                C is not given and three or more bands are all labelled; false holds
                C; true frees it regardless (then a warning says C is one of many).
            dq_bounds: Optional (lower, upper) Dq search range in cm^-1; by default
                derived from the lowest band. A Dq pinned at a bound is warned about.

        Returns:
            FitResult with the optimized Dq and B, the ground term the fit is
            referenced to, per-peak residuals and any non-fatal warnings; or a
            ComputeError when the problem is ill-posed (for example high-spin d5,
            which has no spin-allowed d-d transitions at all) or the optimizer
            cannot reach a physically valid minimum.

        Example:
            Fitting [Ni(H2O)6]2+ (d8) from its three spin-allowed bands:
            ts_fit_spectrum(d_count=8, observed_peaks_cm1=[8500, 13800, 25300])

        """
        if not observed_peaks_cm1:
            return ComputeError(error="At least one observed peak required")
        if len(observed_peaks_cm1) > 50:
            return ComputeError(error="Too many peaks (max 50); filter or summarize")

        try:
            fit = fit_spectrum(
                d_count,
                observed_peaks_cm1,
                C=C,
                spin_state=spin_state,
                include_spin_forbidden=include_spin_forbidden,
                dq_bounds=dq_bounds,
                band_labels=band_labels,
                fit_c=fit_c,
            )
        except (ValueError, RuntimeError) as exc:
            return ComputeError(error=f"Fitting failed: {exc!s}")

        peak_assignments = [
            SpectrumPeak(
                energy_cm1=energy,
                assignment=assignment,
                # Mirrors ts_spectrum_app: spin-forbidden bands are drawn faint.
                intensity=1.0 if spin_allowed else 0.05,
            )
            for energy, assignment, spin_allowed in fit.transitions
        ]

        # Proper R^2, against the variance of the observed peaks. The previous
        # formula divided by an uncentred sum of squares, which returned >= 0.999
        # for essentially any input and so could never signal a bad fit.
        mean_observed = sum(observed_peaks_cm1) / len(observed_peaks_cm1)
        total_ss = sum((p - mean_observed) ** 2 for p in observed_peaks_cm1)
        residual_ss = sum(r**2 for r in fit.residuals_cm1)
        r_squared = None if total_ss <= 0 else max(0.0, min(1.0, 1.0 - residual_ss / total_ss))

        records = labelled_bands(fit, d_count, observed_peaks_cm1)
        band_assignments = [
            BandAssignment(
                observed_cm1=observed,
                computed_cm1=computed,
                residual_cm1=computed - observed,
                level_uid=uid,
                label=record["assignment_unicode"],
            )
            for (observed, computed, uid), record in zip(fit.assignment, records, strict=True)
        ]

        def _minimum(
            m: tuple[float, float, float, float], source: Literal["held", "free_c"] = "held"
        ) -> FitMinimum:
            return FitMinimum(Dq=m[0], B=m[1], C=m[2], objective_cm1=m[3], source=source)

        minima = [_minimum(m) for m in fit.minima]
        minima += [_minimum(m, "free_c") for m in fit.free_c_minima]
        if minima:
            lowest = min(minima, key=lambda m: (m.objective_cm1, m.source != "held"))
            lowest.lowest_rmse = True

        return FitResult(
            d_count=d_count,
            fitted_Dq=fit.Dq,
            fitted_B=fit.B,
            fitted_C=fit.C,
            c_is_default=fit.c_is_default,
            c_constrained=fit.c_constrained,
            r_squared=r_squared,
            rmse_cm1=fit.rmse_cm1,
            observed_peaks_cm1=observed_peaks_cm1,
            predicted_peaks_cm1=[energy for energy, _a, _s in fit.transitions],
            peak_assignments=peak_assignments,
            ground_term=fit.ground_term,
            spin_state=fit.spin_state,
            # From the assignment, not fit.residuals_cm1: that one is in sorted band
            # order, and this field is documented per input peak.
            residuals_cm1=[a.residual_cm1 for a in band_assignments],
            warnings=fit.warnings,
            Dq_source=fit.dq_provenance,
            B_source=fit.b_provenance,
            C_source=fit.c_provenance,
            c_fitted=fit.c_fitted,
            c_candidates=[_minimum(m) for m in fit.c_candidates],
            c_range=fit.c_range,
            minima=minima,
            band_assignments=band_assignments,
            Dq_nu1=fit.dq_nu1,
            Dq_nu1_reason=fit.dq_nu1_reason,
            assumptions=list(fit.assumptions),
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
        d_count: D_COUNT_LITERAL,
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
            free_ion_B=float(result["free_ion_B"]),
            complex_B=fitted_B,
            beta=float(result["beta"]),
            covalency=str(result["covalency"]),
            suggested_ligands=list(result["suggested_ligands"]),
            interpretation=str(result["interpretation"]),
        )
