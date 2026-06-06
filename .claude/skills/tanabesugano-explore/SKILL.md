---
name: tanabesugano-explore
description: >-
  Routes open-ended "what is a Tanabe-Sugano diagram?" or "I want to explore d^n
  ions" conversations to the TanabeSugano MCP server's discovery entry points
  (`ts_explore_app` form, `ts_dashboard_app` overview, `tanabesugano_why` prompt).
  Use when the user has no specific parameters yet -- before they know to ask
  about Dq, Racah B/C, or specific term symbols.
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
   `ts_dashboard_app`. One round-trip; sparkline per d-count.
3. **If the user wants to render their own diagram but isn't sure what to set**
   — call `ts_explore_app`. The form has Sliders / Selects with safe defaults
   and dispatches to `ts_diagram_app` on submit.
4. **Once parameters are settled**, hand off to `ts_diagram_app`, `ts_plot_view`,
   or `ts_plot_png` per the `tanabesugano-plot` skill.

## Do not

- Call `ts_explore_app` after the user has already named a configuration; jump
  straight to `ts_diagram_app` or `ts_plot_view`.
- Re-derive the chemistry rationale yourself when `tanabesugano_why` is on hand.

## Expected outcome

The user lands on a working diagram with minimal friction, regardless of how
much chemistry they remember.
