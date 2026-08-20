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

from typing import Annotated
from typing import Literal

from pydantic import BaseModel
from pydantic import Field

from tanabesugano.constants import CM1_TO_EV  # noqa: F401  (re-exported for the MCP layer)


# Constrains every tool's `d_count` parameter to the eight supported octahedral
# configurations; FastMCP surfaces this as an enum in the tool's input schema.
D_COUNT_LITERAL = Literal[2, 3, 4, 5, 6, 7, 8]

# Energy-unit enum exposed to every chart tool.  "cm1" is the canonical internal
# unit; "eV" and "nm" are converted on output only.  Note that "nm" inverts the
# axis (shorter wavelength = higher energy).
EnergyUnit = Literal["cm1", "eV", "nm"]

# 1 cm^-1 expressed in eV; also used in tanabesugano.tools (racah conversion).

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

    d_count: D_COUNT_LITERAL = Field(  # type: ignore[valid-type]
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
    energy_unit: EnergyUnit = Field(  # type: ignore[valid-type]
        default="cm1",
        title="Energy unit for y-axis",
        description="cm1 = wavenumbers, eV = electron volts, nm = nanometres (inverted axis).",
    )
