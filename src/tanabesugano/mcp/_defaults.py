"""Default Racah parameters and ground-state metadata per d-configuration.

Values mirror the defaults already encoded in tanabesugano.matrices.d{N}.__init__,
extracted here so the MCP layer can advertise them without instantiating solvers.
"""

from __future__ import annotations

from typing import TypedDict


class _DConfig(TypedDict):
    ground_term: str
    matrix_size: int
    default_B: float
    default_C: float


DEFAULTS: dict[int, _DConfig] = {
    2: {"ground_term": "3F", "matrix_size": 10, "default_B": 860.0, "default_C": 3801.0},
    3: {"ground_term": "4F", "matrix_size": 19, "default_B": 918.0, "default_C": 4133.0},
    4: {"ground_term": "5D", "matrix_size": 42, "default_B": 965.0, "default_C": 4449.0},
    5: {"ground_term": "6S", "matrix_size": 42, "default_B": 860.0, "default_C": 3850.0},
    6: {"ground_term": "5D", "matrix_size": 42, "default_B": 1065.0, "default_C": 5120.0},
    7: {"ground_term": "4F", "matrix_size": 19, "default_B": 971.0, "default_C": 4499.0},
    8: {"ground_term": "3F", "matrix_size": 10, "default_B": 1030.0, "default_C": 4850.0},
}


WHY_TANABE_SUGANO = (
    "Why use a Tanabe-Sugano diagram? They normalise all term energies by "
    "Racah B, so one chart is universal for every metal ion with a given "
    "d-electron count. The chart shows spin-allowed AND spin-forbidden d-d "
    "transitions side-by-side, exposes the high-spin / low-spin crossover "
    "for d4-d7 as a discontinuity in the ground term, and lets chemists fit "
    "Dq and B from two experimental band ratios (the 'two-ratio method') "
    "without numerical optimisation. That is why TS diagrams remain the "
    "go-to tool 70+ years after Tanabe & Sugano (1954) for interpreting "
    "visible/UV absorption spectra of octahedral transition-metal complexes "
    "-- a single coarse approximation (crystal-field theory + Racah "
    "parameters) that nails both paired and unpaired d-electron systems."
)


GROUND_STATE_NOTES: dict[int, str] = {
    2: "d2 (e.g. Ti2+, V3+): octahedral ground state 3T1g, three spin-allowed d-d transitions.",
    3: "d3 (e.g. V2+, Cr3+): 4A2g ground state; classic three-band spectrum used to fit Dq, B.",
    4: "d4 (e.g. Cr2+, Mn3+): high-spin 5Eg or low-spin 3T1g across the spin-crossover point.",
    5: "d5 (e.g. Mn2+, Fe3+): high-spin 6A1g; all d-d transitions are spin-forbidden (weak bands).",
    6: "d6 (e.g. Fe2+, Co3+): 5T2g high-spin or 1A1g low-spin; spin-crossover region near 2Dq/B~2.",
    7: "d7 (e.g. Co2+, Ni3+): 4T1g(F) high-spin or 2Eg low-spin.",
    8: (
        "d8 (e.g. Ni2+, Cu3+): 3A2g ground state; three spin-allowed transitions "
        "to 3T2g, 3T1g(F), 3T1g(P)."
    ),
}
