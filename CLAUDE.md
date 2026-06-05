# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & test

```bash
uv sync --all-groups                       # install dev deps (Python ≥ 3.12 required)
uv sync --all-groups --extra mcp           # include the FastMCP server extra
uv run ruff check src/                     # lint
uv run ruff format --check src/            # format check
uv run pytest -vv                          # full test suite with coverage
uv run pytest -vv -m mcp                   # MCP tests only (requires the [mcp] extra)
uv build                                   # wheel + sdist via uv_build backend
```

CI mirrors this on Python 3.12, 3.13, and 3.14.

## Architecture

Two product surfaces share a single solver core:

1. **`tanabesugano` CLI** (`src/tanabesugano/cmd.py` → `cmd_line()`) — argparse pipeline that computes a Tanabe-Sugano (or DD-energy) diagram for a chosen d-configuration and renders it via matplotlib.
2. **`tanabesugano-mcp` MCP server** (`src/tanabesugano/mcp/server.py`) — optional FastMCP 3 server exposing the same solvers as MCP tools, resources, and prompts. Installed via the `[mcp]` extra; never required at runtime for the CLI.

Solver core (do not duplicate logic in the MCP layer):

- `src/tanabesugano/matrices.py` — `LigandFieldTheory` base and `d2 … d8` subclasses, each with a `.solver()` returning `dict[str, np.ndarray]` of eigenvalues per term symbol.
- `src/tanabesugano/batch.py` — `ELECTRON_CONFIG_SOLVERS` dispatch + `Batch` class for sweeps.
- `src/tanabesugano/tools.py` — Slater-Condon ↔ Racah parameter transforms.
- `src/tanabesugano/constants.py` — `ElectronConfiguration` enum + numerical tolerances.

MCP layer (`src/tanabesugano/mcp/`):

- `server.py` — `create_server()` + `main()`. Soft-imports `fastmcp` and exits with an install hint when the extra is missing.
- `tools.py` — `register_tools(mcp)` registers the `ts_*` tool family (compute / diagram / plot / explain).
- `resources.py` — `register_resources(mcp)` registers `tanabesugano://…` resources.
- `prompts.py` — `register_prompts(mcp)` registers the `tanabesugano_explain_complex` prompt.
- `apps.py` — `register_apps(mcp)` wires optional FastMCP `apps` providers (Generative UI + Prefab `LinePlot`); each integration silently no-ops if its dependency is missing.
- `_compute.py` / `plotting.py` / `_defaults.py` / `models.py` — internals shared by the layer.

## Conventions

- Scientific identifiers (`Dq`, `B`, `C`, `d2` … `d8`, term symbols like `A_1_1_states`) keep their canonical casing — ruff rules `N801/N802/N803/N806/N815/N816` are project-wide ignored to allow this.
- All public Python in `src/tanabesugano/` carries `from __future__ import annotations` (ruff `I002`).
- `cmd.py` intentionally shadows the stdlib `cmd` name; `A005` is ignored.
- Tests live next to the package under `src/tanabesugano/test/`. They run via `pytest` with `--cov=src/tanabesugano`.

## MCP design notes (when adding tools)

- Default visualizations use matplotlib PNG (`ts_plot_png`) to keep token cost low. Interactive views (`ts_plot_view` via `apps.prefab.LinePlot`) are opt-in and only registered when the extra is installed.
- Tool names use the `ts_` prefix. Each tool returns a typed Pydantic model from `mcp/models.py` (or `ComputeError` on validation failure). Avoid raising — return the error model so agents can recover.
- Add new tools through `register_tools(mcp)` in `mcp/tools.py`; do not register at import time.
- Per-configuration Racah defaults live in `mcp/_defaults.py`. Keep them in sync with `matrices.d{N}.__init__` signatures.

## Skills & agents (this repository)

- `.claude/skills/tanabesugano-compute/SKILL.md` — when and how to call the compute/diagram tools.
- `.claude/skills/tanabesugano-plot/SKILL.md` — choose between PNG (default) and Prefab line plot.
- `.claude/agents/ts-diagram-curator.agent.md` — autonomous agent for end-to-end spectrum interpretation.

## Release bundle (.mcpb)

`scripts/build_mcpb.py` builds `dist/tanabesugano-<version>.mcpb` — a Claude Desktop / DXT bundle containing a manifest v0.4 and a stdlib-only `uv tool run` launcher shim. The `.github/workflows/mcpb.yml` workflow runs this on push, validates the archive, and uploads it as a build artifact.
