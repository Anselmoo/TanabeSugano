"""Emit a standalone matplotlib script for an observed-vs-computed fit figure.

Why source rather than an image
-------------------------------
There was no observed-vs-computed renderer in this package, so every such
figure -- including the one in the manuscript -- was bespoke matplotlib written
by hand or by a model. That is a second implementation of the assignment logic
with no oracle behind it: it can disagree with the fitter and nothing catches
the disagreement.

Emitting source fixes that three ways at once. The numbers are the fitter's
own, baked in as literals, so the figure cannot re-derive them differently. The
result is text, so it diffs, versions and reviews like code. And text is the
one thing the MCP Apps sandbox cannot block: it strips ``allow-downloads`` from
every UI iframe (see ``ts_emit_png``), so an inline chart can never hand a user
a file, but a script can travel through the conversation and be pasted.

The generated script imports matplotlib and nothing else. It deliberately does
NOT import ``tanabesugano``: a reviewer reproducing a published figure should
not need this package, or this version of it, installed. The cost is that the
script is frozen at its inputs -- change the peaks and you regenerate it, you
do not re-run it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tanabesugano import __version__
from tanabesugano.levels import LevelSet
from tanabesugano.mcp._compute import SpinState
from tanabesugano.mcp._compute import fit_spectrum


if TYPE_CHECKING:
    from collections.abc import Sequence

    from tanabesugano.mcp._compute import SpectrumFit


_ENERGY_MATCH_TOL_CM1: float = 1e-6
"""How close a fit transition must be to a solved level to be the same level.

Both sides come from the same solver at the same (Dq, B, C), so they agree to
floating-point noise. This is a float-equality tolerance, not a physical width:
loosening it would let a neighbouring level steal the label.
"""


def _labelled_transitions(fit: SpectrumFit, d_count: int) -> list[tuple[float, str, str]]:
    """Pair each spin-allowed transition with free-ion-parentage labels.

    Returns ``(energy, latex, unicode)``. Both spellings, because the two
    surfaces need different ones and neither should re-derive the other:
    matplotlib renders mathtext, Chart.js renders none.

    ``SpectrumFit.transitions`` carries positional labels (``3_A_2->3_T_1(a)``)
    because the fitting objective builds its manifold with
    :meth:`LevelSet.from_states`, which skips the extra zero-field solve that
    parentage needs -- correct there, since that runs thousands of times per
    fit. Export runs once, so it can afford :meth:`LevelSet.solve` and print
    what the literature prints.
    """
    manifold = LevelSet.solve(d_count, dq=fit.Dq, b=fit.B, c=fit.C)
    by_energy = sorted(manifold.levels, key=lambda lv: lv.energy_cm1)
    ground = by_energy[0]

    labelled: list[tuple[float, str, str]] = []
    for energy, _assignment, is_allowed in fit.transitions:
        if not is_allowed:
            continue
        level = min(by_energy, key=lambda lv: abs(lv.energy_cm1 - energy))
        if abs(level.energy_cm1 - energy) > _ENERGY_MATCH_TOL_CM1:
            # Never guess a label: an unmatched transition keeps the fitter's
            # own string rather than borrowing a neighbouring level's name.
            labelled.append((float(energy), _assignment, _assignment))
            continue
        # The `{}` before the second superscript is required, not cosmetic:
        # `A \rightarrow ^{3}T` is a superscript with no base, which both
        # mathtext and LaTeX reject.
        arrow = (
            rf"{ground.parent_latex.strip('$')} \rightarrow "
            rf"{{}}{level.parent_latex.strip('$')}"
        )
        labelled.append(
            (
                float(energy),
                f"${arrow}$",
                f"{ground.parent_unicode} \u2192 {level.parent_unicode}",
            ),
        )
    return labelled


def labelled_bands(
    fit: SpectrumFit,
    d_count: int,
    observed_peaks_cm1: Sequence[float],
    *,
    _labelled: list[tuple[float, str, str]] | None = None,
) -> list[dict]:
    """One record per observed band: measured, computed, residual, assignment.

    The single place either figure surface gets its band records --
    :func:`fit_figure_script` for the matplotlib script and
    ``ts_fit_plot_app`` for the inline chart. Two surfaces each pairing bands
    their own way is precisely the "second implementation with no oracle"
    problem this module exists to remove: they could silently disagree about
    which computed line a band was assigned to.

    Each observed band takes the nearest computed line, which is the rule the
    fitting objective itself minimises, so the reported pairing is the pairing
    that was actually fitted. Residuals are computed minus observed, stated
    once here so both surfaces sign them the same way.
    """
    labelled = _labelled if _labelled is not None else _labelled_transitions(fit, d_count)
    records: list[dict] = []
    for peak in (float(p) for p in observed_peaks_cm1):
        energy, latex, unicode_label = min(labelled, key=lambda t: abs(t[0] - peak))
        records.append(
            {
                "observed_cm1": peak,
                "computed_cm1": energy,
                "residual_cm1": energy - peak,
                "assignment": latex,
                "assignment_unicode": unicode_label,
            },
        )
    return records


def fit_figure_script(
    d_count: int,
    observed_peaks_cm1: Sequence[float],
    *,
    C: float | None = None,
    spin_state: SpinState = "high",
    include_spin_forbidden: bool = False,
    title: str | None = None,
) -> str:
    """Return runnable Python that draws the observed-vs-computed figure.

    Raises ``ValueError`` -- propagated from :func:`fit_spectrum` -- when the
    problem is ill-posed, rather than emitting a script that would plot nothing.
    High-spin d5 is the standing example: all its d-d bands are spin-forbidden,
    so there is no spin-allowed comparison to draw.
    """
    fit = fit_spectrum(
        d_count,
        [float(p) for p in observed_peaks_cm1],
        C,
        spin_state=spin_state,
        include_spin_forbidden=include_spin_forbidden,
    )
    labelled = _labelled_transitions(fit, d_count)
    observed = [float(p) for p in observed_peaks_cm1]
    bands = labelled_bands(fit, d_count, observed, _labelled=labelled)
    pairs = [
        (b["observed_cm1"], b["computed_cm1"], b["assignment"], b["residual_cm1"]) for b in bands
    ]

    heading = title or f"d{d_count} fit: Dq = {fit.Dq:,.1f}, B = {fit.B:,.1f} cm$^{{-1}}$"
    warnings = "\n".join(f"#   ! {w}" for w in fit.warnings) or "#   (none)"

    from tanabesugano import plot_style  # deferred: pulls matplotlib

    # Read from plot_style rather than spelled here: the emitted script is a
    # fourth figure surface, and a fourth private copy of the palette is exactly
    # what this work removed from the other three.
    observed_color = plot_style.ANNOTATION_COLORS["observed"]
    computed_color = plot_style.ANNOTATION_COLORS["computed"]
    observed_src = ", ".join(f"{p:.4f}" for p in observed)
    computed_src = ", ".join(f"{energy:.4f}" for _, energy, _, _ in pairs)
    residual_src = ", ".join(f"{residual:.4f}" for *_, residual in pairs)
    label_src = "\n".join(f"    {label!r}," for _, _, label, _ in pairs)
    extra_src = "\n".join(
        f"    ({e:.4f}, {lbl!r}),"
        for e, lbl, _unicode in labelled
        if all(abs(e - p[1]) > _ENERGY_MATCH_TOL_CM1 for p in pairs)
    )

    return f'''"""Observed vs computed d-d bands for d{d_count}.

GENERATED by tanabesugano {__version__} -- tanabesugano.script_export.
Every number below is the fitter's own output, carried through as a literal.
Nothing here recomputes the ligand-field problem, so this figure cannot
disagree with the fit it came from.

Fit provenance
  estimator      least-squares over all supplied bands
  spin regime    {fit.spin_state} (the fit was pinned to this side of any crossover)
  ground term    {fit.ground_term}
  Dq             {fit.Dq:.4f} cm^-1
  Racah B        {fit.B:.4f} cm^-1
  Racah C        {fit.C:.4f} cm^-1
  RMS residual   {fit.rmse_cm1:.4f} cm^-1
  warnings
{warnings}

Note the closed-form estimator answers a different question and will give
different numbers: Dq = nu1 / 10 reproduces the first band exactly and pushes
all misfit into the rest. Neither is more correct; say which one a caption
quotes.

Requires matplotlib only. Run:  python this_file.py
"""

import matplotlib.pyplot as plt

OUTPUT = "tanabesugano_fit.png"

OBSERVED_CM1 = [{observed_src}]
COMPUTED_CM1 = [{computed_src}]
RESIDUALS_CM1 = [{residual_src}]
ASSIGNMENTS = [
{label_src}
]

# Spin-allowed transitions the fit found but no observed band was matched to.
UNMATCHED = [
{extra_src}
]

OBSERVED_COLOR = "{observed_color}"   # Okabe-Ito, colour-blind safe
COMPUTED_COLOR = "{computed_color}"


def main() -> None:
    # Two panels, because one cannot honestly show both. On the band axis a
    # 165 cm^-1 residual spans well under a marker width, so a single panel
    # either hides the misfit or lies about the scale. The right panel gives
    # the residuals their own axis; the shared y ties the rows together.
    n = len(OBSERVED_CM1)
    # constrained layout, not tight_layout: the latter warns and mis-measures
    # when the two panels share a y-axis through a width_ratios gridspec.
    fig, (ax, axr) = plt.subplots(
        1, 2, figsize=(8.4, 0.78 * n + 1.75), sharey=True,
        gridspec_kw={{"width_ratios": [3.2, 1.0]}},
        layout="constrained",
    )

    for energy, _label in UNMATCHED:
        ax.axvline(energy, color="0.88", lw=1.0, zorder=0)

    rows = list(range(n - 1, -1, -1))
    for y, obs, calc, resid, label in zip(
        rows, OBSERVED_CM1, COMPUTED_CM1, RESIDUALS_CM1, ASSIGNMENTS
    ):
        ax.plot([obs, calc], [y, y], color="0.55", lw=1.2, ls="-", zorder=1)
        ax.plot(obs, y, "o", color=OBSERVED_COLOR, ms=9, zorder=3,
                label="observed" if y == rows[0] else None)
        ax.plot(calc, y, "s", color=COMPUTED_COLOR, ms=7.5, zorder=4,
                label="computed" if y == rows[0] else None)
        ax.annotate(label, xy=((obs + calc) / 2, y), xytext=(0, 11),
                    textcoords="offset points", ha="center", fontsize=10.5)

        axr.barh(y, resid, height=0.30, color=COMPUTED_COLOR, alpha=0.85, zorder=2)
        axr.annotate(f"{{resid:+.0f}}", xy=(resid, y),
                     xytext=(6 if resid >= 0 else -6, 0),
                     textcoords="offset points", va="center",
                     ha="left" if resid >= 0 else "right",
                     fontsize=9, color="0.25")

    ax.set_xlabel(r"$\\tilde{{\\nu}}$ (cm$^{{-1}}$)")
    ax.set_yticks([])
    ax.set_ylim(-0.75, n - 0.15)
    ax.margins(x=0.10)
    ax.legend(loc="lower left", frameon=False, fontsize=9.5, ncol=2)
    ax.spines[["left", "right", "top"]].set_visible(False)

    axr.axvline(0.0, color="0.35", lw=1.0, zorder=1)
    axr.set_xlabel(r"residual (cm$^{{-1}}$)")
    span = max((abs(r) for r in RESIDUALS_CM1), default=1.0) * 1.9 or 1.0
    axr.set_xlim(-span, span)
    axr.spines[["left", "right", "top"]].set_visible(False)
    axr.tick_params(labelsize=9)

    fig.suptitle({heading!r})
    fig.savefig(OUTPUT, dpi=200)
    print(f"wrote {{OUTPUT}}")


if __name__ == "__main__":
    main()
'''
