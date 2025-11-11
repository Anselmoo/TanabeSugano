from __future__ import annotations

import numpy as np

from tanabesugano import matrices
from tanabesugano import tools


class Batch:
    def __init__(
        self,
        Dq: list[float] | None = None,
        B: list[float] | None = None,
        C: list[float] | None = None,
        d_count: int = 5,
        slater: bool = False,
    ) -> None:
        if Dq is None:
            Dq = [4000.0, 4500.0, 10]
        if B is None:
            B = [400.0, 4500.0, 10]
        if C is None:
            C = [3600.0, 4000, 10]
        if len(Dq) != 3:
            msg = "The range of `Dq` is based on the three values: start, stop, steps!"
            raise KeyError(msg)
        self.Dq = np.linspace(Dq[0], Dq[1], int(Dq[2]))  # Oh-crystalfield-splitting
        if len(B) != 3:
            msg = "The range of `B` is based on the three values: start, stop, steps!"
            raise KeyError(msg)
        self.B = np.linspace(B[0], B[1], int(B[2]))  # Racah-B-parameter
        if len(C) != 3:
            msg = "The range of `C` is based on the three values: start, stop, steps!"
            raise KeyError(msg)
        self.C = np.linspace(C[0], C[1], int(C[2]))  # Racah-C-parameter

        if slater:
            # Transformin Racah to Slater-Condon
            self.B, self.C = tools.racah(B, C)

        # self.delta_B = self.e_range / self.B

        self.d_count = d_count
        if self.d_count in {4, 5, 6}:
            self._size = 42
        if self.d_count in {3, 7}:
            self._size = 19
        if self.d_count in {2, 8}:
            self._size = 10
        self.result: list[dict] = []

    def calculation(self) -> None:
        """Is filling the self.result with the iTS states of over-iterated energy range."""
        for _Dq in self.Dq:
            for _B in self.B:
                for _C in self.C:
                    if self.d_count == 2:  # d2
                        states = matrices.d2(Dq=_Dq, B=_B, C=_C).solver()
                        self.result.append(
                            {
                                "d_count": self.d_count,
                                "Dq": _Dq,
                                "B": _B,
                                "C": _C,
                                "states": states,
                            },
                        )

                    elif self.d_count == 3:  # d3
                        states = matrices.d3(Dq=_Dq, B=_B, C=_C).solver()
                        self.result.append(
                            {
                                "d_count": self.d_count,
                                "Dq": _Dq,
                                "B": _B,
                                "C": _C,
                                "states": states,
                            },
                        )
                    elif self.d_count == 4:  # d4
                        states = matrices.d4(Dq=_Dq, B=_B, C=_C).solver()
                        self.result.append(
                            {
                                "d_count": self.d_count,
                                "Dq": _Dq,
                                "B": _B,
                                "C": _C,
                                "states": states,
                            },
                        )
                    elif self.d_count == 5:  # d5
                        states = matrices.d5(Dq=_Dq, B=_B, C=_C).solver()
                        self.result.append(
                            {
                                "d_count": self.d_count,
                                "Dq": _Dq,
                                "B": _B,
                                "C": _C,
                                "states": states,
                            },
                        )
                    elif self.d_count == 6:  # d6
                        states = matrices.d6(Dq=_Dq, B=_B, C=_C).solver()
                        self.result.append(
                            {
                                "d_count": self.d_count,
                                "Dq": _Dq,
                                "B": _B,
                                "C": _C,
                                "states": states,
                            },
                        )
                    elif self.d_count == 7:  # d7
                        states = matrices.d7(Dq=_Dq, B=_B, C=_C).solver()
                        self.result.append(
                            {
                                "d_count": self.d_count,
                                "Dq": _Dq,
                                "B": _B,
                                "C": _C,
                                "states": states,
                            },
                        )
                    elif self.d_count == 8:  # d8
                        states = matrices.d8(Dq=_Dq, B=_B, C=_C).solver()
                        self.result.append(
                            {
                                "d_count": self.d_count,
                                "Dq": _Dq,
                                "B": _B,
                                "C": _C,
                                "states": states,
                            },
                        )
                    else:
                        msg = "not a correct value!"
                        raise ValueError(msg)

    @property
    def return_result(self) -> list[dict]:
        return self.result


if __name__ == "__main__":
    res = Batch()
    res.calculation()
