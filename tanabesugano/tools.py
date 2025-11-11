"""Tools for Slater-Condon to Racah parameter transformations."""

from __future__ import annotations

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    import numpy as np


def racah(
    F2: float | np.array,
    F4: float | np.array,
) -> tuple[float, float] | tuple[np.array, np.array]:
    """Transform the Slater-Condon-Parameter to Racah-Parameter.

    Re-calculating and normalization of the Slater-Condon-Parameter to Racah-Parameter
        eV will be converted to wavenumbers

    Args:
        F2 (Union[float, np.array]): Slater-Condon-Pramater `F2` as float-value or
            array.
        F4 (Union[float, np.array]): Slater-Condon-Pramater `F4` as float-value or
            array.

    Returns:
        Union[Tuple[float, float], Tuple[np.array, np.array]]: Return the racah
            parameters.

    """
    eVcm = 8065.54
    B = eVcm * (F2 / 49.0 - 5 / 441.0 * F4)
    C = eVcm * (35 / 441.0 * F4)
    return B, C
