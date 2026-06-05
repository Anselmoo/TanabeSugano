"""Typed input schemas shared by tools, apps, and the Form entry point.

Centralising the d-count Literal and the Pydantic input model means every
tool advertises the same enum / range constraints in its JSON schema, and
the `ts_explore_app` Form can drive any of them via `Form.from_model`.
"""

from __future__ import annotations

from typing import Annotated
from typing import Literal

from pydantic import BaseModel
from pydantic import Field


# Constrains every tool's `d_count` parameter to the eight supported octahedral
# configurations; FastMCP surfaces this as an enum in the tool's input schema.
D_COUNT_LITERAL = Literal[2, 3, 4, 5, 6, 7, 8]

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
    """User-facing parameter set for the Tanabe-Sugano explore form.

    Drives both `ts_explore_app` (via Form.from_model) and is reused as the
    shape that submit-callbacks pass to `ts_diagram_app`.
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
