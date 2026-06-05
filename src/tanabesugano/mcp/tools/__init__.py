"""TanabeSugano MCP tool registration dispatcher.

Each domain submodule (`compute_tools`, `plot_tools`, `table_tools`,
`explain_tools`) exposes a single `register(mcp)` callable. The dispatcher
below invokes them in dependency order — compute first (others reuse its
models), then table/plot/explain which can be enabled or skipped without
breaking the others.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tanabesugano.mcp.tools.compute_tools import register as register_compute
from tanabesugano.mcp.tools.explain_tools import register as register_explain
from tanabesugano.mcp.tools.plot_tools import register as register_plot
from tanabesugano.mcp.tools.table_tools import register as register_table


if TYPE_CHECKING:
    from fastmcp import FastMCP


def register_tools(mcp: FastMCP) -> None:
    """Register every ts_* tool on *mcp* in dependency order."""
    register_compute(mcp)
    register_table(mcp)
    register_plot(mcp)
    register_explain(mcp)
