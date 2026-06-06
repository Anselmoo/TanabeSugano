# Changelog

## [Unreleased]

### Removed
- `ts_explore_app`: the Prefab `Form.from_model` rendered as a frozen panel in Claude Desktop, and its `on_submit=CallTool(tool="ts_diagram_app")` wiring went stale after `ts_diagram_app` migrated to the Chart.js `ToolResult` path (the form's submit no longer matched a Prefab-state consumer). Discovery now goes through the `tanabesugano_why` / `tanabesugano_explain_complex` prompts or `ts_supported_configs` → `ts_diagram_app`

### Changed
- `ts_oxidation_landscape_app` no longer connects independent d-counts with lines: scatter is now the default `style` and every series carries `style: "scatter"` so the Chart.js renderer disables interpolation between d=2, 3, 4 … (previously it drew a misleading sawtooth across physically unrelated configurations). Added a `style="density"` mode that emits a Gaussian-broadened 2D heatmap via the existing `chartjs-chart-matrix` renderer — for each (d, E) cell, value = Σᵢ exp(-(E−Eᵢ)²/(2σ²)) over that d-count's eigenvalues. New `broadening_cm` (σ, default 800 cm⁻¹) and `n_energy_points` (vertical resolution, default 200) parameters control the density grid
- `_DIAGRAM_HTML` (`ui://tanabesugano/diagram.html`) now also imports `chartjs-chart-matrix` and routes to the matrix renderer when the payload carries `chart_type: "heatmap"`; default behaviour for every existing caller (line plot, no `chart_type` field) is unchanged

### Added
- `ts_oxidation_landscape_app`: scatter chart showing every eigenvalue of d²–d⁸ on one Chart.js plot at fixed (Dq, B, C), grouped by spin multiplicity — lets the user see how the term-energy spread evolves across the d-block at a single crystal-field setting
- `ts_compute_app`: sortable DataTable + spin-multiplicity strip plot of every eigenvalue at one (Dq, B, C); replaces the raw `ts_compute` whose nested-dict output was unusable

### Removed
- `ts_compute` and `ts_diagram`: their flat ``{term: [eigvals]}`` and full-sweep JSON payloads were unreadable; Claude consistently suggested "save to CSV / render PNG" follow-ups the client cannot execute. Replacements: `ts_compute_app`, `ts_diagram_app`, `ts_plot_view`, `ts_plot_png` (visualisation) and `ts_terms_table_data` (machine-readable rows)

### Fixed
- migrate `ts_diagram_app` and `ts_compare_app` off Prefab UI `LineChart`: that component renders as a black canvas in current Claude Desktop builds even when fed valid data (verified empirically — 12 series with varying y-values still produced a blank panel). Both tools now use the Chart.js HTML resource (`ui://tanabesugano/diagram.html`) — the same path proven to work in `ts_plot_view`, `ts_overlay_app`, `ts_spectrum_app`, and `ts_ratio_fit_app`. `ts_diagram_app` becomes a richly-titled single-config plot (use `ts_compute_app` / `ts_terms_table_data` for the sortable level table that the old slider+DataTable provided); `ts_compare_app` overlays its d-counts on one chart with `dN` prefixes on each series label
- drop the Prefab `LineChart` strip plot from `ts_compute_app` for the same reason; the Metric cards + sortable DataTable remain Prefab-native (those components do render). Users wanting a strip plot use `ts_oxidation_landscape_app`
- `ts_parameter_heatmap_app` three bugs in one tool: (1) free-ion ground term (`6S` from the dashboard) silently returned NaN at every cell because the solver uses octahedral keys like `6_A_1` — added `resolve_term_key` helper that accepts both forms and a `GROUND_TERM_OCTAHEDRAL` mapping in `_defaults.py`; (2) NaN values are not valid JSON so strict parsers (Chart.js included) crashed with "Unexpected token N" — empty/failed cells now emit `null`; (3) the tool returned `PrefabApp` but the consuming HTML at `ui://tanabesugano/heatmap.html` did `JSON.parse(content[0].text)` which got the literal placeholder `"[Rendered Prefab UI]"` — switched to `ToolResult(content=[TextContent(text=json)])` matching the other Chart.js-backed tools (ts_plot_view / ts_overlay_app / ts_ratio_fit_app); also added a structured error listing valid term keys when an unknown term is passed
- enrich `ts_dashboard_app` cards with a concrete assignable transition: each card now shows the lowest excited term + energy at a reference 10Dq = 10 000 cm⁻¹ (e.g. `→ ³T₂g: 8,812 cm⁻¹ @ 10Dq = 10000`) so chemists see the actual absorption-band data, not just static textbook-style metadata
- harden the MCP smoke tests: previously they only checked `is_error=False`, which passed even when every heatmap cell was NaN — new tests inspect actual content (assert every heatmap cell is finite or null, assert the diagram_app LineChart has varying series, pin the `[Rendered Prefab UI]` regression)
- switch dev-mode `.mcpb` from `uv tool run --from <local-path>` to `uv run --project <local-path> --extra mcp`: `uv tool run` caches the build in a hashed archive and never rebuilds it for local-path sources, so source edits never reached the running server (this is why the `data`-envelope fix appeared to do nothing — the deployed bundle was still running pre-fix code from `~/.cache/uv/archive-v0/.../site-packages/tanabesugano/`); `uv run --project` uses the project's editable venv so edits propagate without any cache-busting flags
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
