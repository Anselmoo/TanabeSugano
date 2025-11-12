"""Physical and computational constants for Tanabe-Sugano calculations."""

from __future__ import annotations

from enum import IntEnum


class ElectronConfiguration(IntEnum):
    """d-electron configurations for transition metal complexes.

    These values represent the number of d-electrons in the partially
    filled d-orbital shell of transition metal ions.
    """

    D2 = 2
    D3 = 3
    D4 = 4
    D5 = 5
    D6 = 6
    D7 = 7
    D8 = 8


# Numerical tolerances
ENERGY_TOLERANCE = 1e-4  # Threshold for energy level corrections in wavenumbers

# Array dimensions
PARAMETER_RANGE_LENGTH = 3  # Expected format: (start, stop, steps)
