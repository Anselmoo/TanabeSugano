"""Matrix definitions for d-orbital electronic state calculations."""

from __future__ import annotations


try:
    from typing import TypeAlias
except ImportError:
    from typing import Any as TypeAlias

import numpy as np

from numpy._typing._array_like import NDArray
from numpy.linalg import eigh

from tanabesugano.constants import ENERGY_TOLERANCE


_sqrt2 = np.sqrt(2.0)
_sqrt3 = np.sqrt(3.0)
_sqrt6 = np.sqrt(6.0)

_2sqrt2 = _sqrt2 * 2.0
_2sqrt3 = _sqrt3 * 2.0
_3sqrt2 = _sqrt2 * 3.0
_3sqrt3 = _sqrt3 * 3.0
_3sqrt6 = _sqrt6 * 3.0

Float64Array: TypeAlias = NDArray[np.float64]


class LigandFieldTheory:
    """Parent class for ligand field theory configurations."""

    def __init__(self, Dq: float, B: float, C: float) -> None:
        """Initialize the configuration with given parameters.

        Args:
            Dq (float): Crystal field splitting in wavenumbers (cm-1).
            B (float): Racah parameter B in wavenumbers (cm-1).
            C (float): Racah parameter C in wavenumbers (cm-1).

        """
        self.Dq = np.float64(Dq)
        self.B = np.float64(B)
        self.C = np.float64(C)

    def eigensolver(self, matrix: Float64Array) -> Float64Array:
        """Solve for the eigenvalues of the given matrix.

        Args:
            matrix (Float64Array): 2-dimensional square array representing the TS matrix
                of the ligand field Hamiltonian.

        Returns:
            Float64Array: 1-dimensional array of eigenvalues of the diagonalized ligand
                field Hamiltonian.

        """
        return eigh(matrix)[0]

    def solver(self) -> dict[str, Float64Array]:
        """Solve for all states and return a dictionary of results.

        Returns:
            Dict[str, Float64Array]: Dictionary with atomic term symbols as keys and
                eigenvalues as values.

        """
        msg = "Subclasses should implement this method."
        raise NotImplementedError(msg)

    def construct_matrix(
        self,
        diag_elements: list[float],
        off_diag_elements: dict[tuple[int, int], float],
    ) -> Float64Array:
        """Construct a symmetric matrix from diagonal and off-diagonal elements."""
        size = len(diag_elements)
        matrix = np.zeros((size, size))
        np.fill_diagonal(matrix, diag_elements)
        for (i, j), value in off_diag_elements.items():
            matrix[i, j] = value
            matrix[j, i] = value  # Assuming the matrix is symmetric
        return matrix


class d2(LigandFieldTheory):
    """Class representing the d2 configuration in ligand field theory."""

    def __init__(self, Dq: float = 0.0, B: float = 860.0, C: float = 3801.0) -> None:
        """Initialize the d2 configuration with given parameters.

        Args:
            Dq (float): Crystal field splitting in wavenumbers (cm-1).
            B (float): Racah parameter B in wavenumbers (cm-1).
            C (float): Racah parameter C in wavenumbers (cm-1).

        """
        super().__init__(Dq, B, C)

    def A_1_1_states(self) -> Float64Array:
        """Calculate the A_1_1 states."""
        diag_elements = [
            -8 * self.Dq + 10 * self.B + 5 * self.C,
            +12 * self.Dq + 8 * self.B + 4 * self.C,
        ]
        off_diag_elements = {(0, 1): _sqrt6 * (2 * self.B + self.C)}
        states = self.construct_matrix(diag_elements, off_diag_elements)
        return self.eigensolver(states)

    def E_1_states(self) -> Float64Array:
        """Calculate the E_1 states."""
        diag_elements = [-8 * self.Dq + self.B + 2 * self.C, +12 * self.Dq + 2 * self.C]
        off_diag_elements = {(0, 1): -_2sqrt3 * self.B}
        states = self.construct_matrix(diag_elements, off_diag_elements)
        return self.eigensolver(states)

    def T_1_2_states(self) -> Float64Array:
        """Calculate the T_1_2 states."""
        diag_elements = [-8 * self.Dq + self.B + 2 * self.C, +2 * self.Dq + 2 * self.C]
        off_diag_elements = {(0, 1): +_2sqrt3 * self.B}
        states = self.construct_matrix(diag_elements, off_diag_elements)
        return self.eigensolver(states)

    def T_3_1_states(self) -> Float64Array:
        """Calculate the T_3_1 states."""
        diag_elements = [-8 * self.Dq - 5 * self.B, +2 * self.Dq + 4 * self.B]
        off_diag_elements = {(0, 1): 6 * self.B}
        states = self.construct_matrix(diag_elements, off_diag_elements)
        return self.eigensolver(states)

    def solver(self) -> dict[str, Float64Array]:
        """Solve for all states and return a dictionary of results.

        Returns:
            Dict[str, Float64Array]: Dictionary with atomic term symbols as keys and
                eigenvalues as values.

        """
        # Ligand field independent states
        GS = self.T_3_1_states()[0]

        T_1_1 = np.array([+2 * self.Dq + 4 * self.B + 2 * self.C]) - GS
        T_3_2 = np.array([+2 * self.Dq - 8 * self.B]) - GS
        A_3_2 = np.array([12 * self.Dq - 8 * self.B]) - GS

        # Ligand field dependent states
        A_1_1 = self.A_1_1_states() - GS
        E_1 = self.E_1_states() - GS
        T_1_2 = self.T_1_2_states() - GS
        T_3_1 = self.T_3_1_states() - GS

        return {
            "1_A_1": A_1_1,
            "1_E": E_1,
            "1_T_3": T_1_2,
            "3_T_1": T_3_1,
            "1_T_1": T_1_1,
            "3_T_2": T_3_2,
            "3_A_2": A_3_2,
        }


class d3(LigandFieldTheory):
    """Class representing the d3 configuration in ligand field theory."""

    def __init__(self, Dq: float = 0.0, B: float = 918.0, C: float = 4133.0) -> None:
        """Initialize the d3 configuration with given parameters.

        Args:
            Dq (float): Crystal field splitting in wavenumbers (cm-1).
            B (float): Racah parameter B in wavenumbers (cm-1).
            C (float): Racah parameter C in wavenumbers (cm-1).

        """
        super().__init__(Dq, B, C)

    def T_2_2_states(self) -> Float64Array:
        """Calculate the T_2_2 states."""
        diag_elements = [
            -12 * self.Dq + 5 * self.C,
            -2 * self.Dq - 6 * self.B + 3 * self.C,
            -2 * self.Dq + 4 * self.B + 3 * self.C,
            +8 * self.Dq + 6 * self.B + 5 * self.C,
            +8 * self.Dq - 2 * self.B + 3 * self.C,
        ]
        off_diag_elements = {
            (0, 1): -_3sqrt3 * self.B,
            (0, 2): -5 * _sqrt3 * self.B,
            (0, 3): 4 * self.B + 2 * self.C,
            (0, 4): 2 * self.B,
            (1, 2): 3 * self.B,
            (1, 3): -_3sqrt3 * self.B,
            (1, 4): -_3sqrt3 * self.B,
            (2, 3): -_sqrt3 * self.B,
            (2, 4): +_sqrt3 * self.B,
            (3, 4): 10 * self.B,
        }
        states = self.construct_matrix(diag_elements, off_diag_elements)
        return self.eigensolver(states)

    def T_2_1_states(self) -> Float64Array:
        """Calculate the T_2_1 states."""
        diag_elements = [
            -12 * self.Dq - 6 * self.B + 3 * self.C,
            -2 * self.Dq + 3 * self.C,
            -2 * self.Dq - 6 * self.B + 3 * self.C,
            +8 * self.Dq - 6 * self.B + 3 * self.C,
            +8 * self.Dq - 2 * self.B + 3 * self.C,
        ]
        off_diag_elements = {
            (0, 1): -3 * self.B,
            (0, 2): +3 * self.B,
            (0, 3): 0.0,
            (0, 4): -_2sqrt3 * self.B,
            (1, 2): -3 * self.B,
            (1, 3): +3 * self.B,
            (1, 4): _3sqrt3 * self.B,
            (2, 3): -3 * self.B,
            (2, 4): -_sqrt3 * self.B,
            (3, 4): _2sqrt3 * self.B,
        }
        states = self.construct_matrix(diag_elements, off_diag_elements)
        return self.eigensolver(states)

    def E_2_states(self) -> Float64Array:
        """Calculate the E_2 states."""
        diag_elements = [
            -12 * self.Dq - 6 * self.B + 3 * self.C,
            -2 * self.Dq + 8 * self.B + 6 * self.C,
            -2 * self.Dq - 1 * self.B + 3 * self.C,
            +18 * self.Dq - 8 * self.B + 4 * self.C,
        ]
        off_diag_elements = {
            (0, 1): -6 * _sqrt2 * self.B,
            (0, 2): -_3sqrt2 * self.B,
            (0, 3): 0.0,
            (1, 2): 10 * self.B,
            (1, 3): +_sqrt3 * (2 * self.B + self.C),
            (2, 3): _2sqrt3 * self.B,
        }
        states = self.construct_matrix(diag_elements, off_diag_elements)
        return self.eigensolver(states)

    def T_4_1_states(self) -> Float64Array:
        """Calculate the T_4_1 states."""
        diag_elements = [-2 * self.Dq - 3 * self.B, +8 * self.Dq - 12 * self.B]
        off_diag_elements = {(0, 1): 6 * self.B}
        states = self.construct_matrix(diag_elements, off_diag_elements)
        return self.eigensolver(states)

    def solver(self) -> dict[str, Float64Array]:
        """Solve for all states and return a dictionary of results.

        Returns:
            Dict[str, Float64Array]: Dictionary with atomic term symbols as keys and
                eigenvalues as values.

        """
        # Ligand field independent states
        GS = np.array([-12 * self.Dq - 15 * self.B])

        A_4_2 = np.array([0], dtype=np.float64)
        T_4_2 = np.array([-2 * self.Dq - 15 * self.B]) - GS

        A_2_1 = np.array([-2 * self.Dq - 11 * self.B + 3 * self.C]) - GS
        A_2_2 = np.array([-2 * self.Dq + 9 * self.B + 3 * self.C]) - GS

        # Ligand field dependent states
        T_2_2 = self.T_2_2_states() - GS
        T_2_1 = self.T_2_1_states() - GS
        E_2 = self.E_2_states() - GS
        T_4_1 = self.T_4_1_states() - GS

        return {
            "2_T_2": T_2_2,
            "2_T_1": T_2_1,
            "2_E": E_2,
            "4_T_1": T_4_1,
            "4_A_2": A_4_2,
            "4_T_2": T_4_2,
            "2_A_1": A_2_1,
            "2_A_2": A_2_2,
        }


class d4(LigandFieldTheory):
    """Class representing the d4 configuration in ligand field theory."""

    def __init__(self, Dq: float = 0.0, B: float = 965.0, C: float = 4449.0) -> None:
        """Initialize the d4 configuration with given parameters.

        Args:
            Dq (float): Crystal field splitting in wavenumbers (cm-1).
            B (float): Racah parameter B in wavenumbers (cm-1).
            C (float): Racah parameter C in wavenumbers (cm-1).

        """
        super().__init__(Dq, B, C)

    def T_3_1_states(self) -> Float64Array:
        """Calculate the T_3_1 states."""
        diag_elements = [
            -16 * self.Dq - 15 * self.B + 5 * self.C,
            -6 * self.Dq - 11 * self.B + 4 * self.C,
            -6 * self.Dq - 3 * self.B + 6 * self.C,
            +4 * self.Dq - self.B + 6 * self.C,
            +4 * self.Dq - 9 * self.B + 4 * self.C,
            +4 * self.Dq - 11 * self.B + 4 * self.C,
            +14 * self.Dq - 16 * self.B + 5 * self.C,
        ]
        off_diag_elements = {
            (0, 1): -_sqrt6 * self.B,
            (0, 2): -_3sqrt2 * self.B,
            (0, 3): _sqrt2 * (2 * self.B + self.C),
            (0, 4): -_2sqrt2 * self.B,
            (0, 5): 0.0,
            (0, 6): 0.0,
            (1, 2): 5 * _sqrt3 * self.B,
            (1, 3): _sqrt3 * self.B,
            (1, 4): -_sqrt3 * self.B,
            (1, 5): 3 * self.B,
            (1, 6): _sqrt6 * self.B,
            (2, 3): -3 * self.B,
            (2, 4): -3 * self.B,
            (2, 5): 5 * _sqrt3 * self.B,
            (2, 6): _sqrt2 * (self.B + self.C),
            (3, 4): -10 * self.B,
            (3, 5): 0.0,
            (3, 6): _3sqrt2 * self.B,
            (4, 5): -2 * _sqrt3 * self.B,
            (4, 6): -_3sqrt2 * self.B,
            (5, 6): _sqrt6 * self.B,
        }
        states = self.construct_matrix(diag_elements, off_diag_elements)
        return self.eigensolver(states)

    def T_1_2_states(self) -> Float64Array:
        """Calculate the T_1_2 states."""
        diag_elements = [
            -16 * self.Dq - 9 * self.B + 7 * self.C,
            -6 * self.Dq - 9 * self.B + 6 * self.C,
            -6 * self.Dq + 3 * self.B + 8 * self.C,
            +4 * self.Dq - 9 * self.B + 6 * self.C,
            +4 * self.Dq - 3 * self.B + 6 * self.C,
            +4 * self.Dq + 5 * self.B + 8 * self.C,
            +14 * self.Dq + 7 * self.C,
        ]
        off_diag_elements = {
            (0, 1): _3sqrt2 * self.B,
            (0, 2): -5 * _sqrt6 * self.B,
            (0, 3): 0.0,
            (0, 4): -_2sqrt2 * self.B,
            (0, 5): _sqrt2 * (2 * self.B + self.C),
            (0, 6): 0.0,
            (1, 2): -5 * _sqrt3 * self.B,
            (1, 3): 3 * self.B,
            (1, 4): -3 * self.B,
            (1, 5): -3 * self.B,
            (1, 6): -_sqrt6 * self.B,
            (2, 3): -3 * _sqrt3 * self.B,
            (2, 4): 5 * _sqrt3 * self.B,
            (2, 5): -5 * _sqrt3 * self.B,
            (2, 6): _sqrt2 * (3 * self.B + self.C),
            (3, 4): -6 * self.B,
            (3, 5): 0.0,
            (3, 6): -_3sqrt6 * self.B,
            (4, 5): -10 * self.B,
            (4, 6): _sqrt6 * self.B,
            (5, 6): _sqrt6 * self.B,
        }
        states = self.construct_matrix(diag_elements, off_diag_elements)
        return self.eigensolver(states)

    def A_1_1_states(self) -> Float64Array:
        """Calculate the A_1_1 states."""
        diag_elements = [
            -16 * self.Dq + 10 * self.C,
            -6 * self.Dq + 6 * self.C,
            +4 * self.Dq + 14 * self.B + 11 * self.C,
            +4 * self.Dq - 3 * self.B + 6 * self.C,
            +24 * self.Dq - 16 * self.B + 8 * self.C,
        ]
        off_diag_elements = {
            (0, 1): -12 * _sqrt2 * self.B,
            (0, 2): _sqrt2 * (4 * self.B + 2 * self.C),
            (0, 3): _2sqrt2 * self.B,
            (0, 4): 0.0,
            (1, 2): -12 * self.B,
            (1, 3): -6 * self.B,
            (1, 4): 0.0,
            (2, 3): 20 * self.B,
            (2, 4): _sqrt6 * (2 * self.B + self.C),
            (3, 4): 2 * _sqrt6 * self.B,
        }
        states = self.construct_matrix(diag_elements, off_diag_elements)
        return self.eigensolver(states)

    def E_1_1_states(self) -> Float64Array:
        """Calculate the E_1_1 states."""
        diag_elements = [
            -16 * self.Dq - 9 * self.B + 7 * self.C,
            -6 * self.Dq - 6 * self.B + 6 * self.C,
            +4 * self.Dq + 5 * self.B + 8 * self.C,
            +4 * self.Dq + 6 * self.B + 9 * self.C,
            +4 * self.Dq - 3 * self.B + 6 * self.C,
        ]
        off_diag_elements = {
            (0, 1): 6 * self.B,
            (0, 2): _sqrt2 * (2 * self.B + self.C),
            (0, 3): -2 * self.B,
            (0, 4): -4 * self.B,
            (1, 2): -_3sqrt2 * self.B,
            (1, 3): -12 * self.B,
            (1, 4): 0.0,
            (2, 3): 10 * _sqrt2 * self.B,
            (2, 4): -10 * _sqrt2 * self.B,
            (3, 4): 0.0,
        }
        states = self.construct_matrix(diag_elements, off_diag_elements)
        return self.eigensolver(states)

    def T_3_2_states(self) -> Float64Array:
        """Calculate the T_3_2 states."""
        diag_elements = [
            -6 * self.Dq - 9 * self.B + 4 * self.C,
            -6 * self.Dq - 5 * self.B + 6 * self.C,
            +4 * self.Dq - 13 * self.B + 4 * self.C,
            +4 * self.Dq - 9 * self.B + 4 * self.C,
            +14 * self.Dq - 8 * self.B + 5 * self.C,
        ]
        off_diag_elements = {
            (0, 1): -5 * _sqrt3 * self.B,
            (0, 2): _sqrt6 * self.B,
            (0, 3): _sqrt3 * self.B,
            (0, 4): -_sqrt6 * self.B,
            (1, 2): -_3sqrt2 * self.B,
            (1, 3): 3 * self.B,
            (1, 4): _sqrt2 * (3 * self.B + self.C),
            (2, 3): -2 * _sqrt2 * self.B,
            (2, 4): -6 * self.B,
            (3, 4): _3sqrt2 * self.B,
        }
        states = self.construct_matrix(diag_elements, off_diag_elements)
        return self.eigensolver(states)

    def T_1_1_states(self) -> Float64Array:
        """Calculate the T_1_1 states."""
        diag_elements = [
            -6 * self.Dq - 3 * self.B + 6 * self.C,
            -6 * self.Dq - 3 * self.B + 8 * self.C,
            +4 * self.Dq - 3 * self.B + 6 * self.C,
            +14 * self.Dq - 16 * self.B + 7 * self.C,
        ]
        off_diag_elements = {
            (0, 1): 5 * _sqrt3 * self.B,
            (0, 2): 3 * self.B,
            (0, 3): _sqrt6 * self.B,
            (1, 2): -5 * _sqrt3 * self.B,
            (1, 3): _sqrt2 * (self.B + self.C),
            (2, 3): -_sqrt6 * self.B,
        }
        states = self.construct_matrix(diag_elements, off_diag_elements)
        return self.eigensolver(states)

    def E_3_1_states(self) -> Float64Array:
        """Calculate the E_3_1 states."""
        diag_elements = [
            -6 * self.Dq - 13 * self.B + 4 * self.C,
            -6 * self.Dq - 10 * self.B + 4 * self.C,
            +4 * self.Dq - 11 * self.B + 4 * self.C,
        ]
        off_diag_elements = {
            (0, 1): -4 * self.B,
            (0, 2): 0.0,
            (1, 2): -_3sqrt2 * self.B,
        }
        states = self.construct_matrix(diag_elements, off_diag_elements)
        return self.eigensolver(states)

    def A_3_2_states(self) -> Float64Array:
        """Calculate the A_3_2 states."""
        diag_elements = [
            -6 * self.Dq - 8 * self.B + 4 * self.C,
            +4 * self.Dq - 2 * self.B + 7 * self.C,
        ]
        off_diag_elements = {(0, 1): -12 * self.B}
        states = self.construct_matrix(diag_elements, off_diag_elements)
        return self.eigensolver(states)

    def A_1_2_states(self) -> Float64Array:
        """Calculate the A_1_2 states."""
        diag_elements = [
            -6 * self.Dq - 12 * self.B + 6 * self.C,
            +4 * self.Dq - 3 * self.B + 6 * self.C,
        ]
        off_diag_elements = {(0, 1): 6 * self.B}
        states = self.construct_matrix(diag_elements, off_diag_elements)
        return self.eigensolver(states)

    def solver(self) -> dict[str, Float64Array]:
        """Solve for all states and return a dictionary of results.

        Returns:
            Dict[str, Float64Array]: Dictionary with atomic term symbols as keys and
                eigenvalues as values.

        """
        # Ligand field independent states
        GS = np.array([-6 * self.Dq - 21 * self.B])

        E_5_1 = np.array([0], dtype=np.float64)
        T_5_2 = np.array([4 * self.Dq - 21 * self.B]) - GS

        A_3_1 = np.array([-6 * self.Dq - 12 * self.B + 4 * self.C]) - GS

        # Ligand field dependent states
        T_1_2 = self.T_1_2_states() - GS
        T_3_1 = self.T_3_1_states() - GS
        A_1_1 = self.A_1_1_states() - GS
        E_1_1 = self.E_1_1_states() - GS
        T_3_2 = self.T_3_2_states() - GS
        T_1_1 = self.T_1_1_states() - GS
        E_3_1 = self.E_3_1_states() - GS
        A_3_2 = self.A_3_2_states() - GS
        A_1_2 = self.A_1_2_states() - GS

        if T_3_1[0] <= 0:
            T_1_2 -= T_3_1[0]
            A_1_1 -= T_3_1[0]
            E_1_1 -= T_3_1[0]
            T_3_2 -= T_3_1[0]
            T_1_1 -= T_3_1[0]
            E_3_1 -= T_3_1[0]
            A_3_2 -= T_3_1[0]
            A_1_2 -= T_3_1[0]
            E_5_1 -= T_3_1[0]
            T_5_2 -= T_3_1[0]
            A_3_1 -= T_3_1[0]
            T_3_1 -= T_3_1[0]

        return {
            "3_T_1": T_3_1,
            "1_T_2": T_1_2,
            "1_A_1": A_1_1,
            "1_E_1": E_1_1,
            "3_T_2": T_3_2,
            "1_T_1": T_1_1,
            "3_E_1": E_3_1,
            "3_A_2": A_3_2,
            "1_A_2": A_1_2,
            "5_E_1": E_5_1,
            "5_T_2": T_5_2,
            "3_A_1": A_3_1,
        }


class d5(LigandFieldTheory):
    """Class representing the d5 configuration in ligand field theory."""

    def __init__(self, Dq: float = 0.0, B: float = 860.0, C: float = 3850.0) -> None:
        """Initialize the d5 configuration with given parameters.

        Args:
            Dq (float): Crystal field splitting in wavenumbers (cm-1).
            B (float): Racah parameter B in wavenumbers (cm-1).
            C (float): Racah parameter C in wavenumbers (cm-1).

        """
        super().__init__(Dq, B, C)

    def T_2_2_states(self) -> Float64Array:
        """Calculate the T_2_2 states."""
        diag_elements = [
            -20 * self.Dq - 20 * self.B + 10 * self.C,
            -10 * self.Dq - 8 * self.B + 9 * self.C,
            -10 * self.Dq - 18 * self.B + 9 * self.C,
            -16 * self.B + 8 * self.C,
            -12 * self.B + 8 * self.C,
            +2 * self.B + 12 * self.C,
            -6 * self.B + 10 * self.C,
            +10 * self.Dq - 18 * self.B + 9 * self.C,
            +10 * self.Dq - 8 * self.B + 9 * self.C,
            +20 * self.Dq - 20 * self.B + 10 * self.C,
        ]
        off_diag_elements = {
            (0, 1): _3sqrt6 * self.B,
            (0, 2): _sqrt6 * self.B,
            (0, 3): 0.0,
            (0, 4): -2 * _sqrt3 * self.B,
            (0, 5): 4 * self.B + 2 * self.C,
            (0, 6): 2 * self.B,
            (0, 7): 0.0,
            (0, 8): 0.0,
            (0, 9): 0.0,
            (1, 2): 3 * self.B,
            (1, 3): _sqrt6 / 2.0 * self.B,
            (1, 4): -_3sqrt2 / 2.0 * self.B,
            (1, 5): _3sqrt6 / 2.0 * self.B,
            (1, 6): _3sqrt6 / 2.0 * self.B,
            (1, 7): 0.0,
            (1, 8): 4 * self.B + self.C,
            (1, 9): 0.0,
            (2, 3): _3sqrt6 / 2.0 * self.B,
            (2, 4): -_3sqrt2 / 2.0 * self.B,
            (2, 5): +5 * _sqrt6 / 2.0 * self.B,
            (2, 6): -5 * _sqrt6 / 2.0 * self.B,
            (2, 7): self.C,
            (2, 8): 0.0,
            (2, 9): 0.0,
            (3, 4): 2 * _sqrt3 * self.B,
            (3, 5): 0.0,
            (3, 6): 0.0,
            (3, 7): -_3sqrt6 / 2.0 * self.B,
            (3, 8): -_sqrt6 / 2.0 * self.B,
            (3, 9): 0.0,
            (4, 5): -10 * _sqrt3 * self.B,
            (4, 6): 0.0,
            (4, 7): _3sqrt2 / 2.0 * self.B,
            (4, 8): _3sqrt2 / 2.0 * self.B,
            (4, 9): -2 * _sqrt3 * self.B,
            (5, 6): 0.0,
            (5, 7): -5 * _sqrt6 / 2.0 * self.B,
            (5, 8): -_3sqrt6 / 2.0 * self.B,
            (5, 9): 4 * self.B + 2 * self.C,
            (6, 7): -5 * _sqrt6 / 2.0 * self.B,
            (6, 8): _3sqrt6 / 2.0 * self.B,
            (6, 9): -2.0 * self.B,
            (7, 8): 3 * self.B,
            (7, 9): -_sqrt6 * self.B,
            (8, 9): -_3sqrt6 * self.B,
        }
        states = self.construct_matrix(diag_elements, off_diag_elements)
        return self.eigensolver(states)

    def T_2_1_states(self) -> Float64Array:
        """Calculate the T_2_1 states."""
        diag_elements = [
            -10 * self.Dq - 22 * self.B + 9 * self.C,
            -10 * self.Dq - 8 * self.B + 9 * self.C,
            -4 * self.B + 10 * self.C,
            -12 * self.B + 8 * self.C,
            -10 * self.B + 10 * self.C,
            -6 * self.B + 10 * self.C,
            +10 * self.Dq - 8 * self.B + 9 * self.C,
            +10 * self.Dq - 22 * self.B + 9 * self.C,
        ]
        off_diag_elements = {
            (0, 1): -3 * self.B,
            (0, 2): -_3sqrt2 / 2.0 * self.B,
            (0, 3): _3sqrt2 / 2.0 * self.B,
            (0, 4): -_3sqrt2 / 2.0 * self.B,
            (0, 5): -_3sqrt6 / 2.0 * self.B,
            (0, 6): 0.0,
            (0, 7): self.C,
            (1, 2): _3sqrt2 / 2.0 * self.B,
            (1, 3): _3sqrt2 / 2.0 * self.B,
            (1, 4): 15 * _sqrt2 / 2.0 * self.B,
            (1, 5): 5 * _sqrt6 / 2.0 * self.B,
            (1, 6): 4 * self.B + self.C,
            (1, 7): 0.0,
            (2, 3): 0.0,
            (2, 4): 0.0,
            (2, 5): 10 * _sqrt3 * self.B,
            (2, 6): _3sqrt2 / 2.0 * self.B,
            (2, 7): -_3sqrt2 / 2.0 * self.B,
            (3, 4): 0.0,
            (3, 5): 0.0,
            (3, 6): -_3sqrt2 / 2.0 * self.B,
            (3, 7): -_3sqrt2 / 2.0 * self.B,
            (4, 5): 2 * _sqrt3 * self.B,
            (4, 6): 15 * _sqrt2 / 2.0 * self.B,
            (4, 7): -_3sqrt2 / 2.0 * self.B,
            (5, 6): 5 * _sqrt6 / 2.0 * self.B,
            (5, 7): -_3sqrt6 / 2.0 * self.B,
            (6, 7): -3 * self.B,
        }
        states = self.construct_matrix(diag_elements, off_diag_elements)
        return self.eigensolver(states)

    def E_2_states(self) -> Float64Array:
        """Calculate the E_2 states."""
        diag_elements = [
            -10 * self.Dq - 4 * self.B + 12 * self.C,
            -10 * self.Dq - 13 * self.B + 9 * self.C,
            -4 * self.B + 10 * self.C,
            -16 * self.B + 8 * self.C,
            -12 * self.B + 8 * self.C,
            +10 * self.Dq - 13 * self.B + 9 * self.C,
            +10 * self.Dq - 4 * self.B + 12 * self.C,
        ]
        off_diag_elements = {
            (0, 1): 10 * self.B,
            (0, 2): 6 * self.B,
            (0, 3): 6 * _sqrt3 * self.B,
            (0, 4): 6 * _sqrt2 * self.B,
            (0, 5): -2 * self.B,
            (0, 6): 4 * self.B + 2 * self.C,
            (1, 2): -3 * self.B,
            (1, 3): 3 * _sqrt3 * self.B,
            (1, 4): 0.0,
            (1, 5): 2 * self.B + self.C,
            (1, 6): 2 * self.B,
            (2, 3): 0.0,
            (2, 4): 0.0,
            (2, 5): -3 * self.B,
            (2, 6): -6 * self.B,
            (3, 4): 2 * _sqrt6 * self.B,
            (3, 5): -3 * _sqrt3 * self.B,
            (3, 6): 6 * _sqrt3 * self.B,
            (4, 5): 0.0,
            (4, 6): 6 * _sqrt2 * self.B,
            (5, 6): -10 * self.B,
        }
        states = self.construct_matrix(diag_elements, off_diag_elements)
        return self.eigensolver(states)

    def A_2_1_states(self) -> Float64Array:
        """Calculate the A_2_1 states."""
        diag_elements = [
            -10 * self.Dq - 3 * self.B + 9 * self.C,
            -12 * self.B + 8 * self.C,
            -19 * self.B + 8 * self.C,
            +10 * self.Dq - 3 * self.B + 9 * self.C,
        ]
        off_diag_elements = {
            (0, 1): -_3sqrt2 * self.B,
            (0, 2): 0.0,
            (0, 3): 6 * self.B + self.C,
            (1, 2): -4 * _sqrt3 * self.B,
            (1, 3): _3sqrt2 * self.B,
            (2, 3): 0.0,
        }
        states = self.construct_matrix(diag_elements, off_diag_elements)
        return self.eigensolver(states)

    def A_2_2_states(self) -> Float64Array:
        """Calculate the A_2_2 states."""
        diag_elements = [
            -10 * self.Dq - 23 * self.B + 9 * self.C,
            -12 * self.B + 8 * self.C,
            +10 * self.Dq - 23 * self.B + 9 * self.C,
        ]
        off_diag_elements = {
            (0, 1): _3sqrt2 * self.B,
            (0, 2): -2 * self.B + self.C,
            (1, 2): -_3sqrt2 * self.B,
        }
        states = self.construct_matrix(diag_elements, off_diag_elements)
        return self.eigensolver(states)

    def T_4_1_states(self) -> Float64Array:
        """Calculate the T_4_1 states."""
        diag_elements = [
            -10 * self.Dq - 25 * self.B + 6 * self.C,
            -16 * self.B + 7 * self.C,
            10 * self.Dq - 25 * self.B + 6 * self.C,
        ]
        off_diag_elements = {
            (0, 1): -_3sqrt2 * self.B,
            (0, 2): self.C,
            (1, 2): -_3sqrt2 * self.B,
        }
        states = self.construct_matrix(diag_elements, off_diag_elements)
        return self.eigensolver(states)

    def T_4_2_states(self) -> Float64Array:
        """Calculate the T_4_2 states."""
        diag_elements = [
            -10 * self.Dq - 17 * self.B + 6 * self.C,
            -22 * self.B + 5 * self.C,
            +10 * self.Dq - 17 * self.B + 6 * self.C,
        ]
        off_diag_elements = {
            (0, 1): _sqrt6 * self.B,
            (0, 2): +4 * self.B + self.C,
            (1, 2): -_sqrt6 * self.B,
        }
        states = self.construct_matrix(diag_elements, off_diag_elements)
        return self.eigensolver(states)

    def E_4_states(self) -> Float64Array:
        """Calculate the E_4 states."""
        diag_elements = [-22 * self.B + 5 * self.C, -21 * self.B + 5 * self.C]
        off_diag_elements = {(0, 1): -2 * _sqrt3 * self.B}
        states = self.construct_matrix(diag_elements, off_diag_elements)
        return self.eigensolver(states)

    def solver(self) -> dict[str, Float64Array]:
        """Solve for all states and return a dictionary of results.

        Returns:
            Dict[str, Float64Array]: Dictionary with atomic term symbols as keys and
                eigenvalues as values.

        """
        # Ligand field independent states
        GS = -35 * self.B

        A_6_1 = np.array(
            [0.0],
            dtype=float,
        )  # Starting value is -35. * B, but has to set to zero per definition
        E_4 = self.E_4_states() - GS
        A_4_1 = np.array([-25 * self.B + 5 * self.C]) - GS
        A_4_2 = np.array([-13 * self.B + 7 * self.C]) - GS

        # Ligandfield dependent
        T_2_2 = self.T_2_2_states() - GS
        T_2_1 = self.T_2_1_states() - GS
        E_2 = self.E_2_states() - GS
        A_2_1 = self.A_2_1_states() - GS
        A_2_2 = self.A_2_2_states() - GS
        T_4_1 = self.T_4_1_states() - GS
        T_4_2 = self.T_4_2_states() - GS

        if T_2_2[0] <= 0:
            A_6_1 -= T_2_2[0]
            E_4 -= T_2_2[0]
            A_4_1 -= T_2_2[0]
            A_4_2 -= T_2_2[0]
            T_2_1 -= T_2_2[0]
            E_2 -= T_2_2[0]
            A_2_1 -= T_2_2[0]
            A_2_2 -= T_2_2[0]
            T_4_1 -= T_2_2[0]
            T_4_2 -= T_2_2[0]
            # Finally create new ligand field independent state
            T_2_2 -= T_2_2[0]

        return {
            "2_T_2": T_2_2,
            "2_T_1": T_2_1,
            "2_E": E_2,
            "2_A_1": A_2_1,
            "2_A_2": A_2_2,
            "4_T_1": T_4_1,
            "4_T_2": T_4_2,
            "4_E": E_4,
            "6_A_1": A_6_1,
            "4_A_1": A_4_1,
            "4_A_2": A_4_2,
        }


class d6(LigandFieldTheory):
    """Class representing the d6 configuration in ligand field theory."""

    def __init__(self, Dq: float = 0.0, B: float = 1065.0, C: float = 5120.0) -> None:
        """Initialize the d6 configuration with given parameters.

        Args:
            Dq (float): Crystal field splitting in wavenumbers (cm-1).
            B (float): Racah parameter B in wavenumbers (cm-1).
            C (float): Racah parameter C in wavenumbers (cm-1).

        """
        super().__init__(Dq, B, C)

    def T_3_1_states(self) -> Float64Array:
        """Calculate the T_3_1 states."""
        diag_elements = [
            +16 * self.Dq - 15 * self.B + 5 * self.C,
            +6 * self.Dq - 11 * self.B + 4 * self.C,
            +6 * self.Dq - 3 * self.B + 6 * self.C,
            -4 * self.Dq - self.B + 6 * self.C,
            -4 * self.Dq - 9 * self.B + 4 * self.C,
            -4 * self.Dq - 11 * self.B + 4 * self.C,
            -14 * self.Dq - 16 * self.B + 5 * self.C,
        ]
        off_diag_elements = {
            (0, 1): -_sqrt6 * self.B,
            (0, 2): -_3sqrt2 * self.B,
            (0, 3): _sqrt2 * (2 * self.B + self.C),
            (0, 4): -_2sqrt2 * self.B,
            (0, 5): 0.0,
            (0, 6): 0.0,
            (1, 2): 5 * _sqrt3 * self.B,
            (1, 3): _sqrt3 * self.B,
            (1, 4): -_sqrt3 * self.B,
            (1, 5): 3 * self.B,
            (1, 6): _sqrt6 * self.B,
            (2, 3): -3 * self.B,
            (2, 4): -3 * self.B,
            (2, 5): 5 * _sqrt3 * self.B,
            (2, 6): _sqrt2 * (self.B + self.C),
            (3, 4): -10 * self.B,
            (3, 5): 0.0,
            (3, 6): _3sqrt2 * self.B,
            (4, 5): -2 * _sqrt3 * self.B,
            (4, 6): -_3sqrt2 * self.B,
            (5, 6): _sqrt6 * self.B,
        }
        states = self.construct_matrix(diag_elements, off_diag_elements)
        return self.eigensolver(states)

    def T_1_2_states(self) -> Float64Array:
        """Calculate the T_1_2 states."""
        diag_elements = [
            +16 * self.Dq - 9 * self.B + 7 * self.C,
            +6 * self.Dq - 9 * self.B + 6 * self.C,
            +6 * self.Dq + 3 * self.B + 8 * self.C,
            -4 * self.Dq - 9 * self.B + 6 * self.C,
            -4 * self.Dq - 3 * self.B + 6 * self.C,
            -4 * self.Dq + 5 * self.B + 8 * self.C,
            -14 * self.Dq + 7 * self.C,
        ]
        off_diag_elements = {
            (0, 1): _3sqrt2 * self.B,
            (0, 2): -5 * _sqrt6 * self.B,
            (0, 3): 0.0,
            (0, 4): -_2sqrt2 * self.B,
            (0, 5): _sqrt2 * (2 * self.B + self.C),
            (0, 6): 0.0,
            (1, 2): -5 * _sqrt3 * self.B,
            (1, 3): 3 * self.B,
            (1, 4): -3 * self.B,
            (1, 5): -3 * self.B,
            (1, 6): -_sqrt6 * self.B,
            (2, 3): -3 * _sqrt3 * self.B,
            (2, 4): 5 * _sqrt3 * self.B,
            (2, 5): -5 * _sqrt3 * self.B,
            (2, 6): _sqrt2 * (3 * self.B + self.C),
            (3, 4): -6 * self.B,
            (3, 5): 0.0,
            (3, 6): -_3sqrt6 * self.B,
            (4, 5): -10 * self.B,
            (4, 6): _sqrt6 * self.B,
            (5, 6): _sqrt6 * self.B,
        }
        states = self.construct_matrix(diag_elements, off_diag_elements)
        return self.eigensolver(states)

    def A_1_1_states(self) -> Float64Array:
        """Calculate the A_1_1 states."""
        diag_elements = [
            +16 * self.Dq + 10 * self.C,
            +6 * self.Dq + 6 * self.C,
            -4 * self.Dq + 14 * self.B + 11 * self.C,
            -4 * self.Dq - 3 * self.B + 6 * self.C,
            -24 * self.Dq - 16 * self.B + 8 * self.C,
        ]
        off_diag_elements = {
            (0, 1): -12 * _sqrt2 * self.B,
            (0, 2): _sqrt2 * (4 * self.B + 2 * self.C),
            (0, 3): _2sqrt2 * self.B,
            (0, 4): 0.0,
            (1, 2): -12 * self.B,
            (1, 3): -6 * self.B,
            (1, 4): 0.0,
            (2, 3): 20 * self.B,
            (2, 4): _sqrt6 * (2 * self.B + self.C),
            (3, 4): 2 * _sqrt6 * self.B,
        }
        states = self.construct_matrix(diag_elements, off_diag_elements)
        return self.eigensolver(states)

    def E_1_1_states(self) -> Float64Array:
        """Calculate the E_1_1 states."""
        diag_elements = [
            +16 * self.Dq - 9 * self.B + 7 * self.C,
            +6 * self.Dq - 6 * self.B + 6 * self.C,
            -4 * self.Dq + 5 * self.B + 8 * self.C,
            -4 * self.Dq + 6 * self.B + 9 * self.C,
            -4 * self.Dq - 3 * self.B + 6 * self.C,
        ]
        off_diag_elements = {
            (0, 1): 6 * self.B,
            (0, 2): _sqrt2 * (2 * self.B + self.C),
            (0, 3): -2 * self.B,
            (0, 4): -4 * self.B,
            (1, 2): -_3sqrt2 * self.B,
            (1, 3): -12 * self.B,
            (1, 4): 0.0,
            (2, 3): 10 * _sqrt2 * self.B,
            (2, 4): -10 * _sqrt2 * self.B,
            (3, 4): 0.0,
        }
        states = self.construct_matrix(diag_elements, off_diag_elements)
        return self.eigensolver(states)

    def T_3_2_states(self) -> Float64Array:
        """Calculate the T_3_2 states."""
        diag_elements = [
            +6 * self.Dq - 9 * self.B + 4 * self.C,
            +6 * self.Dq - 5 * self.B + 6 * self.C,
            -4 * self.Dq - 13 * self.B + 4 * self.C,
            -4 * self.Dq - 9 * self.B + 4 * self.C,
            -14 * self.Dq - 8 * self.B + 5 * self.C,
        ]
        off_diag_elements = {
            (0, 1): -5 * _sqrt3 * self.B,
            (0, 2): _sqrt6 * self.B,
            (0, 3): _sqrt3 * self.B,
            (0, 4): -_sqrt6 * self.B,
            (1, 2): -_3sqrt2 * self.B,
            (1, 3): 3 * self.B,
            (1, 4): _sqrt2 * (3 * self.B + self.C),
            (2, 3): -2 * _sqrt2 * self.B,
            (2, 4): -6 * self.B,
            (3, 4): 3 * _sqrt2 * self.B,
        }
        states = self.construct_matrix(diag_elements, off_diag_elements)
        return self.eigensolver(states)

    def T_1_1_states(self) -> Float64Array:
        """Calculate the T_1_1 states."""
        diag_elements = [
            +6 * self.Dq - 3 * self.B + 6 * self.C,
            +6 * self.Dq - 3 * self.B + 8 * self.C,
            -4 * self.Dq - 3 * self.B + 6 * self.C,
            -14 * self.Dq - 16 * self.B + 7 * self.C,
        ]
        off_diag_elements = {
            (0, 1): 5 * _sqrt3 * self.B,
            (0, 2): 3 * self.B,
            (0, 3): _sqrt6 * self.B,
            (1, 2): -5 * _sqrt3 * self.B,
            (1, 3): _sqrt2 * (self.B + self.C),
            (2, 3): -_sqrt6 * self.B,
        }
        states = self.construct_matrix(diag_elements, off_diag_elements)
        return self.eigensolver(states)

    def E_3_1_states(self) -> Float64Array:
        """Calculate the E_3_1 states."""
        diag_elements = [
            +6 * self.Dq - 13 * self.B + 4 * self.C,
            +6 * self.Dq - 10 * self.B + 4 * self.C,
            -4 * self.Dq - 11 * self.B + 4 * self.C,
        ]
        off_diag_elements = {
            (0, 1): -4 * self.B,
            (0, 2): 0.0,
            (1, 2): -_3sqrt2 * self.B,
        }
        states = self.construct_matrix(diag_elements, off_diag_elements)
        return self.eigensolver(states)

    def A_3_2_states(self) -> Float64Array:
        """Calculate the A_3_2 states."""
        diag_elements = [
            +6 * self.Dq - 8 * self.B + 4 * self.C,
            -4 * self.Dq - 2 * self.B + 7 * self.C,
        ]
        off_diag_elements = {(0, 1): -12 * self.B}
        states = self.construct_matrix(diag_elements, off_diag_elements)
        return self.eigensolver(states)

    def A_1_2_states(self) -> Float64Array:
        """Calculate the A_1_2 states."""
        diag_elements = [
            +6 * self.Dq - 12 * self.B + 6 * self.C,
            -4 * self.Dq - 3 * self.B + 6 * self.C,
        ]
        off_diag_elements = {(0, 1): 6 * self.B}
        states = self.construct_matrix(diag_elements, off_diag_elements)
        return self.eigensolver(states)

    def solver(self) -> dict[str, Float64Array]:
        """Solve for all states and return a dictionary of results.

        Returns:
            Dict[str, Float64Array]: Dictionary with atomic term symbols as keys and
                eigenvalues as values.

        """
        GS = np.array([-4 * self.Dq - 21 * self.B])

        T_5_2 = np.array([0], dtype=np.float64)

        E_5_1 = np.array([6 * self.Dq - 21 * self.B]) - GS

        A_3_1 = np.array([6 * self.Dq - 12 * self.B + 4 * self.C]) - GS

        # Ligandfield dependent
        T_1_2 = -GS + self.T_1_2_states()
        T_3_1 = -GS + self.T_3_1_states()
        A_1_1 = -GS + self.A_1_1_states()
        E_1_1 = -GS + self.E_1_1_states()
        T_3_2 = -GS + self.T_3_2_states()
        T_1_1 = -GS + self.T_1_1_states()
        E_3_1 = -GS + self.E_3_1_states()
        A_3_2 = -GS + self.A_3_2_states()
        A_1_2 = -GS + self.A_1_2_states()

        if A_1_1[0] <= ENERGY_TOLERANCE:
            T_1_2 -= A_1_1[0]

            E_1_1 -= A_1_1[0]
            T_3_2 -= A_1_1[0]
            T_1_1 -= A_1_1[0]
            E_3_1 -= A_1_1[0]
            A_3_2 -= A_1_1[0]
            A_1_2 -= A_1_1[0]
            T_3_1 -= A_1_1[0]

            E_5_1 -= A_1_1[0]
            T_5_2 -= A_1_1[0]
            A_3_1 -= A_1_1[0]
            A_1_1 -= A_1_1[0]

        return {
            "3_T_1": T_3_1,
            "1_T_2": T_1_2,
            "1_A_1": A_1_1,
            "1_E_1": E_1_1,
            "3_T_2": T_3_2,
            "1_T_1": T_1_1,
            "3_E_1": E_3_1,
            "3_A_2": A_3_2,
            "1_A_2": A_1_2,
            "5_E_1": E_5_1,
            "5_T_2": T_5_2,
            "3_A_1": A_3_1,
        }


class d7(LigandFieldTheory):
    """Class for d7 configuration."""

    def __init__(self, Dq: float = 0.0, B: float = 971.0, C: float = 4499.0) -> None:
        """Initialize the d7 configuration with given parameters.

        Args:
            Dq (float): Crystal field splitting in wavenumbers (cm-1).
            B (float): Racah parameter B in wavenumbers (cm-1).
            C (float): Racah parameter C in wavenumbers (cm-1).

        """
        super().__init__(Dq, B, C)

    def T_2_2_states(self) -> Float64Array:
        """Calculate the T_2_2 states."""
        diag_elements = [
            +12 * self.Dq + 5 * self.C,
            +2 * self.Dq - 6 * self.B + 3 * self.C,
            +2 * self.Dq + 4 * self.B + 3 * self.C,
            -8 * self.Dq + 6 * self.B + 5 * self.C,
            -8 * self.Dq - 2 * self.B + 3 * self.C,
        ]
        off_diag_elements = {
            (0, 1): -_3sqrt3 * self.B,
            (0, 2): -5 * _sqrt3 * self.B,
            (0, 3): 4 * self.B + 2 * self.C,
            (0, 4): 2 * self.B,
            (1, 2): 3 * self.B,
            (1, 3): -_3sqrt3 * self.B,
            (1, 4): -_3sqrt3 * self.B,
            (2, 3): -_sqrt3 * self.B,
            (2, 4): +_sqrt3 * self.B,
            (3, 4): 10 * self.B,
        }
        states = self.construct_matrix(diag_elements, off_diag_elements)
        return self.eigensolver(states)

    def T_2_1_states(self) -> Float64Array:
        """Calculate the T_2_1 states."""
        diag_elements = [
            +12 * self.Dq - 6 * self.B + 3 * self.C,
            +2 * self.Dq + 3 * self.C,
            +2 * self.Dq - 6 * self.B + 3 * self.C,
            -8 * self.Dq - 6 * self.B + 3 * self.C,
            -8 * self.Dq - 2 * self.B + 3 * self.C,
        ]
        off_diag_elements = {
            (0, 1): -3 * self.B,
            (0, 2): +3 * self.B,
            (0, 3): 0.0,
            (0, 4): -_2sqrt3 * self.B,
            (1, 2): -3 * self.B,
            (1, 3): +3 * self.B,
            (1, 4): _3sqrt3 * self.B,
            (2, 3): -3 * self.B,
            (2, 4): -_sqrt3 * self.B,
            (3, 4): _2sqrt3 * self.B,
        }
        states = self.construct_matrix(diag_elements, off_diag_elements)
        return self.eigensolver(states)

    def E_2_states(self) -> Float64Array:
        """Calculate the E_2 states."""
        diag_elements = [
            +12 * self.Dq - 6 * self.B + 3 * self.C,
            +2 * self.Dq + 8 * self.B + 6 * self.C,
            +2 * self.Dq - 1 * self.B + 3 * self.C,
            -18 * self.Dq - 8 * self.B + 4 * self.C,
        ]
        off_diag_elements = {
            (0, 1): -6 * _sqrt2 * self.B,
            (0, 2): -_3sqrt2 * self.B,
            (0, 3): 0.0,
            (1, 2): 10 * self.B,
            (1, 3): +_sqrt3 * (2 * self.B + self.C),
            (2, 3): _2sqrt3 * self.B,
        }
        states = self.construct_matrix(diag_elements, off_diag_elements)
        return self.eigensolver(states)

    def T_4_1_states(self) -> Float64Array:
        """Calculate the T_4_1 states."""
        diag_elements = [+2 * self.Dq - 3 * self.B, -8 * self.Dq - 12 * self.B]
        off_diag_elements = {(0, 1): 6 * self.B}
        states = self.construct_matrix(diag_elements, off_diag_elements)
        return self.eigensolver(states)

    def solver(self) -> dict[str, np.ndarray]:
        """Solve for all states and return a dictionary of results.

        Returns:
            Dict[str, np.ndarray]: Dictionary with atomic term symbols as keys and
                eigenvalues as values.

        """
        # Ligand field independent states

        # Ligandfield multi dependent state become GS

        T_4_1 = self.T_4_1_states()

        # Ligendfield single dependent states

        GS = T_4_1[0]

        T_4_1[0] = np.array([0.0], dtype=float)
        A_4_2 = np.array([12 * self.Dq - 15 * self.B]) - GS
        T_4_2 = np.array([2 * self.Dq - 15 * self.B]) - GS

        A_2_1 = np.array([2 * self.Dq - 11 * self.B + 3 * self.C]) - GS
        A_2_2 = np.array([2 * self.Dq + 9 * self.B + 3 * self.C]) - GS

        # Ligandfield dependent
        T_2_2 = self.T_2_2_states() - GS
        T_2_1 = self.T_2_1_states() - GS
        E_2 = self.E_2_states() - GS
        T_4_1[1] -= GS

        if E_2[0] <= 0:
            A_4_2 -= E_2[0]
            T_4_2 -= E_2[0]
            A_2_1 -= E_2[0]
            A_2_2 -= E_2[0]
            T_2_2 -= E_2[0]
            T_2_1 -= E_2[0]
            T_4_1 -= E_2[0]
            E_2 -= E_2[0]

        return {
            "2_T_2": T_2_2,
            "2_T_1": T_2_1,
            "2_E": E_2,
            "4_T_1": T_4_1,
            "4_A_2": A_4_2,
            "4_T_2": T_4_2,
            "2_A_1": A_2_1,
            "2_A_2": A_2_2,
        }


class d8(LigandFieldTheory):
    """Class for d8 configuration."""

    def __init__(self, Dq: float = 0.0, B: float = 1030.0, C: float = 4850.0) -> None:
        """Initialize the d8 configuration with given parameters.

        Args:
            Dq (float): Crystal field splitting in wavenumbers (cm-1).
            B (float): Racah parameter B in wavenumbers (cm-1).
            C (float): Racah parameter C in wavenumbers (cm-1).

        """
        super().__init__(Dq, B, C)

    def A_1_1_states(self) -> Float64Array:
        """Calculate the A_1_1 states."""
        diag_elements = [
            +8 * self.Dq + 10 * self.B + 5 * self.C,
            -12 * self.Dq + 8 * self.B + 4 * self.C,
        ]
        off_diag_elements = {(0, 1): _sqrt6 * (2 * self.B + self.C)}
        states = self.construct_matrix(diag_elements, off_diag_elements)
        return self.eigensolver(states)

    def E_1_states(self) -> Float64Array:
        """Calculate the E_1 states."""
        diag_elements = [+8 * self.Dq + self.B + 2 * self.C, -12 * self.Dq + 2 * self.C]
        off_diag_elements = {(0, 1): -_2sqrt3 * self.B}
        states = self.construct_matrix(diag_elements, off_diag_elements)
        return self.eigensolver(states)

    def T_1_2_states(self) -> Float64Array:
        """Calculate the T_1_2 states."""
        diag_elements = [+8 * self.Dq + self.B + 2 * self.C, -2 * self.Dq + 2 * self.C]
        off_diag_elements = {(0, 1): +_2sqrt3 * self.B}
        states = self.construct_matrix(diag_elements, off_diag_elements)
        return self.eigensolver(states)

    def T_3_1_states(self) -> Float64Array:
        """Calculate the T_3_1 states."""
        diag_elements = [+8 * self.Dq - 5 * self.B, -2 * self.Dq + 4 * self.B]
        off_diag_elements = {(0, 1): 6 * self.B}
        states = self.construct_matrix(diag_elements, off_diag_elements)
        return self.eigensolver(states)

    def solver(self) -> dict[str, Float64Array]:
        """Solve for all states and return a dictionary of results.

        Returns:
            Dict[str, Float64Array]: Dictionary with atomic term symbols as keys and
                eigenvalues as values.

        """
        # Ligand field independent states

        # Ligendfield single depentent states

        GS = np.array([-12 * self.Dq - 8 * self.B])

        T_1_1 = np.array([-2 * self.Dq + 4 * self.B + 2 * self.C]) - GS
        T_3_2 = np.array([-2 * self.Dq - 8 * self.B]) - GS
        A_3_2 = np.array([0], dtype=float)
        # Ligandfield dependent
        A_1_1 = self.A_1_1_states() - GS
        E_1 = self.E_1_states() - GS
        T_1_2 = self.T_1_2_states() - GS
        T_3_1 = self.T_3_1_states() - GS

        return {
            "1_A_1": A_1_1,
            "1_E": E_1,
            "1_T_3": T_1_2,
            "3_T_1": T_3_1,
            "1_T_1": T_1_1,
            "3_T_2": T_3_2,
            "3_A_2": A_3_2,
        }
