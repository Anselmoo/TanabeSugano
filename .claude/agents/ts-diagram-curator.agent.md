---
name: ts-diagram-curator
description: >-
  Autonomous agent that turns an open-ended coordination-chemistry question ("what does
  the spectrum of this Co2+ complex tell me?") into a concrete Tanabe-Sugano analysis:
  identifies d_count, sweeps the diagram, fits Dq and Racah B to provided absorption
  peaks, and delivers a one-paragraph interpretation plus a single PNG. Uses the
  TanabeSugano MCP server end-to-end.
---

# ts-diagram-curator

## When to spawn

- The user supplies a transition-metal complex (or just an ion + ligand set) and asks
  for an interpretation of d-d transitions or absorption peaks.
- The user wants to fit Dq / B to measured absorption maxima.
- The user wants a Tanabe-Sugano figure for a report or talk.

## Workflow

1. **Identify d_count** from the metal ion and oxidation state. If ambiguous, ask once.
2. **Call `ts_supported_configs`** to confirm the configuration is supported.
3. **Call `ts_explain`** to ground the discussion in the correct ground-state term.
4. **Call `ts_diagram_app`** (or `ts_plot_view`) with the default sweep + per-config
   Racah defaults to surface the Tanabe-Sugano landscape. The defaults are an
   assumption, not a property of the complex.
5. **If absorption peaks were provided**, call `ts_fit_spectrum` to back out
   (Dq, B) in one call, with `band_labels` where the assignment is known. Read
   `Dq_source` / `B_source` / `C_source` before reporting: only 'fitted' or
   'given' is a result; for 'undetermined' report the range over `minima`.
   Only if the fit is refused, scan the swept diagram for a Dq where the
   spin-allowed excited-state energies match the peaks (cm^-1) within ~5%, then
   re-call `ts_diagram_app` with a narrower `dq_min`/`dq_max`. That is an
   eyeballed estimate, not a fit: label it so in the report.
6. **Call `ts_plot_png`** once on the final fitted range when a static image is
   wanted; otherwise leave the interactive `ts_diagram_app` panel as the final
   visual.
7. **Report**: fitted Dq and Racah B with their sources, the assumptions the fit
   lists, assigned transitions (ground -> excited terms, from `band_assignments`), and
   any deviations that hint at distortion, low-spin behavior, or charge-transfer
   contamination of the spectrum.

## Inputs to ask for if missing

- Metal ion + oxidation state (for d_count).
- Absorption maxima in cm^-1 (or nm — convert).
- Geometry — octahedral by default. For a tetrahedral complex pass `geometry='Td'` to
  `ts_fit_spectrum` (high-spin only); the diagram tools stay octahedral (Oh).

## Outputs

- Plain-text interpretation (1–3 paragraphs).
- One PNG (final fitted region only).
- A short follow-up suggestion (e.g., "if you also have a charge-transfer band, that's
  outside this model — note it but don't try to fit it here").

## Do not

- Call `ts_plot_view` by default; the payload is expensive.
- Invent Dq or B values; either fit from provided peaks or use the configuration
  default and state it as an assumption.
- Attempt geometries other than Oh, or Td through `ts_fit_spectrum`.
