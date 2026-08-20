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


# Per-configuration free-ion Racah defaults.
#
# PROVENANCE CAVEAT: the implied C/B ratios (d2 4.420 ... d8 4.709) are the
# "classic" per-dn values, but no citable primary source for this exact set was
# located -- the original Tanabe-Sugano papers are paywalled and Koenig & Kremer
# (1977) prints diagrams, not the ratios. C/B is a modelling choice rather than
# a constant (Adachi 2025 argues 3.7 / 4.7 / 8.0 for d3 alone), so treat these
# as documented defaults, not physical truth. test_leftovers.py pins them so a
# change has to be deliberate.
#
# The CLI takes a different route: it uses ONE (B, C) pair for whatever d_count
# is selected, defaulting to the d5 values here.
DEFAULTS: dict[int, _DConfig] = {
    2: {"ground_term": "3F", "matrix_size": 10, "default_B": 860.0, "default_C": 3801.0},
    3: {"ground_term": "4F", "matrix_size": 19, "default_B": 918.0, "default_C": 4133.0},
    4: {"ground_term": "5D", "matrix_size": 42, "default_B": 965.0, "default_C": 4449.0},
    5: {"ground_term": "6S", "matrix_size": 42, "default_B": 860.0, "default_C": 3850.0},
    6: {"ground_term": "5D", "matrix_size": 42, "default_B": 1065.0, "default_C": 5120.0},
    7: {"ground_term": "4F", "matrix_size": 19, "default_B": 971.0, "default_C": 4499.0},
    8: {"ground_term": "3F", "matrix_size": 10, "default_B": 1030.0, "default_C": 4850.0},
}

# Ground term in the WEAK-FIELD (high-spin) octahedral limit, spelled with the
# solver's own term keys.
#
# This table is a TEST ORACLE, not production data. Production code must derive
# the ground term per point via _compute.reference_ground_term(), because the
# ground term is genuinely Dq-dependent for d4/d6/d7 (d6 flips 5_T_2 -> 1_A_1
# across the spin crossover) -- any static per-d_count answer is wrong physics
# somewhere on the diagram. What IS static is the weak-field limit, which is
# also independent of B (verified across B = 400..1400), so this table is a
# sound independent check on that derivation.
#
# Key spellings follow the solver's now-uniform vocabulary: Eg carries no
# subscript (5_E, not 5_E_1) and there is no T3 irrep (1_T_2, not 1_T_3).
HIGH_SPIN_GROUND_TERM: dict[int, str] = {
    2: "3_T_1",  # 3F -> 3T1g
    3: "4_A_2",  # 4F -> 4A2g
    4: "5_E",  # 5D -> 5Eg
    5: "6_A_1",  # 6S -> 6A1g
    6: "5_T_2",  # 5D -> 5T2g
    7: "4_T_1",  # 4F -> 4T1g
    8: "3_A_2",  # 3F -> 3A2g
}


FREE_ION_RACAH_B: dict[str, float] = {
    # Free-ion Racah B parameters in cm^-1. Source: A.B.P. Lever,
    # "Inorganic Electronic Spectroscopy" (2nd ed., 1984), Table 6.
    # Grouped by the d-electron count each ion presents in an octahedral field.
    # d2
    "Ti2+": 718.0,
    "V3+": 861.0,
    # d3
    "V2+": 766.0,
    "Cr3+": 918.0,
    "Mn4+": 1064.0,
    # d4
    "Cr2+": 830.0,
    "Mn3+": 1140.0,
    # d5
    "Mn2+": 860.0,
    "Fe3+": 1015.0,
    # d6
    "Fe2+": 1058.0,
    "Co3+": 1100.0,
    # d7
    "Co2+": 971.0,
    "Ni3+": 1035.0,
    # d8
    "Ni2+": 1041.0,
}

# Which free ions map onto each d-electron count (for validation + suggestions).
ION_BY_D_COUNT: dict[int, tuple[str, ...]] = {
    2: ("Ti2+", "V3+"),
    3: ("V2+", "Cr3+", "Mn4+"),
    4: ("Cr2+", "Mn3+"),
    5: ("Mn2+", "Fe3+"),
    6: ("Fe2+", "Co3+"),
    7: ("Co2+", "Ni3+"),
    8: ("Ni2+",),
}

# Jorgensen k(metal) parameters for the nephelauxetic relation
# (1 - beta) = h(ligand) * k(metal). Source: Jorgensen (1962); Lever (1984).
# Only well-established values are listed; ions absent here simply skip the
# ligand-suggestion step (beta and covalency are still reported).
NEPHELAUXETIC_METAL_K: dict[str, float] = {
    "Mn2+": 0.07,
    "V2+": 0.10,
    "Ni2+": 0.12,
    "Co2+": 0.14,
    "Cr3+": 0.21,
    "Fe3+": 0.24,
    "Co3+": 0.35,
    "Mn4+": 0.50,
}

# Nephelauxetic series: ligands ordered by increasing cloud expansion
# (decreasing beta). Each entry carries Jorgensen's h parameter, where
# (1 - beta) ~= h(ligand) * k(metal). Source: Jorgensen (1962); Lever (1984).
NEPHELAUXETIC_SERIES: tuple[tuple[str, float], ...] = (
    ("F-", 0.8),
    ("H2O", 1.0),
    ("urea", 1.2),
    ("NH3", 1.4),
    ("en", 1.5),
    ("ox2-", 1.5),
    ("NCS-", 2.0),
    ("Cl-", 2.0),
    ("CN-", 2.0),
    ("Br-", 2.3),
    ("N3-", 2.4),
    ("I-", 2.7),
)


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
