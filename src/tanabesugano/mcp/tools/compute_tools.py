"""Numeric ts_* tools: listing, single-point compute, swept diagrams."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tanabesugano import __version__
from tanabesugano.mcp._compute import SUPPORTED_D_COUNTS
from tanabesugano.mcp._compute import compute_point
from tanabesugano.mcp._compute import sweep_dq
from tanabesugano.mcp._defaults import DEFAULTS
from tanabesugano.mcp._inputs import D_COUNT_LITERAL
from tanabesugano.mcp.models import ComputeError
from tanabesugano.mcp.models import ComputeResult
from tanabesugano.mcp.models import DiagramPoint
from tanabesugano.mcp.models import DiagramResult
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
