#!/usr/bin/env python
"""Generate UV-Vis absorption reference figures for the spectrum-fitting examples.

For each documented coordination complex we:
  1. Render the observed UV-Vis absorption envelope from the literature band
     maxima (Gaussian peaks; intensities approximate the visual spectrum).
  2. Assign the three spin-allowed d8 d-d bands (3A2g -> 3T2g, 3T1g(F), 3T1g(P)).
  3. Annotate the reference ligand-field parameters Dq and B together with the
     nephelauxetic ratio beta from `nephelauxetic_analysis`.

These are the reference spectra the fitter is validated against (see
`test_spectrum_fitting.py`). Output PNGs land in `assets/uvvis/` and are
committed so the README / docs can show what the fitter consumes.

Run:  uv run python scripts/plot_uvvis_fits.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib


matplotlib.use("Agg")  # headless: write files without a display

import matplotlib.pyplot as plt
import numpy as np

from tanabesugano.mcp._compute import nephelauxetic_analysis
from tanabesugano.plot_style import ANNOTATION_COLORS
from tanabesugano.plot_style import apply_scientific_rcparams
from tanabesugano.plot_style import style_axes


# Okabe-Ito colour-blind-safe accents, matching the package palette.
# Roles, not literals: `script_export.py` draws the same two ideas and declared
# them separately, which is how "observed" came to mean vermillion in one figure
# surface and blue in the other.
OBSERVED_COLOR = ANNOTATION_COLORS["spectrum"]  # measured absorption envelope
BAND_COLOR = ANNOTATION_COLORS["observed"]  # assigned band maxima
PARAM_COLOR = ANNOTATION_COLORS["parameters"]  # parameter annotation box

# The three spin-allowed octahedral d8 transitions, low energy -> high energy.
# Mathtext for figures; plain ASCII for the exported txt headers.
D8_ASSIGNMENTS = (
    r"$^{3}A_{2g}\!\rightarrow\!^{3}T_{2g}$",
    r"$^{3}A_{2g}\!\rightarrow\!^{3}T_{1g}(F)$",
    r"$^{3}A_{2g}\!\rightarrow\!^{3}T_{1g}(P)$",
)
D8_ASSIGNMENTS_ASCII = (
    "3A2g->3T2g",
    "3A2g->3T1g(F)",
    "3A2g->3T1g(P)",
)


class Complex:
    """One documented complex: label, ion, observed bands, reference Dq/B."""

    def __init__(
        self,
        label: str,
        plain_label: str,
        slug: str,
        d_count: int,
        ion: str,
        bands_nm: list[float],
        intensities: list[float],
        ref_dq: float,
        ref_b: float,
        color_hint: str,
    ) -> None:
        self.label = label
        self.plain_label = plain_label
        self.slug = slug
        self.d_count = d_count
        self.ion = ion
        self.bands_nm = bands_nm
        self.intensities = intensities
        self.ref_dq = ref_dq
        self.ref_b = ref_b
        self.color_hint = color_hint

    @property
    def bands_cm1(self) -> list[float]:
        """Observed band positions converted nm -> cm^-1."""
        return [1.0e7 / nm for nm in self.bands_nm]


# Literature band maxima (nm) and reference ligand-field parameters (cm^-1).
# Sources: Chemistry LibreTexts; Doc Brown's chemistry notes;
# Lever, "Inorganic Electronic Spectroscopy" (2nd ed., 1984).
# For octahedral d8 the first band equals 10*Dq, hence Dq = nu1 / 10.
COMPLEXES: list[Complex] = [
    Complex(
        label=r"[Ni(H$_2$O)$_6$]$^{2+}$",
        plain_label="[Ni(H2O)6]2+",
        slug="ni_aqua",
        d_count=8,
        ion="Ni2+",
        bands_nm=[1176.0, 725.0, 395.0],  # ~8500, ~13800, ~25300 cm^-1
        intensities=[0.35, 0.55, 0.9],
        ref_dq=850.0,  # 10Dq ~ 8500 cm^-1
        ref_b=890.0,  # beta ~ 0.85 vs free-ion Ni2+ (1041)
        color_hint="green",
    ),
    Complex(
        label=r"[Ni(NH$_3$)$_6$]$^{2+}$",
        plain_label="[Ni(NH3)6]2+",
        slug="ni_ammine",
        d_count=8,
        ion="Ni2+",
        bands_nm=[925.0, 570.0, 360.0],  # ~10800, ~17500, ~27800 cm^-1
        intensities=[0.4, 0.6, 0.95],
        ref_dq=1080.0,  # 10Dq ~ 10800 cm^-1
        ref_b=870.0,  # beta ~ 0.84
        color_hint="blue-violet",
    ),
]


def _gaussian_envelope(
    grid_cm1: np.ndarray,
    centers_cm1: list[float],
    intensities: list[float],
    width_cm1: float = 1800.0,
) -> np.ndarray:
    """Sum of Gaussians approximating a measured d-d absorption envelope."""
    envelope = np.zeros_like(grid_cm1)
    for center, amp in zip(centers_cm1, intensities, strict=True):
        envelope += amp * np.exp(-0.5 * ((grid_cm1 - center) / width_cm1) ** 2)
    return envelope


def export_ascii(cx: Complex, out_dir: Path) -> Path:
    """Write the reference spectrum as a documented ASCII txt file.

    Columns are tab-separated (matching the examples/*.txt convention):
    wavenumber (cm^-1), wavelength (nm), absorbance (a.u.). A commented header
    records provenance, reference parameters, and the assigned band maxima so
    the file is self-describing and directly consumable by ts_fit_spectrum.
    """
    observed_cm1 = cx.bands_cm1
    neph = nephelauxetic_analysis(cx.d_count, cx.ref_b, cx.ion)

    grid = np.linspace(4000.0, 33000.0, 1500)
    envelope = _gaussian_envelope(grid, observed_cm1, cx.intensities)
    wavelengths = 1.0e7 / grid

    bands_str = ", ".join(f"{b:.0f}" for b in observed_cm1)
    assign_str = "; ".join(D8_ASSIGNMENTS_ASCII)

    header = (
        f"# UV-Vis reference spectrum — {cx.plain_label} "
        f"({cx.ion}, d{cx.d_count}, {cx.color_hint})\n"
        "# Reconstructed absorption envelope from literature band maxima "
        "(sum of Gaussians).\n"
        "# Sources: Chemistry LibreTexts; Doc Brown's chemistry notes; "
        "Lever, Inorganic Electronic Spectroscopy (1984).\n"
        f"# Reference parameters: Dq={cx.ref_dq:.0f} cm^-1  B={cx.ref_b:.0f} cm^-1  "
        f"beta={neph['beta']:.3f} ({neph['covalency']})\n"
        f"# Observed band maxima (cm^-1): {bands_str}\n"
        f"# Assignments (low->high energy): {assign_str}\n"
        "# columns: wavenumber_cm-1\twavelength_nm\tabsorbance_au\n"
    )

    out_path = out_dir / f"uvvis_fit_{cx.slug}.txt"
    with out_path.open("w", encoding="utf-8") as fh:
        fh.write(header)
        for wn, wl, ab in zip(grid, wavelengths, envelope, strict=True):
            fh.write(f"{wn:.6f}\t{wl:.6f}\t{ab:.6f}\n")
    return out_path


def render(cx: Complex, out_dir: Path) -> Path:
    """Render one complex's UV-Vis reference figure and return the written path."""
    observed_cm1 = cx.bands_cm1
    neph = nephelauxetic_analysis(cx.d_count, cx.ref_b, cx.ion)

    grid = np.linspace(4000.0, 33000.0, 1600)
    envelope = _gaussian_envelope(grid, observed_cm1, cx.intensities)

    fig, ax = plt.subplots(figsize=(7.4, 4.5))

    # Measured absorption envelope.
    ax.plot(grid, envelope, color=OBSERVED_COLOR, lw=2.0, label="observed envelope")
    ax.fill_between(grid, envelope, color=OBSERVED_COLOR, alpha=0.10)

    # Observed band maxima with d-d assignments.
    obs_heights = _gaussian_envelope(np.asarray(observed_cm1), observed_cm1, cx.intensities)
    ax.scatter(
        observed_cm1,
        obs_heights,
        color=BAND_COLOR,
        s=46,
        zorder=5,
        label="assigned bands",
    )
    for center, height, assignment in zip(
        observed_cm1,
        obs_heights,
        D8_ASSIGNMENTS,
        strict=True,
    ):
        ax.annotate(
            assignment,
            xy=(center, height),
            xytext=(0, 12),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=8.0,
            color=BAND_COLOR,
        )
        ax.annotate(
            f"{center:.0f} cm$^{{-1}}$",
            xy=(center, 0),
            xytext=(0, 3),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=7.0,
            color=OBSERVED_COLOR,
        )

    style_axes(
        ax,
        title=f"UV-Vis reference spectrum — {cx.label}  ({cx.color_hint}, d{cx.d_count})",
        x_label=r"wavenumber / cm$^{-1}$",
        y_label="absorbance (a.u.)",
    )
    # Keep the legend out of the assigned-band labels.
    leg = ax.get_legend()
    if leg is not None:
        leg.set_loc("upper left")
    ax.set_xlim(4000.0, 33000.0)
    ax.set_ylim(0.0, max(envelope) * 1.5)

    # Secondary wavelength axis (nm) with explicit, non-overlapping ticks.
    sec = ax.secondary_xaxis(
        "top",
        functions=(
            lambda w: 1.0e7 / np.where(w == 0, np.nan, w),
            lambda nm: 1.0e7 / np.where(nm == 0, np.nan, nm),
        ),
    )
    sec.set_xlabel("wavelength / nm")
    sec.set_xticks([2000, 1000, 700, 500, 400, 350])

    # Annotate the reference ligand-field parameters.
    txt = (
        f"reference:  Dq = {cx.ref_dq:.0f} cm$^{{-1}}$\n"
        f"            B  = {cx.ref_b:.0f} cm$^{{-1}}$\n"
        rf"            $\beta$  = {neph['beta']:.3f} ({neph['covalency']})"
    )
    ax.text(
        0.985,
        0.97,
        txt,
        transform=ax.transAxes,
        ha="right",
        va="top",
        fontsize=8.5,
        family="monospace",
        bbox={"boxstyle": "round,pad=0.4", "fc": "white", "ec": PARAM_COLOR, "alpha": 0.92},
    )

    fig.tight_layout()
    out_path = out_dir / f"uvvis_fit_{cx.slug}.png"
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path


def main() -> None:
    """Render every complex and report the written asset paths."""
    apply_scientific_rcparams()
    repo_root = Path(__file__).resolve().parent.parent
    out_dir = repo_root / "assets" / "uvvis"
    out_dir.mkdir(parents=True, exist_ok=True)

    for cx in COMPLEXES:
        png_path = render(cx, out_dir)
        print(f"wrote {png_path.relative_to(repo_root)}")
        txt_path = export_ascii(cx, out_dir)
        print(f"wrote {txt_path.relative_to(repo_root)}")


if __name__ == "__main__":
    main()
