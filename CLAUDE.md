# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & test

```bash
# Install. --extra mcp AND --extra plotly both matter:
#   without [mcp]    -> 8 tests error on a missing fastmcp
#   without [plotly] -> the artifact drift check silently skips its .html half
uv sync --all-groups --extra mcp --extra plotly

uv run poe check          # lint + format + types + tests + artifact drift (what CI runs)

uv run poe lint           # ruff over src/ AND scripts/, full ALL ruleset
uv run poe format         # ruff format --check
uv run poe types          # ty, in the project env (see below)
uv run poe test           # suite, no coverage, screenshot tests excluded
uv run poe test-mcp       # MCP-only tests
uv run poe cov            # suite with a coverage report
uv build                  # wheel + sdist via the uv_build backend
```

**Every committed artifact has a script, and every script has a poe task.**
These trees went stale for years because regenerating them was folklore rather
than a command:

```bash
uv run poe regen-all              # every committed artifact
uv run poe regen-diagrams         # ts-diagrams CSVs, .html diagrams, manifest.json
uv run poe regen-diagrams-check   # fail on drift -- this is the CI gate
uv run poe regen-examples         # examples/ tables + the two README figures
uv run poe regen-uvvis            # assets/uvvis reference figures
```

Two things that bite:

- **Run `ty` through `poe types`, not `uvx ty`.** In an isolated environment ty
  cannot resolve numpy/scipy stubs and silently checks *less* — that is how a
  real `eigensolver` return-type mismatch went unseen while `uvx ty` reported
  "1 diagnostic". `ty` is a declared dev dependency for exactly this reason.
- **`pytest` no longer forces coverage.** `addopts` used to carry
  `--cov=src/tanabesugano`, so every ad-hoc run paid for it and had to be
  undone with `--no-cov`. Ask for it explicitly with `poe cov`.

CI mirrors this on Python 3.12, 3.13, and 3.14.

## Architecture

Two product surfaces share a single solver core:

1. **`tanabesugano` CLI** (`src/tanabesugano/cmd.py` → `cmd_line()`) — argparse pipeline that computes a Tanabe-Sugano (or DD-energy) diagram for a chosen d-configuration and renders it via matplotlib.
2. **`tanabesugano-mcp` MCP server** (`src/tanabesugano/mcp/server.py`) — optional FastMCP 3 server exposing the same solvers as MCP tools, resources, and prompts. Installed via the `[mcp]` extra; never required at runtime for the CLI.

Solver core (do not duplicate logic in the MCP layer):

- `src/tanabesugano/matrices.py` — `LigandFieldTheory` base and `d2 … d8` subclasses, each with a `.solver()` returning a **`LevelSet`** (see below). It is *not* a Mapping: `states[key]`, `.items()` and `len()` all raise `TypeError`. Call `.as_dict()` for the old `dict[TermKey, Float64Array]` shape.
- `src/tanabesugano/terms.py` — `TermKey` / `Irrep` / `FreeIonTerm` closed enums. `TermKey` is a `StrEnum`, so it *is* a `str` at every boundary.
- `src/tanabesugano/levels.py` — `Level` / `LevelSet`: the typed view of a term manifold. A `dict[TermKey, ndarray]` cannot express a multiplet, so anything that **names** a level or a transition must go through `LevelSet`, never through the raw dict. `LevelSet.solve()` derives free-ion parentage; `LevelSet.from_states()` wraps an already-computed dict without paying for that.
- `src/tanabesugano/batch.py` — `ELECTRON_CONFIG_SOLVERS` dispatch + `Batch` class for sweeps.
- `src/tanabesugano/free_ion.py` — Racah's free-ion term energies for d2–d8 and the L → Oh reduction. These are an **absolute oracle** for the solver, asserted in `test_matrices_invariants.py`, which is the only place that asserts against them. Never copy an expression out of here: the same closed form pinned in two places at two tolerances lets the looser mask the tighter.
- `src/tanabesugano/script_export.py` — emits a standalone matplotlib script for an observed-vs-computed fit, plus `labelled_bands()`, the single place a band is paired with a computed line. Both figure surfaces (`ts_fit_script`, `ts_fit_plot_app`) read it, so they cannot disagree about an assignment.
- `src/tanabesugano/tools.py` — Slater-Condon ↔ Racah parameter transforms.
- `src/tanabesugano/constants.py` — `ElectronConfiguration` enum + numerical tolerances.

Naming rule: `Level.label` (`3_T_1(b)`) is a **display** string — the `(a)/(b)`
ordinal is suppressed for terms holding a single level, matching how the
literature writes them. Identity is `(term, index)`; its string form is
`Level.uid` (`3_T_1#1`). Never key on `label`.

Two label vocabularies, and the choice is not cosmetic. `label` / `latex` /
`unicode` carry the **positional** ordinal `(a)/(b)`; `parent_label_display` /
`parent_latex` / `parent_unicode` carry **free-ion parentage** `(F)/(P)`. Use
the parentage form for anything a reader compares against the literature — a
figure axis, a caption, a chart label — because `(a)/(b)` is this package's
internal spelling and appears in no textbook. Parentage is `None` where it is
genuinely undecidable (d3/d7 place ²H and ²P at the same 9B+3C for every B and
C, so three ²T₁ levels cannot be told apart by energy); `parent_candidates`
lists what it could be and the display falls back to the ordinal. Nothing
guesses.

Rendering: matplotlib gets `parent_latex` (mathtext), Chart.js gets
`parent_unicode` — Chart.js renders no mathtext and will print `$^{3}A_{2g}…$`
verbatim if handed LaTeX.

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

## Testing

Defend a claim at the strongest tier that can express it. **T1a absolute oracles** (`min(levels) == 0`,
`nu1 == 10Dq` for d3/d8, `E(3P) - E(3F) == 15B` at Dq = 0, `math.comb(10, n)` term counts) >
**T1b relative invariants** (hole conjugation `d^n(+Dq) == d^(10-n)(-Dq)`, level counts, sortedness) >
**T2 synthetic round-trips** (recover the parameters the forward model was given, from a *displaced*
seed) > **T3 literature fixtures** (real complexes, tolerance-justified). A structural/contract test
may never be the only test of a numeric change. Long form, not in-repo: `~/.claude/plans/tdd-strategy.md`.

Three rules, each earned the hard way:

1. **Provenance.** Before asserting an expected value, state where it came from and whether that
   source touches the code under test. This project hit the same tautology four times: a bound
   bracketing the optimizer's own `(5000, 600)` seed; round-trips that pass because
   `closed_form_dq_b` *is* the seed; tolerances measured off the implementation and then enshrined;
   level counts that pin a regression but could never detect a manifold wrong from the start.
   `math.comb(10, n)` is the model — an oracle the code cannot influence.
2. **Valid red.** A fix does not land until its test has been *observed to fail for the right reason*;
   record the observed failure text in the test docstring. Not ceremony — it caught that
   `ToolResult(content=app)` serialises a `PrefabApp` via `model_dump()`, dropping the entire child
   tree and emitting an empty card. Inspection alone showed nothing wrong.
3. **One claim, one place, one tolerance.** The same fixture asserted in two modules at two
   tolerances means the looser one masks what the tighter one catches (already fixed once, for the
   Cr(III) fixtures). The module boundary is in the `test_ion_case_studies.py` docstring; keep it.

Literature fixtures are admissible only as `IonFixture` records in `test_ion_case_studies.py`:
`published_quantity` (Dq vs 10Dq vs Delta_o), `estimator` (closed-form and least-squares disagree
legitimately), `degrees_of_freedom`, `expected_outcome` (fit / raises / warns), `source_tier` and a
mandatory `tolerance_reason` are all validated at construction. **R1 — never validate a d5 or d6
fixture against a published TS *diagram*:** the published d5/d6 diagrams carry a propagated error
(Hormann & Shaw, *J. Chem. Educ.* **1987**, 64, 918), so such a test validates the error.

## MCP design notes (when adding tools)

- `ts_plot_png` takes a `format` of `png` (inline image), `pdf` or `svg` (vector, returned as an embedded blob resource). Vector MIME types are spelled out in `plotting.EXPORT_MIME_TYPES`; do **not** switch to FastMCP's `File(format=...)`, which maps a bare extension to `application/<ext>` and so emits the unregistered `application/svg`.
- Type errors: fix the annotation, do not silence the checker. `# type: ignore[code]` is mypy's spelling and **ty does not read it** — three such comments added during one session were all dead. ty honours bare `# type: ignore` or `# ty: ignore[code]`. Usually the real fix is a `Literal` (e.g. `SpinState` rather than `str`), which also gives agents an `enum` in the tool's JSON schema.
- Default visualizations use matplotlib PNG (`ts_plot_png`) to keep token cost low. Interactive views (`ts_plot_view` via `apps.prefab.LinePlot`) are opt-in and only registered when the extra is installed.
- Tool names use the `ts_` prefix. Each tool returns a typed Pydantic model from `mcp/models.py` (or `ComputeError` on validation failure). Avoid raising — return the error model so agents can recover.
- Add new tools through `register_tools(mcp)` in `mcp/tools.py`; do not register at import time.
- Per-configuration Racah defaults live in `mcp/_defaults.py`. Keep them in sync with `matrices.d{N}.__init__` signatures.

## Skills & agents (this repository)

- `.claude/skills/tanabesugano-compute/SKILL.md` — when and how to call the compute/diagram tools.
- `.claude/skills/tanabesugano-plot/SKILL.md` — choose between PNG (default) and Prefab line plot.
- `.claude/agents/ts-diagram-curator.agent.md` — autonomous agent for end-to-end spectrum interpretation.

## Release bundle (.mcpb)

Two paths produce the bundle, and they are not interchangeable:

- **CI / releases** — the `mcpb` job in `.github/workflows/cicd.yml` runs the pinned
  `mcp2mcpb==1.0.0` CLI directly (not the composite action, whose input mapping treats
  `--from-dist` and `--pin` as mutually exclusive; a release bundle needs both). It builds
  offline from the freshly-built wheel and emits a version-pinned runtime reference.
  `scripts/validate_mcpb.py` then asserts the launch recipe before the release is created,
  and a post-release `mcpb-smoke` job runs `mcp2mcpb sandbox` against the real bundle.
- **Local dev** — `poe build-mcpb-dev` runs `scripts/build_mcpb.py`, which points the
  manifest at the local source tree. Use this to iterate without publishing.

When changing either path, the launch recipe must end in `tanabesugano-mcp` and request
`tanabesugano[mcp]==<version>`. Launching the `tanabesugano` CLI instead makes the bundle
hang on stdin and never answer the MCP `initialize` handshake.
