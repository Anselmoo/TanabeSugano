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

# Unit conversion. Single source of truth: cmd.py previously used 0.00012
# (~1/8333) while tools.py and the MCP layer used 1/8065.54 -- a 3.3% split
# between two conversions in the same package.
WAVENUMBER_PER_EV: float = 8065.54
CM1_TO_EV: float = 1.0 / WAVENUMBER_PER_EV

# Secular-matrix size per configuration, excluding the ground level.
# Previously duplicated as three unguarded `if` chains (batch.py, cmd.py) plus a
# "matrix_size" field in mcp/_defaults.py. The `if` chains had no `else`, so an
# unsupported d_count left self._size unset and surfaced as an AttributeError
# from __init__ -- making the intended ValueError guard unreachable.
MATRIX_SIZE_BY_D_COUNT: dict[int, int] = {
    2: 10,
    3: 19,
    4: 42,
    5: 42,
    6: 42,
    7: 19,
    8: 10,
}


def matrix_size(d_count: int) -> int:
    """Secular-matrix size for ``d_count``, or ValueError if unsupported."""
    try:
        return MATRIX_SIZE_BY_D_COUNT[int(d_count)]
    except (KeyError, TypeError, ValueError):
        supported = ", ".join(f"d{d}" for d in sorted(MATRIX_SIZE_BY_D_COUNT))
        msg = (
            f"d_count must be one of {supported} "
            f"(the number of d electrons, 2 to 8 -- NOT the number of unpaired "
            f"electrons, which is 2 for d8); got {d_count!r}"
        )
        raise ValueError(msg) from None
