---
name: tanabesugano-plot
description: >-
  Helps agents choose between matplotlib PNG output (cheap, default) and the interactive
  Prefab LinePlot view when visualizing Tanabe-Sugano diagrams via the TanabeSugano MCP
  server. Use when the user asks for a plot, graph, or visualization of d-d transitions.
---

# tanabesugano-plot

## When to pick which plot tool

| Tool | Pick when |
|---|---|
| `ts_plot_png` | Default. Static PNG, low token cost, works in every client. Use unless the user explicitly wants interactivity. |
| `ts_plot_view` | The user wants to hover/zoom or compare specific term curves; client is Claude Desktop or another `apps/prefab`-capable MCP host. Heavy payload — never the default. |

## Parameters worth tuning

- `normalize=True` (default) renders the classical Tanabe-Sugano diagram (`E/B` vs `10Dq/B`).
- `normalize=False` renders the energy-correlation diagram (cm^-1 axes).
- `steps`: 50 is fine for a clean curve; drop to 20 for a sanity-check plot.
- `dq_min`/`dq_max`: bracket the region of interest (e.g., spin-crossover near `2Dq/B~2`
  for d4-d7) before plotting at the default 0..1500 cm^-1 sweep.

## Do not use for

- Polar / Argand / phase plots — not provided.
- 3D rendering — out of scope.

## Expected outcome

A single clear plot is returned, and the agent annotates the relevant features in text
rather than uploading multiple variants.
