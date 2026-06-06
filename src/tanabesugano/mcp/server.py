"""TanabeSugano FastMCP server entry point."""

from __future__ import annotations

import argparse
import sys

from typing import TYPE_CHECKING
from typing import Any

from tanabesugano import __version__


if TYPE_CHECKING:
    from fastmcp import FastMCP

_INSTALL_HINT = (
    "FastMCP is not installed. Install the MCP extra:\n"
    "    pip install 'tanabesugano[mcp]'\n"
    "    # or: uv add 'tanabesugano[mcp]'\n"
)


def create_server() -> FastMCP[Any]:
    """Build and configure the TanabeSugano FastMCP server."""
    try:
        from fastmcp import FastMCP
    except ImportError as exc:
        raise SystemExit(_INSTALL_HINT) from exc

    from tanabesugano.mcp.apps import register_apps
    from tanabesugano.mcp.prompts import register_prompts
    from tanabesugano.mcp.resources import register_resources
    from tanabesugano.mcp.tools import register_tools

    mcp: FastMCP[Any] = FastMCP(
        name="tanabesugano",
        instructions=(
            "MCP server for TanabeSugano. Exposes d2-d8 Tanabe-Sugano and "
            "energy-correlation diagram computation, term-symbol eigenvalues, "
            "and matplotlib plots. Use ts_supported_configs to discover what "
            "is available; ts_compute / ts_diagram for numbers; ts_plot_png "
            "for a cheap visualization or ts_plot_view for an interactive "
            "line plot in capable clients."
        ),
        version=__version__,
    )

    register_tools(mcp)
    register_resources(mcp)
    register_prompts(mcp)
    register_apps(mcp)
    return mcp


def main() -> None:
    """Console-script entry point for `tanabesugano-mcp`."""
    parser = argparse.ArgumentParser(
        prog="tanabesugano-mcp",
        description="Run the TanabeSugano MCP server.",
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "http"],
        default="stdio",
        help="Transport protocol (default: stdio, for Claude Desktop and similar).",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Bind host for HTTP transport (default: 127.0.0.1).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port for HTTP transport (default: 8000).",
    )
    args = parser.parse_args()

    try:
        server = create_server()
    except SystemExit as exc:
        sys.stderr.write(str(exc))
        sys.exit(1)

    if args.transport == "http":
        server.run(transport="http", host=args.host, port=args.port)
    else:
        server.run(transport="stdio")


if __name__ == "__main__":
    main()
