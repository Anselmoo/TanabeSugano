"""Register TanabeSugano MCP prompts on a FastMCP server."""

from __future__ import annotations

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from fastmcp import FastMCP


def register_prompts(mcp: FastMCP) -> None:
    """Register tanabesugano_* prompts on *mcp*."""

    @mcp.prompt(
        name="tanabesugano_explain_complex",
        title="Interpret a transition-metal complex absorption spectrum",
        tags={"tanabesugano", "interpretation"},
    )
    def tanabesugano_explain_complex(
        d_count: int,
        absorption_peaks_cm1: str = "",
    ) -> str:
        """Frame a guided interpretation of a d^n complex from measured absorptions.

        Args:
            d_count: d-electron count of the central metal (2..8).
            absorption_peaks_cm1: Optional comma-separated peak positions in cm^-1
                (e.g., "17500, 24500, 38000").

        """
        peaks_text = (
            f"Measured absorption maxima: {absorption_peaks_cm1} cm^-1."
            if absorption_peaks_cm1.strip()
            else "No measured peaks provided yet."
        )
        return (
            f"You are helping interpret the electronic absorption spectrum of an "
            f"octahedral d{d_count} transition-metal complex. {peaks_text}\n\n"
            "Plan:\n"
            f"1. Call `ts_supported_configs` to confirm d{d_count} is supported.\n"
            f"2. Call `ts_explain` with d_count={d_count} for ground-state context.\n"
            f"3. Call `ts_diagram` (default sweep) and identify which Dq/B value "
            "reproduces the measured peaks. If no peaks were provided, ask for them.\n"
            "4. Render `ts_plot_png` with the fitted Dq region for visual confirmation.\n"
            "5. Report assigned transitions (ground term -> excited terms), the "
            "fitted Dq and Racah B, and any deviations that suggest distortion or "
            "low-spin behavior."
        )
