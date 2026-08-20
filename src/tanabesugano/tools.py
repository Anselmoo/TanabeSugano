"""Tools for Slater-Condon to Racah parameter transformations."""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import overload

from tanabesugano.constants import WAVENUMBER_PER_EV


if TYPE_CHECKING:
    import numpy as np

    from numpy.typing import NDArray


@overload
def racah(F2: float, F4: float) -> tuple[float, float]: ...
@overload
def racah(
    F2: NDArray[np.float64],
    F4: NDArray[np.float64],
) -> tuple[NDArray[np.float64], NDArray[np.float64]]: ...
def racah(
    F2: float | NDArray[np.float64],
    F4: float | NDArray[np.float64],
) -> tuple[float | NDArray[np.float64], float | NDArray[np.float64]]:
    """Transform the Slater-Condon-Parameter to Racah-Parameter.

    Re-calculating and normalization of the Slater-Condon-Parameter to Racah-Parameter
        eV will be converted to wavenumbers

    Callers pass either two floats or two arrays together (never one of each), and
    get back the matching shape: two floats in, two floats out; two arrays in, two
    arrays out. The overloads above encode that correlation so call sites keep the
    scalar-vs-array type of their result -- the single-signature union previously
    here decorrelated `F2`/`F4` from the return value, which is why
    ``self.B, self.C = tools.racah(self.B, self.C)`` in `batch.py` (both always
    arrays there) widened to `float | NDArray` afterwards.

    Args:
        F2 (Union[float, NDArray[np.float64]]): Slater-Condon-Pramater `F2` as
            float-value or array.
        F4 (Union[float, NDArray[np.float64]]): Slater-Condon-Pramater `F4` as
            float-value or array.

    Returns:
        Tuple[Union[float, NDArray[np.float64]], Union[float, NDArray[np.float64]]]:
            Return the racah parameters, matching the input's scalar-or-array shape.

    """
    eVcm = WAVENUMBER_PER_EV
    B = eVcm * (F2 / 49.0 - 5 / 441.0 * F4)
    C = eVcm * (35 / 441.0 * F4)
    return B, C
