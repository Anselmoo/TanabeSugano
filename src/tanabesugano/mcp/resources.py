"""Register TanabeSugano MCP resources on a FastMCP server."""

from __future__ import annotations

import json

from typing import TYPE_CHECKING

from tanabesugano import __version__
from tanabesugano.mcp._compute import SUPPORTED_D_COUNTS
from tanabesugano.mcp._defaults import DEFAULTS
from tanabesugano.mcp._defaults import GROUND_STATE_NOTES


if TYPE_CHECKING:
    from fastmcp import FastMCP


def register_resources(mcp: FastMCP) -> None:
    """Register tanabesugano:// resources on *mcp*."""

    @mcp.resource("tanabesugano://version", title="TanabeSugano version")
    def resource_version() -> str:
        """Return the installed tanabesugano package version."""
        return __version__

    @mcp.resource(
        "tanabesugano://configs",
        mime_type="application/json",
        title="Supported d-configurations",
    )
    def resource_configs() -> str:
        """Return all supported d-electron configurations as JSON."""
        return json.dumps(
            [
                {
                    "d_count": d,
                    "ground_term": DEFAULTS[d]["ground_term"],
                    "matrix_size": DEFAULTS[d]["matrix_size"],
                    "default_B": DEFAULTS[d]["default_B"],
                    "default_C": DEFAULTS[d]["default_C"],
                }
                for d in SUPPORTED_D_COUNTS
            ],
            indent=2,
        )

    @mcp.resource(
        "tanabesugano://config/{d_count}",
        mime_type="application/json",
        title="One d-configuration",
    )
    def resource_config(d_count: str) -> str:
        """Return metadata + ground-state note for a single d-configuration."""
        try:
            d = int(d_count)
        except ValueError:
            return json.dumps({"error": f"invalid d_count: {d_count!r}"})
        if d not in SUPPORTED_D_COUNTS:
            return json.dumps({"error": f"d_count must be one of {SUPPORTED_D_COUNTS}"})
        cfg = DEFAULTS[d]
        return json.dumps(
            {
                "d_count": d,
                "ground_term": cfg["ground_term"],
                "matrix_size": cfg["matrix_size"],
                "default_B": cfg["default_B"],
                "default_C": cfg["default_C"],
                "notes": GROUND_STATE_NOTES[d],
            },
            indent=2,
        )
