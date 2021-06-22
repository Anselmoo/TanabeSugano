import numpy as np

from tanabesugano import tools, ts

from typing import List


class CMDmain(object):
    def __init__(
        self,
        Dq: List[float] = [4000.0, 4500.0, 100],
        B: List[float] = [400.0, 4500.0, 100],
        C: List[float] = [3600.0, 4000, 100],
        mode: int = 5,
        slater: bool = False,
    ):
        if len(Dq) != 3:
            raise KeyError(
                "The range of `Dq` is based on the three values: start, stop, steps!"
            )
        else:
            self.Dq = np.linspace(Dq[0], Dq[1], int(Dq[2]))  # Oh-crystalfield-splitting
        if len(B) != 3:
            raise KeyError(
                "The range of `B` is based on the three values: start, stop, steps!"
            )
        else:
            self.B = np.linspace(
                B[0], B[1], int(B[2])
            )  # Racah-Parameter B in wavenumbers
        if len(C) != 3:
            raise KeyError(
                "The range of `C` is based on the three values: start, stop, steps!"
            )
        else:
            self.C = np.linspace(
                C[0], C[1], int(C[2])
            )  # Racah-Parameter C in wavenumbers

        if slater:
            # Transformin Racah to Slater-Condon
            self.B, self.C = tools.racah(B, C)

        # self.delta_B = self.e_range / self.B

        self.spin_state = int(mode)
        if self.spin_state in {4, 5, 6}:
            self._size = 42
        if self.spin_state in {3, 7}:
            self._size = 19
        if self.spin_state in {2, 8}:
            self._size = 10
        # self.result = np.zeros((self._size + 1, nroots))
