# Changelog

## [Unreleased]
### Changed

- **One notation ladder now spans four renderers.** Plotly surfaces get a new
  fourth rung, `term_to_plotly` / `Level.parent_plotly`, emitting
  `<sup>3</sup>T<sub>1g</sub>(F)`. The committed `.html` diagrams had shown raw
  solver keys (`3_T_1_0`) and the docs app showed `3 T 1 0`
- **One colour standard.** Three palettes disagreed: `mcp/apps.py` carried an
  Okabe-Ito copy **shifted by one multiplicity** (a quartet rendered green in
  matplotlib and vermillion in the oxidation-landscape chart), and the React
  docs app carried a hand-written "Alucard" palette mapping 2→cyan / 4→orange
  where Okabe-Ito says 2→orange / 4→green. `mcp/apps.py` in fact held **two**
  shifted copies, and `ts_spin_crossover_app` hardcoded its two ground-state
  curves, so the low-spin curve of d6 — a singlet — drew in the triplet blue.
  All deleted; `plot_style.SPIN_COLORS` and the new `color_for_multiplicity`
  are the only source, pinned by a test that fails on any `"#rrggbb"` literal
  outside `plot_style`
- **Dash now encodes spin-allowedness, not level index.** It used to cycle
  through five patterns by level, which recycles while d6's `3_T_1` holds seven
  levels — the channel was ambiguous *and* carried an internal ordinal that
  appears in no textbook. Solid now means a transition from the ground level is
  spin-allowed. Level index moved to a lightness ramp. Consequence worth stating:
  d5 comes out entirely dashed, which is why Mn(II) is pale
- Committed `.html` diagrams now reference plotly.js from the CDN instead of
  inlining a 4.9 MB copy each: `ts-diagrams/` went from 80 MB to about 20 MB
  even after gaining 28 figures. `poe regen-diagrams-offline` and the
  `-html-offline` CLI flag write self-contained copies for offline reading
- `docs-site/` deleted — 36 tracked files, ~80 MB, with no `package.json` and
  no `src/`, built by no workflow. The live Vite app is `docs/`, whose
  `package.json` is confusingly *named* `docs-site`

### Added

- Every diagram now ships a matplotlib PNG and PDF beside its CSV and HTML (14
  diagrams x 2 formats), rendered by `poe regen-diagrams` at 200 sweep points
- `manifest.json` carries a `series` block per diagram — label, colour, dash and
  uid per CSV column — so the React app holds no palette and no label formatter
  of its own
- `src/tanabesugano/figure_style.py`, the single place that decides how a level
  is drawn, shared by matplotlib, plotly, Chart.js and the manifest
- `LevelSet.display_labels(renderer)`, which guarantees no two levels on a
  figure share a label. Parentage is not injective — d4, d5 and d6 each hold
  two pairs whose `parent_*` labels are byte-identical (d6: two `3T1g(H)`) — so
  only the colliding pairs gain the ordinal, as `3T1g(H,a)` / `3T1g(H,b)`
- `scripts/record_interactive_gif.py` and `poe regen-gif`: the README's
  interactive GIF was a hand-made screen recording, which is why it still showed
  the old raw legend keys. Deliberately outside `regen-all` (needs a browser)
  and outside the drift gate (a recording is not reproducible frame-for-frame)

### Fixed

- Matplotlib figures named only the FIRST level of each term (`label=... if n == 0 else None`),
  so every dashed curve was anonymous by construction. All levels are now
  labelled directly on the curve in free-ion parentage, with a legend that
  explains the visual channels instead of listing states
- `cmd.plot()` legends used the raw solver key rather than typeset notation
- `scripts/plot_uvvis_fits.py` and `script_export.py` each declared their own
  `OBSERVED_COLOR` and disagreed — vermillion in one figure surface, blue in the
  other, for figures a reader compares side by side. Both now read named roles
  from `plot_style.ANNOTATION_COLORS`, which is kept separate from the
  multiplicity palette because nothing indexes it by a number
- `cmd._split()` rendered every single-level A and T term in the fallback grey:
  each such key already ends in a digit, so `"3_A_1"` split into `("3_A", 1)`
  and `color_for("3_A")` matched nothing. `figure_style.column_to_uid` resolves
  the split against `TermKey` membership instead
- The HTML drift gate would have become a permanent pass. It grepped raw term
  keys out of the embedded data, and typesetting the legends removed them — an
  empty set compares equal to any other empty set. It now reads `trace.meta.uid`
  and raises `VacuousGateError` rather than comparing nothing
- `scripts/regenerate_ts_diagrams.py` decided which directories get HTML by
  checking which already contained HTML, so deleting every `.html` once made the
  tree unable to regenerate itself. The target is now declared

### Documentation

- Repaired three broken README links: the CI badge pointed at a workflow
  file (`python-package.yml`) that no longer exists — the workflow is now
  `cicd.yml`; the citation BibTeX carried the GitHub repository id as a
  Zenodo DOI (`10.5281/zenodo.206847682`), which 404s, replaced with the
  resolving concept DOI `10.5281/zenodo.3402463`; and the footer linked to
  `/discussions`, which 404s because Discussions is not enabled, repointed at
  the interactive diagrams site. Also added a 2.0.0 upgrade section

## [2.0.0-alpha.1] - 2026-08-20
### Changed

- **Regenerated every committed artifact against the 2.0.0 CLI** — 42 CSVs, 28
  interactive `.html` diagrams, both `manifest.json` indexes, the `examples/`
  tables and figures, and the UV-Vis reference PNGs. The `.html` diagrams were
  the worst of it: they still named `1_T_3`, an irrep that does not exist in
  Oh, because nothing had regenerated them since the rename, and two carried
  names from an older buggy scheme (`B_918.0_C_4132`, a truncated `C_413`).
  `scripts/regenerate_ts_diagrams.py` now covers `.html` and `manifest.json`
  as well as `.csv`, so all three are guarded by the existing CI drift gate
  rather than only the CSVs
- `examples/` moved from `.txt` to the `.csv` the CLI has actually emitted for
  some time, and its two README figures were regenerated through the shared
  renderer. They had been *screenshots of a matplotlib window* — macOS title
  bar and toolbar included — in a palette predating `plot_style`. New
  `scripts/regenerate_examples.py` makes them reproducible


- **BREAKING** — `matrices.dN.solver()` now returns a `LevelSet` instead of
  `dict[TermKey, Float64Array]`. `LevelSet` is **not** a Mapping: `states[key]`,
  `states.items()` and `len(states)` all raise `TypeError`.
  *Migration:* call `.as_dict()` to recover the old shape, or iterate
  `.levels`, which is what the new code does. A bare dict cannot express a
  multiplet — for d8 it mapped `3_T_1` to a two-element array, so `ν₂` and `ν₃`
  both came back labelled `3_A_2→3_T_1` and were indistinguishable
- **BREAKING** — term keys renamed: `1_T_3` → `1_T_2` (no T₃ irrep exists in
  Oh) and `*_E_1` → `*_E` (Eg carries no subscript in Oh). Both were spelling
  defects that survived for the life of the project because the term regex was
  permissive. *Migration:* update any literal key match; `TermKey` now makes
  both spellings unwritable. This also renames the corresponding **CSV
  columns** in the shipped `ts-diagrams/**` artifacts
- **BREAKING for downstream CSV consumers** — the committed
  `ts-diagrams/**` artifacts changed in three ways: the `delta_B` column held
  `Dq/B` while labelled `Δ/B` and is now **10× larger** (the old values were
  wrong); the cm⁻¹→eV factor was `0.00012` and is now `1/8065.54`; and columns
  are renamed as above and reordered (dict-insertion → sorted) as a
  consequence of the `LevelSet` return shape. Values are otherwise unchanged —
  verified cell-by-cell, matched by column name, across all 42 regenerated
  files. A `--check` step in CI now guards these

### Added

- README examples are now **executed by the test suite**. The README documented
  `from tanabesugano import TanabeSugano` for years; that class has never
  existed and raised `ImportError` on every released version, because nothing
  ever ran it. Replaced with the real `LevelSet` / `Batch` API, and every
  ```python block is compiled and run — which immediately caught a second error
  in the replacement itself
- `tanabesugano.free_ion` — Racah's free-ion term energies for d2–d8 plus the
  L → Oh reduction. Moved out of `test_matrices_invariants.py` (not copied:
  the same closed form asserted in two places at two tolerances lets the
  looser mask the tighter) because `Level` now needs the free-ion term symbol.
  d2/d8 are new and joined the absolute oracle, which previously covered them
  only through relative checks
- free-ion parentage labels on `Level` — `parent_candidates`, `parent_symbol`,
  `parent_suffix`, `parent_label_display`, `parent_latex`, `parent_unicode`.
  d8's two ³T₁ levels now read `(F)` and `(P)` as the literature writes them
  rather than the positional `(a)`/`(b)`. Matching is on energy AND
  multiplicity AND irrep; where the answer is genuinely undecidable (d3/d7 put
  ²H and ²P at the same 9B+3C for every B and C, so three ²T₁ levels are
  indistinguishable by energy) both candidates are reported and the display
  falls back to the ordinal — nothing guesses
- `tanabesugano.script_export` and the `ts_fit_script` MCP tool — emit a
  standalone matplotlib script for an observed-vs-computed fit figure. The
  fitter's numbers are baked in as literals, and the script imports matplotlib
  and nothing else, so a reviewer can reproduce a published figure without
  installing this package
- `ts_fit_plot_app` — the inline counterpart, plotting residuals rather than
  raw band positions (a ~100 cm⁻¹ misfit is narrower than a marker on an
  8,000–26,000 cm⁻¹ axis). Both surfaces read one `labelled_bands()` so they
  cannot disagree about which computed line a band was assigned to
- `format` parameter on `ts_plot_png` for PDF and SVG export. MIME types are
  spelled out rather than derived: FastMCP's `File(format=...)` helper maps a
  bare extension to `application/<ext>`, yielding the unregistered
  `application/svg` and `application/png`

### Fixed

- `ts_plot_png`'s diagram emphasised and annotated the wrong curve. It chose
  the ground term as "lowest eigenvalue at the **first** Dq point", then drew
  the label at the **last** one. Two compounding errors: at Dq = 0 the ligand
  field vanishes so every crystal-field component of the free-ion ground term
  is exactly degenerate and the argmin is settled by a tie-break rather than by
  physics (d6 returned `5_E`, where even the weak-field answer is `5_T_2`); and
  d4–d7 cross over, so a correct weak-field answer still names the wrong term
  at strong field. Now evaluated at the annotated edge, which makes the label
  true where it is drawn — d6 reads `1_A_1`, d3 `4_A_2`, d8 `3_A_2`
- `LevelSet.for_term("3_T_1")` returned an empty tuple and no error. It
  compared with `is`, which is False for a plain string even though `TermKey`
  is a `StrEnum` and compares equal — the whole point of that design. Silent
  emptiness is the failure mode this package keeps re-learning; an unknown term
  still returns `()`, a known one spelled as a string no longer does
- `ts_spin_crossover_app` reported the critical Δ by scanning its drawing grid,
  so the answer was quantised to the sweep spacing — it overshot the true
  crossing by 167–450 cm⁻¹ and moved with `steps`, a parameter documented as
  drawing resolution. Now bisected with `crossover_dq()` (renamed from
  `_crossover_dq`, which gained a second consumer): d4 26,667 → 26,386,
  d5 24,545 → 24,332, d6 21,515 → 21,348, d7 21,212 → 21,059 cm⁻¹
- `ts_spin_crossover_app`'s default `dq_max` of 2500 put d⁴'s crossing (at
  Dq = 2639) outside the swept range entirely, so it reported no crossing at
  all at its own defaults; the docstring's claim that 2500 "leaves margin on
  both sides" was false for two of the four supported configurations. Raised to
  3500. This survived because every existing test passed `dq_max` explicitly,
  so the shipped default was never exercised

- `LigandFieldTheory.construct_matrix` was annotated `list[float]` /
  `dict[..., float]` while every call site actually passes `np.float64`
  values (coerced in `__init__`); switched to the covariant, read-only
  `Sequence[float]` / `Mapping[..., float]` supertypes, which both match
  runtime reality and clear ty's invariant-generics complaint
- `tools.racah()` used `np.array` (a function) as a type instead of an array
  type, and its single signature decorrelated the scalar/array-ness of the
  return value from the inputs; split into `@overload`s so `Batch`'s
  `self.B, self.C = racah(self.B, self.C)` keeps its arrays typed as arrays
- `_compute.nephelauxetic_analysis` returned the uninformative
  `dict[str, object]` (every value type technically satisfied, none of them
  named) instead of a `TypedDict` describing the actual fields; the three
  `# type: ignore[arg-type]` comments in `compute_tools.py` that leaned on
  that looseness used mypy's code spelling and were never honored by ty (ty
  only recognizes bare `# type: ignore` or its own `# ty: ignore[code]`), so
  they are removed now that the underlying types check out for real

## [1.8.0-alpha.1] - 2026-08-19
### Fixed

- CI could not resolve `astral-sh/setup-uv@v10`: that project stopped publishing
  floating major-version tags after v7, so `v8`/`v9`/`v10` do not exist as refs. Pinned
  to the exact `v10.0.1` release tag, which Dependabot's new `github-actions` coverage
  keeps current
- 7 npm advisories in `docs/package-lock.json` (5 high — vite path traversal and
  arbitrary file read, rollup path traversal, nanoid, postcss). Resolved within the
  existing semver ranges; the docs site still builds

- **the release pipeline never produced a GitHub Release.** `rrt release notes` was
  invoked with no target, so it read `[Unreleased]` — which `changelog_workflow =
  "incremental"` empties at bump time — and exited 1 on every tag. The job failed
  after PyPI had already published, and `release-assets` was skipped, so v1.7.0,
  v1.7.1 and v1.7.2 shipped to PyPI with no Release and no attached artifacts. The
  release job now targets the tag's own changelog section, falls back to
  `--latest-released` and then to a minimal body, and never fails a release whose
  artifacts are already public
- **the `.mcpb` bundle could not start.** Bundle generation relied on entry-script
  auto-detection, which picks the console script matching the package name — so the
  manifest launched the `tanabesugano` argparse CLI instead of `tanabesugano-mcp`.
  Under Claude Desktop the process sat on stdin and never answered the JSON-RPC
  `initialize` request (reproduced locally: `mcp2mcpb sandbox` times out). The entry
  script is now passed explicitly and asserted before release
- **`.mcpb` bundles were not version-pinned.** The runtime reference was
  `tanabesugano[mcp]` with no `==`, so a bundle labelled 1.7.2 installed whatever was
  newest on PyPI. Bundles now pin the exact published version
- **a failed tag pipeline could never be re-run.** `publish-pypi` had no
  `skip-existing`, so any re-run 400'd on the already-uploaded files and could never
  reach the release job
- pre-release tags were published as stable releases. `prerelease:` was hardcoded
  `false`, and the obvious fix — pattern-matching the tag — is also wrong, because
  `rrt bump alpha` writes SemVer-style `1.8.0-alpha.1` whose PEP 440 normalisation is
  `1.8.0a1`; a `(a|b|rc)[0-9]*$` regex reads the raw string as stable. Tags are now
  parsed with `packaging.version.Version`
- creating a Release by hand re-triggered the whole pipeline via `on: release:
  [published]`, and that path failed at SBOM with `Resource not accessible by
  integration`. The trigger is removed; tags are the only release path
- `test_front.py` used the `script_runner.run(a, b, c)` form deprecated by
  pytest-console-scripts

### Added

- `scripts/validate_mcpb.py` — asserts a built bundle's launch recipe (entry point,
  `[mcp]` extra, exact version pin) before it is attached to a Release. Verified to
  reject the bundle the previous pipeline produced. Expectations are derived from
  `pyproject.toml` (package name, the console script targeting the `mcp` package, and
  the `mcp` extra) while the workflow passes them to the builder explicitly, so the
  two sources cross-check each other
- `scripts/release_notes.py` — owns the release-body fallback chain (tag spelling →
  PEP 440 form → `--latest-released` → minimal body) outside the workflow YAML, so
  every branch can be exercised locally. It cannot fail: by the time it runs the
  artifacts are already on PyPI
- `scripts/release_version.py` — single source of truth for resolving a tag to its
  PEP 440 version, detecting pre-releases, and refusing to build when a tag disagrees
  with the artifact actually built
- `mcpb-smoke` job — runs `mcp2mcpb sandbox` against the real bundle after the Release
  exists, so a broken bundle reports loudly without blocking a published release
- release process documentation in `CONTRIBUTING.md`, including the two version
  spellings and how to verify a release body before pushing a tag
- `[tool.coverage]` configuration (branch coverage, test files omitted); the project
  previously ran coverage with no configuration at all
- `CITATION.cff` registered as an `rrt` version target — it had sat at 1.4.1 (2023)
  through nine releases

### Changed

- `release` and `release-assets` merged into one atomic job, removing the state that
  broke v1.7.x: a Release created with zero assets, or a PyPI publish with no Release.
  `fail_on_unmatched_files` is now `true`, so a missing `.mcpb` is an error
- the `.mcpb` bundle is built by invoking the pinned `mcp2mcpb==1.0.0` CLI directly
  rather than through the composite action, whose input mapping treats `--from-dist`
  and `--pin` as mutually exclusive — a release bundle needs both
- all GitHub Actions updated (`checkout` v4→v7, `setup-uv` v5→v10, `upload-artifact`
  v4→v7, `download-artifact` v4→v8, `action-gh-release` v2→v3, `repo-release-tools`
  v1.8.3→v1.15.0, and others), clearing the Node-20-on-Node-24 runner warnings
- dependency floors raised to versions that actually support `requires-python >=3.12`
  (`pandas>=2.2`, `matplotlib>=3.9`, `prettytable>=3.11`) and ceilings added where a
  major bump would be untested — notably `numpy<3`, whose version is baked into bundle
  manifests
- lifted the `pytest<9` and `pytest-cov<6` caps that were blocking upgrades; the suite
  passes on pytest 9.1.1 / pytest-cov 7.1.0
- `repo-release-tools` pinned consistently at 1.15.0 across `pyproject.toml`,
  `.pre-commit-config.yaml` and the workflow, resolving a three-way version skew
- Dependabot now covers `github-actions`, `pre-commit` and the previously ungoverned
  `docs/package.json`, and tracks `uv` (which understands `uv.lock`) rather than bare
  `pip`. The `pre-commit` ecosystem exists precisely to stop the hook-rev drift found
  here, where `repo-release-tools` was pinned at v1.8.3 while the lock resolved 1.9.0
- `uv_build` ceiling raised to `<0.14.0`; the previous `<0.12.0` already excluded the
  uv in use

### Removed

- the `update` dependency — declared since the project's early history and never
  imported anywhere in `src/` or `scripts/`
- the `pyupgrade` pre-commit hook — redundant with ruff's `UP` rules under
  `select = ["ALL"]`, and its `--py310-plus` target contradicted `requires-python >=3.12`
- the stale `.github/workflows/mcpb.yml` references in `README.md` and `CLAUDE.md`;
  that workflow was folded into `cicd.yml` and has not existed since

## [1.7.2] - 2026-06-22
### Changed
- CI/CD: switch mcpb job to use `Anselmoo/mcp2mcpb` composite action with `--from-dist` to build bundles from locally-built wheel (pinned to SHA `b040bab` — pre-release v0.5)

## [1.7.1] - 2026-06-10
### Fixed

- correct workflow pipeline for release

## [1.7.0] - 2026-06-09
### Fixed
- PNG export ("Send PNG to chat" button) was silently failing with "Send failed": the iframe JavaScript called `app.callTool()` but the MCP Apps SDK exposes `app.callServerTool()` — renamed to the correct method

### Removed
- `ts_parameter_heatmap_app`: a fixed-Dq sweep of Racah (B, C) of a single eigenvalue is not a standard coordination-chemistry visualisation (absent from Cotton, Figgis & Hitchman, Bertini, Lever) and the default user call against a ground-term level trivially returned 0 cm⁻¹ everywhere (user-reported uniformly dark heatmap for `d8 3_A_2 level 0 at Dq=900`). Replaced by three TS-companion tools (`ts_orgel_diagram_app` shipped now; `ts_spin_crossover_app` and `ts_correlation_diagram_app` follow)
- `ts_explore_app`: the Prefab `Form.from_model` rendered as a frozen panel in Claude Desktop, and its `on_submit=CallTool(tool="ts_diagram_app")` wiring went stale after `ts_diagram_app` migrated to the Chart.js `ToolResult` path (the form's submit no longer matched a Prefab-state consumer). Discovery now goes through the `tanabesugano_why` / `tanabesugano_explain_complex` prompts or `ts_supported_configs` → `ts_diagram_app`

### Fixed
- `_sweep_payload` in `apps.py` now returns a `ValueError` when `normalize=True` and `B ≤ 0`, instead of silently collapsing the entire x-axis to `0.0` and producing a misleading chart
- remove dead `resolve_term_key` helper from `tools/_shared.py` and its `GROUND_TERM_OCTAHEDRAL` comment from `_defaults.py`; the only consumer (`ts_parameter_heatmap_app`) was removed in a prior commit
- fix stale docstring/comments that still referenced the removed strip-plot in `ts_compute_app` and the removed `ts_parameter_heatmap_app` in the `apps.py` module docstring and `compute_tools.py` replacement comment
- expand `test_ts_emit_png_echoes_image_content` with empty-string and data-URI input branches to lock in those error and normalisation behaviours
- add `ts_correlation_diagram_app` and `ts_spin_crossover_app` to the generic app-tool smoke-test parametrisation so registration regressions are caught immediately
- fix README.md interactive-app-tools heading from "Prefab UI" to "Prefab / Chart.js UI" and correct `ts_compute_app` (no strip plot), `ts_diagram_app` (Chart.js only), and `ts_compare_app` (overlaid chart) descriptions
- fix CI/CD: tags trigger narrowed from `["v*", "*"]` to `["v*"]` — the catch-all `"*"` glob caused `publish-testpypi` to fire on every scratch tag push; `pages-build`/`pages-deploy` no longer allow `workflow_dispatch` from arbitrary branches (feature-branch docs were overwriting production GitHub Pages); `publish-testpypi` condition narrowed to `main`-only during the master→main migration

- the in-iframe **Copy to clipboard** button now actually works. The MCP Apps host sandboxes every UI iframe with no Permissions Policy by default, so `navigator.clipboard.write` was rejected silently — the toolbar always landed in the "Copy denied" branch. Fixed by declaring `_meta.ui.permissions.clipboardWrite` on both `ui://tanabesugano/diagram.html` and `ui://tanabesugano/spectrum.html` via FastMCP's `ResourcePermissions(clipboard_write={})`. The host now adds `allow="clipboard-write"` to the iframe element and the call succeeds. Reference: [MCP Apps stable spec 2026-01-26](https://github.com/modelcontextprotocol/ext-apps/blob/main/specification/2026-01-26/apps.mdx). Pinned by `test_ui_resources_request_clipboard_write_permission`
- update CI/CD pipeline to include master branch and refine conditions for pages build and deploy

### Changed
- the in-iframe **Download PNG** button is replaced with **Send PNG to chat**. The MCP Apps spec deliberately does **not** define a "downloads" permission (the supported set is `{camera, microphone, geolocation, clipboardWrite}` — see the 2026-01-26 spec) and the host strips `allow-downloads` from every UI iframe, so the previous `<a download>` click was silently suppressed by every browser. Instead, the button now captures the Chart.js canvas via `toBase64Image()` and calls back into a new server tool `ts_emit_png` through `app.callTool(...)`; the tool echoes the PNG as MCP `ImageContent` and the chat surface renders it inline, where the user can save / copy / share it. This is the only spec-compliant export path. Pinned by `test_ts_emit_png_echoes_image_content`

### Added
- `ts_emit_png` — internal export sink tool that accepts a base64-encoded PNG and a title, returns the image as MCP `ImageContent`. Lives in `tools/plot_tools.py`. Invoked from the toolbar JS, not the LLM (the server `instructions` documents that). Rejects empty / malformed base64 with a clear error message
- `ts_correlation_diagram_app` no longer drops the ground term. The Phase-2 commit (22e6011) included a `max(ys) - min(ys) < 1.0` post-filter intended to skip flat curves, but in normalised solver output the ground manifold sits at E ≈ 0 across all three regimes by construction — so the filter silently hid the ground term, defeating the diagram's pedagogical purpose (the whole point of a Tsuchida-style correlation diagram is to visualise ground-term continuity from free ion → weak field → strong field). Replaced with an empty-series guard. Regression-pinned in `test_correlation_diagram_app_emits_three_panels` by asserting the d³ ⁴A₂ ground term appears in the rendered series list
- `ts_spin_crossover_app` payload now emits both `critical_delta_cm1` (the Δ = 10·Dq value plotted on the x-axis, in cm⁻¹) **and** `critical_Dq_cm1` (the raw Dq parameter, exactly Δ/10). The Phase-2 commit (22e6011) wrote Δ into the `critical_Dq_cm1` field, so consumers reading the JSON got a value 10× the textbook number (d⁶ returned ~21465 instead of ~2146 cm⁻¹). The chart title and axis labels were always correct; only the JSON field name was wrong. Regression-pinned by asserting `critical_delta_cm1 ≈ 10 · critical_Dq_cm1` and that `critical_Dq_cm1 / B` falls in the textbook 1.5–3.5 band
- final stale-reference sweep flagged by `/code-review` before ship: the `tanabesugano_explain_complex` prompt still instructed the LLM to call the removed `ts_diagram` (rewritten to use `ts_fit_spectrum` → `ts_diagram_app` → `ts_terms_table_data`); two Claude Code skill files (`tanabesugano-compute`, `tanabesugano-explore`) and the `ts-diagram-curator` agent still recommended `ts_compute` / `ts_diagram` / `ts_explore_app`; the screenshot test parametrised `ts_explore_app`; `apps.py` had dead imports for `CallTool` and `LineChart` after the Prefab migration; the module docstrings in `apps.py` and `_inputs.py` advertised features (`LineChart`, `Form`, `ts_explore_app`) that no longer exist. All eight rewritten to point at live tools
- the three hand-registered `ui://tanabesugano/*` HTML resources now serve `text/html;profile=mcp-app` instead of plain `text/html`. The MCP Apps spec requires this profile suffix and Claude Desktop announces exactly that MIME during `initialize` (`extensions.io.modelcontextprotocol/ui`); plain `text/html` was rejected client-side as "Unsupported UI resource content format", which kept every Chart.js iframe (ts_diagram_app, ts_plot_view, ts_overlay_app, ts_compare_app, ts_oxidation_landscape_app, ts_parameter_heatmap_app, ts_spectrum_app, ts_ratio_fit_app) from rendering. The auto-generated `ui://prefab/tool/*/renderer.html` Prefab resources already used the correct MIME, which is why `ts_compute_app` and `ts_dashboard_app` worked. References: https://modelcontextprotocol.io/extensions/apps/overview and https://github.com/modelcontextprotocol/ext-apps

### Changed
- correct server `instructions` and `ts_compute_app` metadata that lagged behind the recent migrations: `ts_diagram_app` and `ts_oxidation_landscape_app` were grouped as "in-chat Prefab UI" but are now Chart.js, and `ts_compute_app`'s title/description still advertised a "strip plot" that was removed when the Prefab `LineChart` was dropped. The LLM reading these strings was being mis-directed; fixed across `server.py` instructions and `_register_compute_table` title + docstrings
- `ts_oxidation_landscape_app` no longer connects independent d-counts with lines: scatter is now the default `style` and every series carries `style: "scatter"` so the Chart.js renderer disables interpolation between d=2, 3, 4 … (previously it drew a misleading sawtooth across physically unrelated configurations). Added a `style="density"` mode that emits a Gaussian-broadened 2D heatmap via the existing `chartjs-chart-matrix` renderer — for each (d, E) cell, value = Σᵢ exp(-(E−Eᵢ)²/(2σ²)) over that d-count's eigenvalues. New `broadening_cm` (σ, default 800 cm⁻¹) and `n_energy_points` (vertical resolution, default 200) parameters control the density grid
- `_DIAGRAM_HTML` (`ui://tanabesugano/diagram.html`) now also imports `chartjs-chart-matrix` and routes to the matrix renderer when the payload carries `chart_type: "heatmap"`; default behaviour for every existing caller (line plot, no `chart_type` field) is unchanged

### Added
- All Chart.js-rendered apps (`ts_diagram_app`, `ts_overlay_app`, `ts_compare_app`, `ts_spectrum_app`, `ts_oxidation_landscape_app`, `ts_orgel_diagram_app`, `ts_spin_crossover_app`, `ts_correlation_diagram_app`, `ts_reverse_fit_app`, `ts_ratio_fit_app`, `ts_plot_view`) now expose a **Download PNG** + **Copy to clipboard** toolbar above the chart in the `ui://tanabesugano/diagram.html` iframe. PNG export uses Chart.js' built-in `toBase64Image()`; clipboard copy uses `canvas.toBlob()` + `navigator.clipboard.write([new ClipboardItem({"image/png": blob})])` — the pattern recommended in [chartjs/Chart.js#10090](https://github.com/chartjs/Chart.js/discussions/10090) and the [web.dev clipboard patterns doc](https://web.dev/patterns/clipboard/copy-images/). Filename is slugified from the chart title; clipboard copy gracefully degrades on Firefox / non-secure-context iframes with an inline "Copy denied" notice instead of throwing
- `ts_spin_crossover_app`: ground-term HS↔LS crossover map for d⁴–d⁷ — plots the lowest-energy high-spin and low-spin curves as a function of Δ and annotates the critical Dq where the ground term flips. Returns the numeric `critical_Dq_cm1` (textbook values are Dq/B ≈ 2 for d⁶, ≈ 2.1 for d⁷, ≈ 3 for d⁵, ≈ 2.7 for d⁴; this tool computes the actual crossing for the user's Racah parameters). d²/d³/d⁸ return a structured error pointing at `ts_diagram_app` / `ts_orgel_diagram_app`
- `ts_correlation_diagram_app`: three-axis correlation diagram (free ion → weak field → strong field), the classical Tsuchida-style bridge from free-ion term symbols to strong-field t₂g^x e_g^y configurations (Cotton's *Chemical Applications of Group Theory*; Figgis & Hitchman §4)
- `ts_orgel_diagram_app`: Orgel diagram (E (cm⁻¹) vs Δ (cm⁻¹), unnormalised) — the canonical companion to `ts_diagram_app` taught in every undergraduate inorganic textbook (Cotton, Figgis & Hitchman, Bertini, Lever) and explicitly referenced as the parent of the TS form ([Wikipedia](https://en.wikipedia.org/wiki/Tanabe%E2%80%93Sugano_diagram)). Reuses the existing `sweep_dq` solver path; renders as a Chart.js line plot through `ui://tanabesugano/diagram.html`
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
