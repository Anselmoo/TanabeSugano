"""Typed input schemas + shared scalar constants for the MCP layer.

Centralising the d-count ``Literal``, energy-unit enum, and Racah-bound
``Annotated`` types means every tool advertises the same enum / range
constraints in its JSON schema. Also exposes the cm⁻¹ → eV conversion
factor used by every energy-unit aware tool.

``TSInput`` (the Pydantic ``BaseModel`` at the bottom of the file) was
originally consumed by the now-removed ``ts_explore_app`` Form. It is
kept as a public schema that future form/explore surfaces can reuse, but
no tool currently dispatches against it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Annotated
from typing import Literal

from pydantic import BaseModel
from pydantic import Field

from tanabesugano.constants import CM1_TO_EV  # noqa: F401  (re-exported for the MCP layer)
from tanabesugano.constants import WAVENUMBER_PER_EV


if TYPE_CHECKING:
    from collections.abc import Sequence


# Constrains every tool's `d_count` parameter to the eight supported octahedral
# configurations; FastMCP surfaces this as an enum in the tool's input schema.
D_COUNT_LITERAL = Literal[2, 3, 4, 5, 6, 7, 8]

# Energy-unit enum exposed to every chart tool.  "cm1" is the canonical internal
# unit; "eV" and "nm" are converted on output only.  Note that "nm" inverts the
# axis (shorter wavelength = higher energy).
EnergyUnit = Literal["cm1", "eV", "nm"]

# 1 cm^-1 expressed in eV; also used in tanabesugano.tools (racah conversion).

EV_CEILING_CM1 = 100.0
"""A peak list whose largest entry is below this is not in cm^-1.

d-d band maxima in eV lie at about 0.4-6 (and in kK at 4-50), so both stay under
100; no d-d band in cm^-1 does.
"""

NM_CEILING_CM1 = 3000.0
"""A peak list whose largest entry is below this (and above 100) reads as nm.

d-d bands in nm lie at 200-2500. The lowest real d-d band in cm^-1 is a Td Co(II)
nu1 near 3300, and an octahedral d2-d8 list always reaches well past 3000: the
lowest maximum over the 208 synthetic audit cases is 4080 (d6, Dq 408).
"""

DD_CEILING_CM1 = 100_000.0
"""A peak list reaching past this many cm^-1 is no d-d spectrum.

d-d bands end at about 50000 cm^-1 (200 nm). The case this catches is a kK list
declared as eV -- energy_unit has no kK, and Ni(H2O)6 at 8.5/13.8/25.3 kK read as
eV lands at 68557-204056 -- or a cm^-1 list declared as eV.
"""


def suspect_unit(peaks_cm1: Sequence[float]) -> tuple[Literal["eV", "nm"], list[float]] | None:
    """Return the unit a cm^-1 peak list was probably given in, with its cm^-1 values.

    Reads the largest entry only, so one stray small value in a real cm^-1 list
    does not trip it. ``None`` when the list looks like cm^-1 (or is empty).
    """
    positive = [p for p in peaks_cm1 if p > 0]
    if not positive:
        return None
    top = max(positive)
    if top < EV_CEILING_CM1:
        return "eV", [float(round(p * WAVENUMBER_PER_EV)) for p in positive]
    if top < NM_CEILING_CM1:
        return "nm", [float(round(1e7 / p)) for p in positive]
    return None


def unit_error(peaks_cm1: Sequence[float], *, unit_param: str | None = None) -> str | None:
    """The refusal for a peak list that is not in cm^-1, or ``None`` when it is.

    ``unit_param`` names a sibling parameter (``energy_unit``) that can declare the
    unit; without one the caller is shown the converted values to pass instead.
    """
    top = max((p for p in peaks_cm1 if p > 0), default=0.0)
    if top > DD_CEILING_CM1:
        return (
            f"the largest peak is {top:.0f} cm^-1, above any d-d band (they end near "
            "50000) -- if these were kK given as eV, multiply the kK values by 1000 and "
            "pass them in cm^-1."
        )
    guess = suspect_unit(peaks_cm1)
    if guess is None:
        return None
    unit, converted = guess
    shown = [int(c) for c in converted]
    if unit == "eV":
        kilo = [round(p * 1000.0) for p in peaks_cm1 if p > 0]
        meaning = f"eV (= {shown} cm^-1) or kK (= {kilo} cm^-1)"
        cm1 = "if kK, multiply by 1000 and pass cm^-1"
        fix = f"if eV, pass {unit_param}='eV'; {cm1}" if unit_param else f"{cm1}; if eV, convert"
    else:
        meaning = f"nm (= {shown} cm^-1)"
        fix = f"pass {unit_param}='nm', or give cm^-1" if unit_param else "pass cm^-1"
    return f"these peaks look like {meaning}, but they are read in cm^-1 -- {fix}."


# Typical maxima used to validate Sliders / range queries.
DQ_MAX = 5000.0  # cm^-1; well past the strong-field limit for first-row TM ions
B_MAX = 2000.0  # cm^-1; Co3+ tops the chart around 1100
C_MAX = 8000.0  # cm^-1; ~5x typical B

DqValue = Annotated[
    float,
    Field(ge=0.0, le=DQ_MAX, description="Crystal-field strength Dq (cm^-1)."),
]
BValue = Annotated[float, Field(gt=0.0, le=B_MAX, description="Racah B (cm^-1).")]
CValue = Annotated[float, Field(gt=0.0, le=C_MAX, description="Racah C (cm^-1).")]
Steps = Annotated[int, Field(ge=2, le=500, description="Number of sweep points.")]


class TSInput(BaseModel):
    """User-facing parameter set for a Tanabe-Sugano sweep.

    Public schema kept available for future form/explore surfaces; the
    original ``ts_explore_app`` consumer was removed (its Prefab
    ``Form.from_model`` rendered as a frozen panel in Claude Desktop).
    Defaults match the typical first-row-transition-metal regime.
    """

    d_count: D_COUNT_LITERAL = Field(
        default=5,
        title="d-electron count",
        description="Number of d-electrons (d2 ... d8).",
    )
    dq_min: DqValue = Field(default=0.0, title="Dq min (cm^-1)")
    dq_max: DqValue = Field(default=1500.0, title="Dq max (cm^-1)")
    steps: Steps = Field(default=60, title="Sweep steps")
    B: BValue = Field(default=860.0, title="Racah B (cm^-1)")
    C: CValue = Field(default=3850.0, title="Racah C (cm^-1)")
    normalize: bool = Field(
        default=True,
        title="Normalize by B (Tanabe-Sugano x/y axes)",
    )
    energy_unit: EnergyUnit = Field(
        default="cm1",
        title="Energy unit for y-axis",
        description="cm1 = wavenumbers, eV = electron volts, nm = nanometres (inverted axis).",
    )
