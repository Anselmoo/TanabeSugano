"""Batch processing for Tanabe-Sugano diagram calculations."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from tanabesugano import matrices
from tanabesugano import tools
from tanabesugano.constants import PARAMETER_RANGE_LENGTH
from tanabesugano.constants import ElectronConfiguration


if TYPE_CHECKING:
    from collections.abc import Callable


# Mapping from electron configuration to solver class
ELECTRON_CONFIG_SOLVERS: dict[int, Callable] = {
    ElectronConfiguration.D2: matrices.d2,
    ElectronConfiguration.D3: matrices.d3,
    ElectronConfiguration.D4: matrices.d4,
    ElectronConfiguration.D5: matrices.d5,
    ElectronConfiguration.D6: matrices.d6,
    ElectronConfiguration.D7: matrices.d7,
    ElectronConfiguration.D8: matrices.d8,
}


def _validate_parameter_range(
    param: list[float],
    param_name: str,
) -> None:
    """Validate that a parameter range has the expected format.

    Parameters
    ----------
    param : list[float]
        Parameter range to validate
    param_name : str
        Name of the parameter for error messages

    Raises
    ------
    KeyError
        If the parameter range doesn't have exactly PARAMETER_RANGE_LENGTH values

    """
    if len(param) != PARAMETER_RANGE_LENGTH:
        msg = (
            f"The range of `{param_name}` is based on the three values: "
            f"start, stop, steps!"
        )
        raise KeyError(msg)


class Batch:
    """Batch calculation of Tanabe-Sugano diagrams across parameter ranges.

    This class performs calculations across ranges of crystal field splitting (Dq),
    Racah parameters (B, C) to generate comprehensive Tanabe-Sugano diagram data.
    """

    def __init__(
        self,
        Dq: list[float] | None = None,
        B: list[float] | None = None,
        C: list[float] | None = None,
        d_count: int = 5,
        slater: bool = False,
    ) -> None:
        """Initialize batch calculation parameters.

        Parameters
        ----------
        Dq : list[float] | None, optional
            Range for Oh crystal field splitting [start, stop, steps],
            by default [4000.0, 4500.0, 10]
        B : list[float] | None, optional
            Range for Racah B parameter [start, stop, steps],
            by default [400.0, 4500.0, 10]
        C : list[float] | None, optional
            Range for Racah C parameter [start, stop, steps],
            by default [3600.0, 4000, 10]
        d_count : int, optional
            Electron configuration (d2-d8), by default 5
        slater : bool, optional
            Transform from Racah to Slater-Condon parameters, by default False

        """
        if Dq is None:
            Dq = [4000.0, 4500.0, 10]
        if B is None:
            B = [400.0, 4500.0, 10]
        if C is None:
            C = [3600.0, 4000, 10]

        # Validate parameter ranges
        _validate_parameter_range(Dq, "Dq")
        _validate_parameter_range(B, "B")
        _validate_parameter_range(C, "C")

        self.Dq = np.linspace(Dq[0], Dq[1], int(Dq[2]))  # Oh-crystalfield-splitting
        self.B = np.linspace(B[0], B[1], int(B[2]))  # Racah-B-parameter
        self.C = np.linspace(C[0], C[1], int(C[2]))  # Racah-C-parameter

        if slater:
            # Transformin Racah to Slater-Condon
            self.B, self.C = tools.racah(B, C)

        self.d_count = d_count
        if self.d_count in {
            ElectronConfiguration.D4,
            ElectronConfiguration.D5,
            ElectronConfiguration.D6,
        }:
            self._size = 42
        if self.d_count in {ElectronConfiguration.D3, ElectronConfiguration.D7}:
            self._size = 19
        if self.d_count in {ElectronConfiguration.D2, ElectronConfiguration.D8}:
            self._size = 10
        self.result: list[dict] = []

    def calculation(self) -> None:
        """Fill self.result with iTS states of over-iterated energy range."""
        # Get the solver class for this electron configuration
        solver_class = ELECTRON_CONFIG_SOLVERS.get(self.d_count)
        if solver_class is None:
            msg = "not a correct value!"
            raise ValueError(msg)

        for _Dq in self.Dq:
            for _B in self.B:
                for _C in self.C:
                    states = solver_class(Dq=_Dq, B=_B, C=_C).solver()
                    self.result.append(
                        {
                            "d_count": self.d_count,
                            "Dq": _Dq,
                            "B": _B,
                            "C": _C,
                            "states": states,
                        },
                    )

    @property
    def return_result(self) -> list[dict]:
        """Return the calculated Tanabe-Sugano diagram results.

        Returns
        -------
        list[dict]
            List of dictionaries containing d_count, Dq, B, C,
            and states for each calculation.

        """
        return self.result


if __name__ == "__main__":
    res = Batch()
    res.calculation()
