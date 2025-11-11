"""Tests for matrix calculation module."""

from __future__ import annotations

import numpy as np
import pytest

from tanabesugano.matrices import LigandFieldTheory


# Define a type alias for clarity
Float64Array = np.ndarray


@pytest.fixture
def ligand_field_theory():
    # Arrange
    # Create a fixture for the LigandFieldTheory instance
    return LigandFieldTheory(Dq=1000.0, B=800.0, C=4000.0)


@pytest.mark.parametrize(
    "matrix, expected_eigenvalues",
    [
        (
            np.array([[1, 0], [0, 1]], dtype=np.float64),
            np.array([1, 1], dtype=np.float64),
        ),
        (
            np.array([[2, 1], [1, 2]], dtype=np.float64),
            np.array([1, 3], dtype=np.float64),
        ),
        (
            np.array([[0, 0], [0, 0]], dtype=np.float64),
            np.array([0, 0], dtype=np.float64),
        ),
    ],
    ids=["identity_matrix", "symmetric_matrix", "zero_matrix"],
)
def test_eigensolver(ligand_field_theory, matrix, expected_eigenvalues):
    # Act
    eigenvalues = ligand_field_theory.eigensolver(matrix)

    # Assert
    np.testing.assert_array_almost_equal(eigenvalues, expected_eigenvalues)


@pytest.mark.parametrize(
    "diag_elements, off_diag_elements, expected_matrix",
    [
        ([1, 2], {(0, 1): 0.5}, np.array([[1, 0.5], [0.5, 2]], dtype=np.float64)),
        (
            [3, 4, 5],
            {(0, 2): 1.0, (1, 2): 0.5},
            np.array([[3, 0, 1], [0, 4, 0.5], [1, 0.5, 5]], dtype=np.float64),
        ),
        ([0, 0], {}, np.array([[0, 0], [0, 0]], dtype=np.float64)),
    ],
    ids=["simple_2x2", "complex_3x3", "zero_2x2"],
)
def test_construct_matrix(
    ligand_field_theory,
    diag_elements,
    off_diag_elements,
    expected_matrix,
):
    # Act
    matrix = ligand_field_theory.construct_matrix(diag_elements, off_diag_elements)

    # Assert
    np.testing.assert_array_almost_equal(matrix, expected_matrix)


def test_solver_not_implemented(ligand_field_theory):
    # Act & Assert
    with pytest.raises(
        NotImplementedError,
        match=r"Subclasses should implement this method\.",
    ):
        ligand_field_theory.solver()


@pytest.mark.parametrize(
    "matrix",
    [
        np.array([[1, 2], [3, 4]], dtype=np.float64),  # Non-symmetric matrix
        np.array([[1, 2, 3], [4, 5, 6]], dtype=np.float64),  # Non-square matrix
    ],
    ids=["non_symmetric_matrix", "non_square_matrix"],
)
@pytest.mark.xfail(reason="Functionality not implemented yet")
def test_eigensolver_invalid_input(ligand_field_theory, matrix):
    # Act & Assert
    with pytest.raises(ValueError, match="Input matrix must be"):
        ligand_field_theory.eigensolver(matrix)
