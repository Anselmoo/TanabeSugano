# Changelog

## [Unreleased]

### Fixed
- defensively unwrap `{"data": {...}}` tool-call args in a FastMCP middleware so calls from clients that wrap flat args in a `data` envelope (a recent Claude Desktop build was observed doing this) no longer fail with Pydantic's confusing dual error (`Unexpected keyword argument: data` + `Missing required argument: d_count`); our advertised inputSchemas remain flat
- rework `ts_dashboard_app` so cards actually convey useful information: each card now shows the matrix size, representative free ions (Fe²⁺, Co³⁺, …) from `ION_BY_D_COUNT`, a one-line chemical note from `GROUND_STATE_NOTES`, and a Sparkline of the **first excited state energy** across the Dq sweep (the lowest d-d band an absorption spectrum would show) — previously every sparkline was a flat zero line because it tracked the self-zeroed ground-term energy
- validate `d_count` centrally in `resolve_bc` — invalid values now raise a clear `ValueError` listing supported configurations instead of bubbling up as `KeyError: 99`; fixes `ts_diagram_app`, `ts_spectrum_app`, `ts_reverse_fit_app`, `ts_ratio_fit_app`, and any future tool sharing the helper
- expand MCP smoke tests to cover all 10 app tools (added `ts_overlay_app`, `ts_spectrum_app`, `ts_reverse_fit_app`, `ts_ratio_fit_app`) plus a regression test pinning Claude Desktop's stringified-args coercion (`{"d_count": "5", "normalize": "true"}` must produce identical output to typed args) — `apps.py` coverage from 53% → 79%
- fix `ts_dashboard_app` and `ts_compare_app` crash: NumPy 2.4.x made 1-D array assignment to scalar slot a hard `ValueError`; `d7.solver()` used `T_4_1[0] = np.array([0.0])` instead of the scalar `T_4_1[0] = 0.0`
- fix style inconsistency in `d8.solver()`: `A_3_2 = np.array([0], dtype=float)` now uses `dtype=np.float64` consistent with d3, d4, d6
- fix mcpb tool environment numpy version drift: `build_mcpb.py` now reads the numpy version from `uv.lock` and pins it in the manifest args (`--with numpy=={version}`) so the installed mcpb never resolves a newer breaking numpy
- fix division by zero in `_sweep_payload` when `B=0` and `normalize=True` (x-axis row was unguarded; y-axis guard already existed)
- fix `min()` on empty iterator in `_sweep_payload` when solver returns no data (`default=0.0` added)
- fix `ts_diagram_app` and `ts_compare_app` black chart: `LineChart` from `prefab_ui` uses camelCase params (`xAxis`, `showLegend`, `showTooltip`, `showGrid`, `showDots`); the snake_case names were silently dropped by Pydantic, leaving the chart with no x-axis key and no configuration → black canvas

### Added
- add `--dev` mode to `build_mcpb.py` and `poe build-mcpb-dev` task for building a .mcpb that points to the local source tree before PyPI publication; both modes now pin the fastmcp version from `uv.lock` via `--with fastmcp[apps]=={version}` to prevent Claude Desktop cycling caused by version drift
- add poethepoet task runner with `build-mcpb`, `build-mcpb-dev`, `lint`, `format`, `test`, and `test-mcp` tasks; `uv run poe build-mcpb-dev` produces a local-source Claude Desktop bundle
- document all MCP server tools, interactive app tools, and prompts in README (ts_fit_spectrum, ts_nephelauxetic, ts_terms_table_data, and all nine Prefab-UI app tools were previously undocumented)
- add rrt pre-commit hooks and unified cicd workflow
- add spectrum fitting tool (`ts_fit_spectrum`) to extract Dq and B parameters from observed UV-Vis absorption peaks
- add scipy dependency for least-squares optimization in spectrum fitting
- add comprehensive test suite for spectrum fitting with validation against real coordination complex spectra
- add pattern documentation for Algorithm Selection + Lazy Computation dogma in spectrum fitting
- add nephelauxetic analysis tool (`ts_nephelauxetic`) interpreting a fitted Racah B as metal-ligand bond covalency via β = B(complex)/B(free ion), with free-ion B tables and ligand-series suggestions
- add UV-Vis reference spectra assets (`assets/uvvis/`) with a generator script (`scripts/plot_uvvis_fits.py`) for the Ni(II) spectrum-fitting examples
- export UV-Vis reference spectra as self-describing tab-separated ASCII `.txt` datasets (wavenumber / wavelength / absorbance) alongside the figures
- harden MCP tool input validation (`ts_plot_png`, `ts_terms_table_data`, `ts_plot_view`, `ts_reverse_fit`) to return structured errors instead of raising
- add Playwright screenshot tests (`test_screenshots.py`, `screenshot` mark) and gitignore the generated `test-screenshots/` output
- update `.gitignore` to exclude python and node modules in the correct fashion
- update `cicd.yml` to use the correct version of `repo-release-tools` for validating release policies
- add initial `tree.lock.toml` for dependency management and add screenshot tests to CI/CD pipeline and exclude them from coverage
- add step to resolve wheel path before generating SPDX SBOM
- fix update branch references from master to main in CI/CD configuration

---

## Before v1.2.0

* Adding `Changelog.md`
* Add `poetry` for dependecy mangament
  * `setup.py` depends now on the `project.toml`
* Modified the `GitHub-Actions`
* Introduced `TanabeSugano` batch for extending analysis of correlation matrices
