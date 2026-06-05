"""Register TanabeSugano MCP tools on a FastMCP server."""

from __future__ import annotations

import base64

from typing import TYPE_CHECKING

from fastmcp.tools import ToolResult
from mcp import types

from tanabesugano import __version__
from tanabesugano.mcp._compute import SUPPORTED_D_COUNTS
from tanabesugano.mcp._compute import compute_point
from tanabesugano.mcp._compute import sweep_dq
from tanabesugano.mcp._defaults import DEFAULTS
from tanabesugano.mcp._defaults import GROUND_STATE_NOTES
from tanabesugano.mcp.models import ComputeError
from tanabesugano.mcp.models import ComputeResult
from tanabesugano.mcp.models import DiagramPoint
from tanabesugano.mcp.models import DiagramResult
from tanabesugano.mcp.models import SupportedConfig
from tanabesugano.mcp.plotting import render_diagram_png


if TYPE_CHECKING:
    from fastmcp import FastMCP


def _resolve_bc(d_count: int, B: float | None, C: float | None) -> tuple[float, float]:
    cfg = DEFAULTS[d_count]
    return (B if B is not None else cfg["default_B"], C if C is not None else cfg["default_C"])


def register_tools(mcp: FastMCP) -> None:
    """Register the ts_* tool family on *mcp*."""

    @mcp.tool(
        name="ts_supported_configs",
        title="Supported d-configurations",
        tags={"tanabesugano", "metadata"},
        meta={"domain": "tanabesugano", "surface": "mcp", "read_only": True},
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
        tags={"tanabesugano", "compute"},
        meta={"domain": "tanabesugano", "surface": "mcp", "read_only": True},
    )
    def ts_compute(
        d_count: int,
        Dq: float,
        B: float | None = None,
        C: float | None = None,
    ) -> ComputeResult | ComputeError:
        """Solve the d^n ligand-field Hamiltonian at a single (Dq, B, C) point.

        Args:
            d_count: d-electron count (2..8).
            Dq: Crystal-field strength in cm^-1.
            B: Racah B parameter (cm^-1). Defaults to the per-configuration value.
            C: Racah C parameter (cm^-1). Defaults to the per-configuration value.

        Returns eigenvalues grouped by spectroscopic term symbol.

        """
        if d_count not in SUPPORTED_D_COUNTS:
            return ComputeError(error=f"d_count must be one of {SUPPORTED_D_COUNTS}; got {d_count}")
        b_val, c_val = _resolve_bc(d_count, B, C)
        try:
            terms = compute_point(d_count, Dq, b_val, c_val)
        except (ValueError, RuntimeError) as exc:
            return ComputeError(error=str(exc))
        return ComputeResult(d_count=d_count, Dq=Dq, B=b_val, C=c_val, terms=terms)

    @mcp.tool(
        name="ts_diagram",
        title="Compute a Tanabe-Sugano diagram",
        tags={"tanabesugano", "compute", "diagram"},
        meta={"domain": "tanabesugano", "surface": "mcp", "read_only": True},
    )
    def ts_diagram(
        d_count: int,
        dq_min: float = 0.0,
        dq_max: float = 1500.0,
        steps: int = 50,
        B: float | None = None,
        C: float | None = None,
    ) -> DiagramResult | ComputeError:
        """Sweep Dq and return all term eigenvalues per point.

        Args:
            d_count: d-electron count (2..8).
            dq_min: Lower Dq bound of the sweep (cm^-1).
            dq_max: Upper Dq bound of the sweep (cm^-1). Default 0..1500 covers
                the typical octahedral crystal-field strength region.
            steps: Number of sample points (>=2).
            B: Optional Racah B parameter; defaults to the per-configuration value.
            C: Optional Racah C parameter; defaults to the per-configuration value.

        """
        if d_count not in SUPPORTED_D_COUNTS:
            return ComputeError(error=f"d_count must be one of {SUPPORTED_D_COUNTS}; got {d_count}")
        b_val, c_val = _resolve_bc(d_count, B, C)
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
        name="ts_plot_png",
        title="Render a Tanabe-Sugano diagram (PNG)",
        tags={"tanabesugano", "plot"},
        meta={"domain": "tanabesugano", "surface": "mcp", "read_only": True},
    )
    def ts_plot_png(
        d_count: int,
        dq_min: float = 0.0,
        dq_max: float = 1500.0,
        steps: int = 50,
        B: float | None = None,
        C: float | None = None,
        normalize: bool = True,
        dpi: int = 120,
    ) -> ToolResult:
        """Render a matplotlib PNG of the Tanabe-Sugano (or DD-energy) diagram.

        Use this as the default low-token-cost visualization. For interactive
        line-plots in capable clients, prefer ts_plot_view.
        """
        if d_count not in SUPPORTED_D_COUNTS:
            return ToolResult(
                content=[
                    types.TextContent(
                        type="text",
                        text=f"d_count must be one of {SUPPORTED_D_COUNTS}; got {d_count}",
                    ),
                ],
            )
        b_val, c_val = _resolve_bc(d_count, B, C)
        png = render_diagram_png(
            d_count=d_count,
            dq_min=dq_min,
            dq_max=dq_max,
            steps=steps,
            B=b_val,
            C=c_val,
            normalize=normalize,
            dpi=dpi,
        )
        b64 = base64.b64encode(png).decode()
        return ToolResult(
            content=[types.ImageContent(type="image", data=b64, mimeType="image/png")],
        )

    @mcp.tool(
        name="ts_explain",
        title="Explain a d-configuration",
        tags={"tanabesugano", "docs"},
        meta={"domain": "tanabesugano", "surface": "mcp", "read_only": True},
    )
    def ts_explain(d_count: int) -> str | ComputeError:
        """Return a one-paragraph description of the d^n ground state and spectrum."""
        if d_count not in SUPPORTED_D_COUNTS:
            return ComputeError(error=f"d_count must be one of {SUPPORTED_D_COUNTS}; got {d_count}")
        cfg = DEFAULTS[d_count]
        note = GROUND_STATE_NOTES[d_count]
        return (
            f"d{d_count} configuration — ground term {cfg['ground_term']}, "
            f"matrix sum dim {cfg['matrix_size']}, "
            f"default Racah B={cfg['default_B']:g} cm^-1, C={cfg['default_C']:g} cm^-1. "
            f"Library version {__version__}. {note}"
        )
