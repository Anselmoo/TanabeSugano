# Closure record: hand-driven MCP defect report

A session driving the `tanabesugano` MCP server by hand against
`2.0.0-alpha.1` produced a report of eleven defects. This records what happened
to each against `2.0.0-beta.1`, including the rows that were **not** defects
here, so the same report is not re-litigated from scratch.

The report's own policy asked for exactly this: rows must not be closed
silently, and a partial resolution must say so.

## Fixed

| Reported | Where | Commit |
| --- | --- | --- |
| Density heatmap renders its energy axis inverted | `mcp/apps.py` | `ef653aa` |
| Ground term derived from the Dq = 0 sample point | `mcp/apps.py` | `c86852c` |
| Dashboard sparkline spikes at the origin | `mcp/apps.py` | `c86852c` |
| No flag distinguishes a fitted C from a passthrough default | `mcp/_compute.py`, `mcp/models.py` | `51d024d` |
| `dq_max` units ambiguous against Δ = 10·Dq | `mcp/apps.py` | `51d024d` |
| Ground-manifold exclusion undocumented | `mcp/apps.py` | `51d024d` |
| No axis-limit parameters for comparing two ions | `mcp/plotting.py`, `mcp/apps.py`, `mcp/tools/plot_tools.py` | `51d024d` |
| No selection-rule weighting on the landscape | `mcp/apps.py` | `aaa1edc` |

Guarded by `src/tanabesugano/test/test_mcp_regressions.py`.

## Not defects against this tree

Each was real when reported and had already been fixed, or was never in this
package. Recorded because the report is otherwise unfalsifiable — a future
reader has no way to tell a stale row from an unfixed one.

**Static ground-term table wrong for d4 and d6.** The named symbol,
`GROUND_TERM_OCTAHEDRAL`, does not exist. It was deleted as dead code, and its
successor `HIGH_SPIN_GROUND_TERM` already carries d4 = `5_E` and d6 = `5_T_2`,
which are the values the report asked for. It is additionally labelled in
source as a test oracle rather than production data, and production derives the
ground term per point through `reference_ground_term`.

**`n_energy_points` default undocumented.** It is documented, with its default.

**PDF and SVG export rejected.** Not this package. `ts_plot_png` returns `png`
as `ImageContent` (`image/png`) and `pdf`/`svg` as `EmbeddedResource`
(`application/pdf`, `image/svg+xml`), each with correct magic bytes —
verified through the tool. Returning vector output as a *resource* rather than
an *image* block is precisely the remedy the report proposed; it was already
implemented. Any remaining failure is in the consuming client's handling of
`EmbeddedResource` and has to be raised there. `test_plot_export_formats.py`
pins the package side against file-format magic numbers and the IANA registry.
The local matplotlib fallback the report resorted to was therefore never
necessary here.

## Corrected in the report

**The Dq = 0 tie-break named the wrong configurations.** The report listed d3,
d6 and d8. Measured against this tree it misnamed **d2, d6 and d7**; d3 and d8
resolved correctly. The underlying cause was real and is fixed, but the
evidence cited for it was not reproducible as written.

**Severity of the Dq = 0 picker.** Reported as a wrong reported fact. Its only
output, `ground_y`, was discarded at all six call sites, so nothing it produced
ever reached a user. Latent rather than user-visible — which is precisely why
it survived an earlier pass that corrected three sibling call sites. It was
deleted rather than corrected.

## Unresolved

**The d8 fitter anchoring to a singlet ground term.** The report cites a prior
session's memory of a confirmed bug and asks for the original fixture to be
re-run, on the correct principle that two clean fits do not retire a documented
defect.

The original fixture could not be located; this project's memory store is
empty, so the memory the report refers to is not available here. What can be
said:

- It does not reproduce on seven cases — four real Ni(II) complexes, a
  single-band fit, a two-band fit, and the spin-forbidden path. All return
  `3_A_2`.
- It is structurally prevented. `fit_spectrum` pins itself to
  `reference_ground_term`, which probes a field strong enough to have lifted
  the zero-field degeneracy, and
  `test_spectrum_fitting.py::TestSyntheticRoundTrip::test_round_trip` already
  asserts `fit.ground_term == HIGH_SPIN_GROUND_TERM[d_count]` for d8 among
  others. A singlet anchor would fail a standing test.

Absent the fixture this is "cannot reproduce, and a standing guard would catch
it", not "was never real". If the fixture resurfaces, run it before assuming
the row is closed.
