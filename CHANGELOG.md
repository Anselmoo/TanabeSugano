# Changelog

## [Unreleased]

### Fixed
- fix `ts_dashboard_app` and `ts_compare_app` crash: NumPy 2.4.x made 1-D array assignment to scalar slot a hard `ValueError`; `d7.solver()` used `T_4_1[0] = np.array([0.0])` instead of the scalar `T_4_1[0] = 0.0`
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
