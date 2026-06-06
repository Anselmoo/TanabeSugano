"""MCP server for TanabeSugano — exposes diagram solvers as MCP tools.

This subpackage wires TanabeSugano into the Model Context Protocol (MCP) so
AI assistants (Claude Desktop, Claude Code, Cursor, VS Code Copilot, and any
MCP-compatible host) can compute Tanabe-Sugano diagrams, render plots, and
inspect d-configurations as first-class tools.

The server is built on FastMCP 3.x and ships as an optional extra:

    pip install "tanabesugano[mcp]"
    # or with uv:
    uv add "tanabesugano[mcp]"
"""

from __future__ import annotations
