---
name: tanabesugano-compute
description: >-
  Guides agents using the TanabeSugano MCP server to compute eigenvalues, Tanabe-Sugano
  diagrams, and term-symbol energies for d2-d8 transition-metal complexes. Use when the
  user asks about ligand-field splitting, octahedral d-d transitions, Racah parameters
  (B, C), or absorption spectra interpretation. DO NOT USE for unrelated quantum
  chemistry or for crystal structure analysis.
---

# tanabesugano-compute

## User problem statement

I need eigenvalues or a full Tanabe-Sugano diagram for a d^n octahedral complex, and I
want the AI to drive the computation instead of asking me to run a Python script.

## Available MCP tools

| Tool | Use it when |
|---|---|
| `ts_supported_configs` | First call. Confirms d_count is supported and surfaces default Racah B, C. |
| `ts_explain` | Get a one-paragraph orientation on a configuration (ground term, typical spectrum). |
| `ts_terms_table_data` | Need eigenvalues for a single (Dq, B, C) point as sorted machine-readable rows (replaces the removed `ts_compute`). |
| `ts_compute_app` | Same data as `ts_terms_table_data` but as an in-chat sortable DataTable for the user. |
| `ts_fit_spectrum` | Back out Dq and Racah B from observed UV-Vis absorption peaks. |
| `ts_diagram_app` | Need a swept Tanabe-Sugano diagram as an in-chat Chart.js plot. |
| `ts_plot_png` | Need a static visual. Returns a matplotlib PNG. Default visualisation — low token cost. |
| `ts_plot_view` | Same data as `ts_diagram_app` but plain Chart.js without the title/metric header — slightly cheaper payload. |

## Workflow

1. Call `ts_supported_configs` if d_count is uncertain.
2. Call `ts_explain` to ground the discussion in the correct ground term.
3. For a fit-to-spectrum task: feed measured peaks to `ts_fit_spectrum` to get
   `(Dq, B)` directly; if a coarse sweep is needed instead, use `ts_diagram_app`
   (or `ts_plot_view`) at default Racah B/C and read off the candidate region.
4. Render the final fitted region with `ts_plot_png` for static delivery, or
   `ts_diagram_app` for an interactive in-chat panel.

## Tips

- All energies are in cm^-1 unless explicitly normalized (`normalize=True` divides by B).
- Use `ts_explain` once per session rather than calling repeatedly — the description is
  static per d_count.
- If the tool returns a `ComputeError`, surface the `error` string verbatim to the user
  rather than retrying with random parameters.

## Do not use for

- Non-octahedral geometries (tetrahedral, square-planar) — not modeled.
- Spin-orbit coupling or zero-field splitting — not in the Hamiltonian.
- Arbitrary multireference quantum chemistry — out of scope.

## Expected outcome

The agent answers a coordination-chemistry question with concrete numerical results
and (when helpful) a single PNG, without asking the user to run any script.
