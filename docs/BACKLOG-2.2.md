# Backlog for 2.2

Work deliberately left out of 2.1.0. Every entry says what is open and, in one line, why
it was deferred rather than done. None of these entries describes a wrong result that 2.1.0
reports as correct; those were fixed or are listed under "Known limitations" in
`CHANGELOG.md`.

## Optional spin-orbit solver with double-group labels

Diagonalise the d^n Hamiltonian with spin-orbit coupling and label the levels by the
double-group irreps (Γ6, Γ7, Γ8 in O').

Deferred because the physics is small (a prototype reproduces three limiting cases) but the
labels, every renderer and the MCP schema would all have to change for it.

## Optional ΔS = ±2 transitions (hypothesis, to be checked against the literature first)

Let a caller include ΔS = ±2 levels for spectroscopies that may show them, such as 2p3d RIXS
and MCD. 2.1.0 fits only ΔS = 0, ±1.

Deferred because whether these lines are observable at useful intensity has not yet been
checked against the literature. Doing it properly also needs the spin-orbit solver and
intensities.

## Optional intensity / ε input

Accept a band intensity or molar absorptivity beside each position, so weak spin-forbidden
lines can be told apart from spin-allowed ones.

Deferred because it is a feature, not a fix. 2.1.0 states the spin-allowed assumption
instead of guessing.

## (Dq/B, C/B) phase and identifiability maps

Map, over Dq/B and C/B, where a band set determines (Dq, B, C) and where it does not.

Deferred because 2.1.0 already reports identifiability per fit (provenance, minima,
ranges). A map is an analysis tool built on top of that report.

## Tie-branch refinement

Refine the held-C tie branch, which reports an alternative free-C minimum that fits at least
as well.

Deferred because the noise in this branch was already cut from 52 cases to 0. What is left is
genuine non-identifiability, not error.

## Per-source discrimination rule in the audit

Define how the audit pools or separates bands that come from different sources for the
same system.

Deferred because it is audit methodology and changes no fit result.

## Extended F1b optimiser test

Extend the optimiser test beyond the cases pinned in 2.1.0.

Deferred as software hygiene: no reported number depends on it.

## Remaining JCE classification

Classify the remaining JCE 2023 reference rows (observed, graphical, derived).

Deferred as software hygiene: an unclassified row is already graded comparison-only.

## Unread sources

Read and check Jørgensen 1955 (refs 26 and 37), Riordan 2005, Pontnau & Adde, and
Sugano, Tanabe & Kamimura against the tabulated values.

Deferred because these are needed only if those systems enter a later study.

## Re-grade the textbook fixtures from primary sources

[Cr(H2O)6]3+, [Ni(NH3)6]2+, [Cr(NH3)6]3+, MgO:Cr3+ and [Ni(H2O)6]2+ are literature
fixtures whose source is not verified ([Ni(H2O)6]2+ also takes its bands and its parameters
from different sources). In 2.1.0 they are comparison-only: each reports its distance
from the printed values and grades neither Dq nor B. Re-grade them against Tanabe &
Sugano 1954, which `audit/jce2023/SOURCE-CHECK.md` verifies, or against another primary
source.

Deferred because each needs its original read and its bands checked. Until then, an
unverified value has no tolerance it could be graded at.

## Re-derive the 2.0.0 fixture tolerances

The literature fixtures from 2.0.0 carry bounds whose `tolerance_reason` records a value
measured from the implementation. For example, [Cr(H2O)6]3+ has an RMSE bound of 300
cm⁻¹ against a measured 215.5. Re-derive each bound from the source's stated uncertainty
before measuring, as the 2.1.0 JCE fixtures do (`COVERAGE` × σ).

Deferred because the four fixtures most affected are comparison-only in 2.1.0, and the
remaining bounds pin a regression rather than a published claim.

## Jahn–Teller and charge-transfer validity note

State in the tool output where a ligand-field fit is outside its model: a Jahn–Teller
distorted ion (high-spin d4, low-spin d7), and bands that are charge transfer
rather than d–d.

Deferred because it is advisory text with no effect on a computed value, and the cases
need a rule that does not guess from band positions alone.

## Tool-text polish

Items from the MCP tool-text review:

- `ts_compare_app` and `ts_overlay_app` cannot be told apart from their descriptions:
  merge them or separate them.
- The plot tool descriptions contradict each other (Prefab vs Chart.js, "no table").
- Placeholder defaults: Dq = 900; B = 900 / C = 4000; "see _defaults.py"; "critical Delta
  for this complex".
- `str` where a `Literal` fits: `energy_unit` in seven apps, `format`, `style`, and
  `d_count: int` in twelve apps.
- Wasted tokens and malformed docstrings: the crop paragraph repeated four times, the
  sandbox text repeated four times, and a duplicated `broadening_cm` in the `Args:` of
  `ts_oxidation_landscape_app`.

Deferred because each change is a schema or description edit with no effect on a computed
value, and they are best done together in one pass.

## Unified error contract

Apps and `ts_fit_script` return `ToolResult(is_error=True)`, `ts_fit_spectrum` returns
`ComputeError`, and `ts_emit_png` returns plain text. Settle on one contract.

Deferred because it changes the result type of several tools, which is a breaking change for
clients.

## Plan E minors (M1–M8)

- **M1.** A wavelength list that reaches past 3000 nm is still fitted as cm⁻¹, for example
  `fit_spectrum(3, [3030, 1700, 650])`. This is rare (a Td Co(II) ν1 given in nm).
- **M2.** When cm⁻¹ values are sent with `energy_unit="nm"`, the diagnosis gives the right
  numbers but never names `energy_unit`.
- **M3.** The inverse JCE test is a floor test (B is graded on 2 of 7 records). Its
  docstring should say so.
- **M4.** Missing JCE CSVs broke test collection. Resolved in 2.1.0: the module skips when
  `audit/jce2023` is absent.
- **M5.** The xfail meta-test covers only `JCE_FINDINGS`, which is empty today, so an
  `xfail` added directly to the module bypasses it.
- **M6.** The `fit_c` description still reads wrongly after the `Args:` split.
- **M7.** `test_no_second_ev_constant` only searches for `8065` under `mcp/`. A reciprocal
  literal, or a copy elsewhere in the package, passes.
- **M8.** `RATIO_ROUNDING` is an absolute 0.0005 used as a relative tolerance. The effect is
  negligible.

Deferred because each is small, none changes a reported number, and no paper claim rests on
any of them.

## Final-review minors

Copied from the deferred-minor lines of the 2.1.0 plan reviews. Entries already resolved on
the release branch are marked as such.

- `extract_jce2023.py`: a lambda without a docstring. The CSVs carry no `source_doi`
  column. A `pyproject` poe comment says ~50 s where ~80 s is measured.
- Test-file constant comment blocks should become docstrings.
- Free C is measured only at C/B 4.0 and 4.8.
- Mutation testing is not configured.
- The `ts_oxidation_landscape_app` reach warning fires only for an explicit
  `dq_max_search`. It is silent when the default cap misses the fitted Dq.
- `fit_objective` recomputes the reference ground term at each node, while the fit pins it
  once. The keys are the same today, and the docstring's "cannot rank differently" is
  slightly too strong. Measured times: the reverse app takes 1.2 s for d6 low-spin and 2.1 s
  for labelled d5.
- Some behaviour changes are not in docstrings: reverse-app residuals are now in caller
  order, grid-candidate RMS is now the injective objective at the fit's C, and calls that
  are spin-forbidden or low-spin without the matching flag now return an error instead of a
  wrong number.
- Missing tests:
  - no schema-rejection test for a malformed label;
  - no app test that combines shuffled peaks, labels and a dropped non-positive peak;
  - some ratio red texts do not record their commit;
  - `TestComparisonOnly.test_every_declared_id_exists_or_is_jce` and
    `test_comparison_only_reports_delta` record no observed red.
- The `Dq_nu1_reason` description omits that ν1 is assumed to be the lowest band.
- Dead mypy-style `# type: ignore[attr-defined]` comments in `test_mcp.py`, which ty does
  not read.
- Twenty-two multi-line comment blocks and eight section banners added on the branch,
  for example `test_fit_recovery.py`, `test_ion_case_studies.py`, `test_mcp.py`,
  `audit_fit_paths.py` and `_compute.py`.
- `audit-fit-check` is not in CI.
- Resolved in 2.1.0:
  - the MCP tool now exposes `fit_c`, band labels, minima and provenance;
  - the Mn(II) fixture carries label and spin-forbidden fields;
  - the four dead `# type: ignore[valid-type]` comments are gone;
  - the `FitMinimum.source` description is correct when C is fitted;
  - `ts_fit_plot_app`'s assumptions are pinned by `test_fit_tool_contract.py`.

Deferred because none of these changes a reported number. They are hygiene for the next
cycle.
