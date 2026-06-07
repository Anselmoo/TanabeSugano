---
name: tanabesugano-explore
description: >-
  Routes open-ended "what is a Tanabe-Sugano diagram?" or "I want to explore d^n
  ions" conversations to the TanabeSugano MCP server's discovery entry points
  (`ts_dashboard_app` overview, `tanabesugano_why` prompt). Use when the user
  has no specific parameters yet -- before they know to ask about Dq, Racah B/C,
  or specific term symbols.
---

# tanabesugano-explore

## When to spawn

- The user says "show me what this does" or "I don't know what to enter".
- The user is new to crystal-field theory and wants a tour.
- The user asks "why use a Tanabe-Sugano diagram at all?".

## Workflow

1. **If the user asks WHY** (motivation, "what's it good for") — call the
   `tanabesugano_why` prompt and quote the rationale. Don't paraphrase from
   training data; the prompt content is the canonical source.
2. **If the user wants an overview** of every supported configuration — call
   `ts_dashboard_app`. One round-trip; per-d-count card with ground term,
   representative ions, and a sparkline of the first excited-state energy.
3. **If the user wants the energy landscape across the d-block at one Racah
   setting**, call `ts_oxidation_landscape_app` (scatter; `style="density"` for
   a Gaussian-broadened heatmap).
4. **Once parameters are settled**, hand off to `ts_diagram_app`, `ts_plot_view`,
   or `ts_plot_png` per the `tanabesugano-plot` skill.

## Do not

- Re-derive the chemistry rationale yourself when `tanabesugano_why` is on hand.
- Jump straight into `ts_diagram_app` if the user hasn't named a d-configuration
  — start with `ts_dashboard_app` so they can pick visually.

## Expected outcome

The user lands on a working diagram with minimal friction, regardless of how
much chemistry they remember.
