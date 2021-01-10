from __future__ import print_function

import numpy as np
from numpy.linalg import eigh

_sqrt2 = np.sqrt(2.0)
_sqrt3 = np.sqrt(3.0)
_sqrt6 = np.sqrt(6.0)

_2sqrt2 = _sqrt2 * 2.0
_2sqrt3 = _sqrt3 * 2.0
_3sqrt2 = _sqrt2 * 3.0
_3sqrt3 = _sqrt3 * 3.0
_3sqrt6 = _sqrt6 * 3.0


class d2(object):
    def __init__(self, Dq=0.0, B=860.0, C=3801.0):
        """
        parameter
        ---------
        All parameters in wavenumbers (cm-)
        Dq: float
                Crystalfield-Splitting
        B: float
                Racah-Parameter
        C: float
                Racah-Parameter
        returns
        -------
        dictionary with elements of:
                * Atomic-Termsymbols: str
                * Eigen-Energies: float numpy-array
                        Eigen-Energies of the atomic states depending on the crystalfield
        """
        self.Dq = np.float64(Dq)
        self.B = np.float64(B)
        self.C = np.float64(C)

    def A_1_1_states(self):
        # -  diagonal elements

        AA = -8 * self.Dq + 10 * self.B + 5 * self.C
        BB = +12 * self.Dq + 8 * self.B + 4 * self.C

        # non diagonal elements

        AB = BA = _sqrt6 * (2 * self.B + self.C)

        states = np.array([[AA, AB], [BA, BB]])

        return self.eigensolver(states)

    def E_1_states(self):
        # -  diagonal elements

        AA = +12 * self.Dq + self.B + 2 * self.C
        BB = +2 * self.Dq + 2 * self.C

        # non diagonal elements

        AB = BA = -_2sqrt3 * self.B

        states = np.array([[AA, AB], [BA, BB]])

        return self.eigensolver(states)

    def T_1_2_states(self):
        # -  diagonal elements

        AA = -8 * self.Dq + self.B + 2 * self.C
        BB = +2 * self.Dq + 2 * self.C

        # non diagonal elements

        AB = BA = +_2sqrt3 * self.B

        states = np.array([[AA, AB], [BA, BB]])

        return self.eigensolver(states)

    def T_3_1_states(self):
        # -  diagonal elements

        AA = -8 * self.Dq - 5 * self.B
        BB = +2 * self.Dq + 4 * self.B

        # non diagonal elements

        AB = BA = 6 * self.B

        states = np.array([[AA, AB], [BA, BB]])

        return self.eigensolver(states)

    def eigensolver(self, M):
        """
        :param M: 2 dimensional square array == TS matrics of Ligand field Hamiltonian
        :return: 1 dimensiona                                 l array == eigenvalues of the diagonalized Ligand field Hamiltonian
        """

        return eigh(M)[0]

    def solver(self):
        # Ligand field independent states

        # Ligendfield single depentent states

        GS = self.T_3_1_states()[0]

        T_1_1 = np.array([+2 * self.Dq + 4 * self.B + 2 * self.C]) - GS
        T_3_2 = np.array([+2 * self.Dq - 8 * self.B]) - GS
        A_3_2 = np.array([12 * self.Dq - 8 * self.B]) - GS
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


class d3(object):
    def __init__(self, Dq=0.0, B=918.0, C=4133.0):
        """
        parameter
        ---------
        All parameters in wavenumbers (cm-)
        Dq: float
                Crystalfield-Splitting
        B: float
                Racah-Parameter
        C: float
                Racah-Parameter

        returns
        -------
        dictionary with elements of:
                * Atomic-Termsymbols: str
                * Eigen-Energies: float numpy-array
                        Eigen-Energies of the atomic states depending on the crystalfield
        """
        self.Dq = np.float64(Dq)
        self.B = np.float64(B)
        self.C = np.float64(C)

    def T_2_2_states(self):
        # -  diagonal elements

        AA = -12 * self.Dq + 5 * self.C
        BB = -2 * self.Dq - 6 * self.B + 3 * self.C
        CC = -2 * self.Dq + 4 * self.B + 3 * self.C
        DD = +8 * self.Dq + 6 * self.B + 5 * self.C
        EE = +8 * self.Dq - 2 * self.B + 3 * self.C

        # non diagonal elements

        AB = BA = -_3sqrt3 * self.B
        AC = CA = -5 * _sqrt3 * self.B
        AD = DA = 4 * self.B + 2 * self.C
        AE = EA = 2 * self.B

        BC = CB = 3 * self.B
        BD = DB = -_3sqrt3 * self.B
        BE = EB = -_3sqrt3 * self.B

        CD = DC = -_sqrt3 * self.B
        CE = EC = +_sqrt3 * self.B

        DE = ED = 10 * self.B

        states = np.array(
            [
                [AA, AB, AC, AD, AE],
                [BA, BB, BC, BD, BE],
                [CA, CB, CC, CD, CE],
                [DA, DB, DC, DD, DE],
                [EA, EB, EC, ED, EE],
            ]
        )

        return self.eigensolver(states)

    def T_2_1_states(self):
        # -  diagonal elements

        AA = -12 * self.Dq - 6 * self.B + 3 * self.C
        BB = -2 * self.Dq + 3 * self.C
        CC = -2 * self.Dq - 6 * self.B + 3 * self.C
        DD = +8 * self.Dq - 6 * self.B + 3 * self.C
        EE = +8 * self.Dq - 2 * self.B + 3 * self.C

        # non diagonal elements

        AB = BA = -3 * self.B
        AC = CA = +3 * self.B
        AD = DA = 0.0
        AE = EA = -_2sqrt3 * self.B

        BC = CB = -3 * self.B
        BD = DB = +3 * self.B
        BE = EB = _3sqrt3 * self.B

        CD = DC = -3 * self.B
        CE = EC = -_sqrt3 * self.B

        DE = ED = _2sqrt3 * self.B

        states = np.array(
            [
                [AA, AB, AC, AD, AE],
                [BA, BB, BC, BD, BE],
                [CA, CB, CC, CD, CE],
                [DA, DB, DC, DD, DE],
                [EA, EB, EC, ED, EE],
            ]
        )

        return self.eigensolver(states)

    def E_2_states(self):
        # -  diagonal elements

        AA = -12 * self.Dq - 6 * self.B + 3 * self.C
        BB = -2 * self.Dq + 8 * self.B + 6 * self.C
        CC = -2 * self.Dq - 1 * self.B + 3 * self.C
        DD = +18 * self.Dq - 8 * self.B + 4 * self.C

        # non diagonal elements

        AB = BA = -6 * _sqrt2 * self.B
        AC = CA = -_3sqrt2 * self.B
        AD = DA = 0.0

        BC = CB = 10 * self.B
        BD = DB = +_sqrt3 * (2 * self.B + self.C)

        CD = DC = _2sqrt3 * self.B

        states = np.array(
            [[AA, AB, AC, AD], [BA, BB, BC, BD], [CA, CB, CC, CD], [DA, DB, DC, DD]]
        )

        return self.eigensolver(states)

    def T_4_1_states(self):
        # -  diagonal elements

        AA = -2 * self.Dq - 3 * self.B
        BB = +8 * self.Dq - 12 * self.B

        # non diagonal elements

        AB = BA = 6 * self.B

        states = np.array([[AA, AB], [BA, BB]])

        return self.eigensolver(states)

    def eigensolver(self, M):
        """
        :param M: 2 dimensional square array == TS matrics of Ligand field Hamiltonian
        :return: 1 dimensiona                                 l array == eigenvalues of the diagonalized Ligand field Hamiltonian
        """

        return eigh(M)[0]

    def solver(self):
        # Ligand field independent states

        # Ligendfield single depentent states

        GS = np.array([-12 * self.Dq - 15 * self.B])

        A_4_2 = np.array([0], dtype=np.float)
        T_4_2 = np.array([-2 * self.Dq - 15 * self.B]) - GS

        A_2_1 = np.array([-2 * self.Dq - 11 * self.B + 3 * self.C]) - GS
        A_2_2 = np.array([-2 * self.Dq + 9 * self.B + 3 * self.C]) - GS

        # Ligandfield dependent
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


class d4(object):
    def __init__(self, Dq=0.0, B=965.0, C=4449.0):
        """
        parameter
        ---------
        All parameters in wavenumbers (cm-)
        Dq: float
                Crystalfield-Splitting
        B: float
                Racah-Parameter
        C: float
                Racah-Parameter
        returns
        -------
        dictionary with elements of:
                * Atomic-Termsymbols: str
                * Eigen-Energies: float numpy-array
                * Eigen-Energies of the atomic states depending on the crystalfield
        """
        self.Dq = np.float64(Dq)
        self.B = np.float64(B)
        self.C = np.float64(C)

    def T_3_1_states(self):
        # -  diagonal elements

        AA = -16 * self.Dq - 15 * self.B + 5 * self.C
        BB = -6 * self.Dq - 11 * self.B + 4 * self.C
        CC = -6 * self.Dq - 3 * self.B + 6 * self.C
        DD = +4 * self.Dq - self.B + 6 * self.C
        EE = +4 * self.Dq - 9 * self.B + 4 * self.C
        FF = +4 * self.Dq - 11 * self.B + 4 * self.C
        GG = +14 * self.Dq - 16 * self.B + 5 * self.C

        # non diagonal elements

        AB = BA = _sqrt6 * self.B
        AC = CA = _3sqrt2 * self.B
        AD = DA = -_sqrt2 * (2 * self.B + self.C)
        AE = EA = _2sqrt2 * self.B
        AF = FA = 0.0
        AG = GA = 0.0

        BC = CB = 5 * _sqrt3 * self.B
        BD = DB = _sqrt3 * self.B
        BE = EB = -_sqrt3 * self.B
        BF = FB = 3 * self.B
        BG = GB = _sqrt6 * self.B

        CD = DC = -3 * self.B
        CE = EC = -3 * self.B
        CF = FC = 5 * _sqrt3 * self.B
        CG = GC = _sqrt2 * (self.B + self.C)

        DE = ED = -10 * self.B
        DF = FD = 0.0
        DG = GD = _3sqrt2 * self.B

        EF = FE = -2 * _sqrt3 * self.B
        EG = GE = -_3sqrt2 * self.B

        FG = GF = _sqrt6 * self.B

        states = np.array(
            [
                [AA, AB, AC, AD, AE, AF, AG],
                [BA, BB, BC, BD, BE, BF, BG],
                [CA, CB, CC, CD, CE, CF, CG],
                [DA, DB, DC, DD, DE, DF, DG],
                [EA, EB, EC, ED, EE, EF, EG],
                [FA, FB, FC, FD, FE, FF, FG],
                [GA, GB, GC, GD, GE, GF, GG],
            ]
        )

        return self.eigensolver(states)

    def T_1_2_states(self):
        # diagonal elements

        AA = -16 * self.Dq - 9 * self.B + 7 * self.C
        BB = -6 * self.Dq - 9 * self.B + 6 * self.C
        CC = -6 * self.Dq + 3 * self.B + 8 * self.C
        DD = +4 * self.Dq - 9 * self.B + 6 * self.C
        EE = +4 * self.Dq - 3 * self.B + 6 * self.C
        FF = +4 * self.Dq + 5 * self.B + 8 * self.C
        GG = +14 * self.Dq + 7 * self.C

        # non diagonal elements

        AB = BA = -_3sqrt2 * self.B
        AC = CA = 5 * _sqrt6 * self.B
        AD = DA = 0.0
        AE = EA = _2sqrt2 * self.B
        AF = FA = -_sqrt2 * (2 * self.B + self.C)
        AG = GA = 0.0

        BC = CB = -5 * _sqrt3 * self.B
        BD = DB = 3 * self.B
        BE = EB = -3 * self.B
        BF = FB = -3 * self.B
        BG = GB = -_sqrt6 * self.B

        CD = DC = -3 * _sqrt3 * self.B
        CE = EC = 5 * _sqrt3 * self.B
        CF = FC = -5 * _sqrt3 * self.B
        CG = GC = _sqrt2 * (3 * self.B + self.C)

        DE = ED = -6 * self.B
        DF = FD = 0.0
        DG = GD = -_3sqrt6 * self.B

        EF = FE = -10 * self.B
        EG = GE = _sqrt6 * self.B

        FG = GF = _sqrt6 * self.B

        states = np.array(
            [
                [AA, AB, AC, AD, AE, AF, AG],
                [BA, BB, BC, BD, BE, BF, BG],
                [CA, CB, CC, CD, CE, CF, CG],
                [DA, DB, DC, DD, DE, DF, DG],
                [EA, EB, EC, ED, EE, EF, EG],
                [FA, FB, FC, FD, FE, FF, FG],
                [GA, GB, GC, GD, GE, GF, GG],
            ]
        )

        return self.eigensolver(states)

    def A_1_1_states(self):
        # diagonal elements

        AA = -16 * self.Dq + 10 * self.C
        BB = -6 * self.Dq + 6 * self.C
        CC = +4 * self.Dq + 14 * self.B + 11 * self.C
        DD = +4 * self.Dq - 3 * self.B + 6 * self.C
        EE = +24 * self.Dq - 16 * self.B + 8 * self.C

        # non diagonal elements

        AB = BA = -12 * _sqrt2 * self.B
        AC = CA = _sqrt2 * (4 * self.B + 2 * self.C)
        AD = DA = _2sqrt2 * self.B
        AE = EA = 0.0

        BC = CB = -12 * self.B
        BD = DB = -6 * self.B
        BE = EB = 0.0

        CD = DC = 20 * self.B
        CE = EC = _sqrt6 * (2 * self.B + self.C)

        DE = ED = 2 * _sqrt6 * self.B

        states = np.array(
            [
                [AA, AB, AC, AD, AE],
                [BA, BB, BC, BD, BE],
                [CA, CB, CC, CD, CE],
                [DA, DB, DC, DD, DE],
                [EA, EB, EC, ED, EE],
            ]
        )

        return self.eigensolver(states)

    def E_1_1_states(self):
        # diagonal elements

        AA = -16 * self.Dq - 9 * self.B + 7 * self.C
        BB = -6 * self.Dq - 6 * self.B + 6 * self.C
        CC = +4 * self.Dq + 5 * self.B + 8 * self.C
        DD = +4 * self.Dq + 6 * self.B + 9 * self.C
        EE = +4 * self.Dq - 3 * self.B + 6 * self.C

        # non diagonal elements

        AB = BA = -6 * self.B
        AC = CA = _sqrt2 * (2 * self.B + self.C)
        AD = DA = 2 * self.B
        AE = EA = 4 * self.B

        BC = CB = -_3sqrt2 * self.B
        BD = DB = -12 * self.B
        BE = EB = 0.0

        CD = DC = 10 * _sqrt2 * self.B
        CE = EC = -10 * _sqrt2 * self.B

        DE = ED = 0.0

        states = np.array(
            [
                [AA, AB, AC, AD, AE],
                [BA, BB, BC, BD, BE],
                [CA, CB, CC, CD, CE],
                [DA, DB, DC, DD, DE],
                [EA, EB, EC, ED, EE],
            ]
        )

        return self.eigensolver(states)

    def T_3_2_states(self):
        # diagonal elements

        AA = -6 * self.Dq - 9 * self.B + 4 * self.C
        BB = -6 * self.Dq - 5 * self.B + 6 * self.C
        CC = +4 * self.Dq - 13 * self.B + 4 * self.C
        DD = +4 * self.Dq - 9 * self.B + 4 * self.C
        EE = +14 * self.Dq - 8 * self.B + 5 * self.C

        # non diagonal elements

        AB = BA = -5 * _sqrt3 * self.B
        AC = CA = _sqrt6 * self.B
        AD = DA = _sqrt3 * self.B
        AE = EA = _sqrt6 * self.B

        BC = CB = -_3sqrt2 * self.B
        BD = DB = 3 * self.B
        BE = EB = _sqrt2 * (3 * self.B + self.C)

        CD = DC = -2 * _sqrt2 * self.B
        CE = EC = -6 * self.B

        DE = ED = -8 * self.B + 5 * self.C

        states = np.array(
            [
                [AA, AB, AC, AD, AE],
                [BA, BB, BC, BD, BE],
                [CA, CB, CC, CD, CE],
                [DA, DB, DC, DD, DE],
                [EA, EB, EC, ED, EE],
            ]
        )

        return self.eigensolver(states)

    def T_1_1_states(self):
        # diagonal elements

        AA = -6 * self.Dq - 3 * self.B + 6 * self.C
        BB = -6 * self.Dq - 3 * self.B + 8 * self.C
        CC = +4 * self.Dq - 3 * self.B + 6 * self.C
        DD = +14 * self.Dq - 16 * self.B + 7 * self.C

        # non diagonal elements

        AB = BA = -5 * _sqrt3 * self.B
        AC = CA = 3 * self.B
        AD = DA = _sqrt6 * self.B

        BC = CB = -5 * _sqrt3 * self.B
        BD = DB = _sqrt2 * (self.B + self.C)

        CD = DC = -_sqrt6 * self.B

        states = np.array(
            [[AA, AB, AC, AD], [BA, BB, BC, BD], [CA, CB, CC, CD], [DA, DB, DC, DD]]
        )

        return self.eigensolver(states)

    def E_3_1_states(self):
        # diagonal elements

        AA = -6 * self.Dq - 13 * self.B + 4 * self.C
        BB = -6 * self.Dq - 10 * self.B + 4 * self.C
        CC = +4 * self.Dq - 11 * self.B + 4 * self.C

        # non diagonal elements

        AB = BA = -4 * self.B
        AC = CA = 0.0

        BC = CB = -_3sqrt2 * self.B

        states = np.array([[AA, AB, AC], [BA, BB, BC], [CA, CB, CC]])

        return self.eigensolver(states)

    def A_3_2_states(self):
        # diagonal elements

        AA = -6 * self.Dq - 8 * self.B + 4 * self.C
        BB = +4 * self.Dq - 2 * self.B + 7 * self.C

        # non diagonal elements

        AB = BA = -12 * self.B

        states = np.array([[AA, AB], [BA, BB]])

        return self.eigensolver(states)

    def A_1_2_states(self):
        # diagonal elements

        AA = -6 * self.Dq - 12 * self.B + 6 * self.C
        BB = +4 * self.Dq - 3 * self.B + 6 * self.C

        # non diagonal elements

        AB = BA = -6 * self.B

        states = np.array([[AA, AB], [BA, BB]])

        return self.eigensolver(states)

    def eigensolver(self, M):
        """
        :param M: 2 dimensional square array == TS matrics of Ligand field Hamiltonian
        :return: 1 dimensional array == eigenvalues of the diagonalized Ligand field Hamiltonian
        """

        return eigh(M)[0]

    def solver(self):
        # Ligand field independent states

        # A_6_1 = np.array( [ 0 ] )  # Starting value is -35. * B, but has to set to zero per definition
        # E_4 = self.E_4_states( ) + 35 * self.B
        # A_4_1 = np.array( [ -25 * self.B + 5 * self.C ] ) + 35 * self.B
        # A_4_2 = np.array( [ -13 * self.B + 7 * self.C ] ) + 35 * self.B

        # Ligendfield single depentent states

        GS = np.array([-6 * self.Dq - 21 * self.B])

        E_5_1 = np.array([0], dtype=np.float)
        T_5_2 = np.array([4 * self.Dq - 21 * self.B]) - GS

        A_3_1 = np.array([-6 * self.Dq - 12 * self.B + 4 * self.C]) - GS

        # Ligandfield dependent
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


class d5(object):
    def __init__(self, Dq=0.0, B=860.0, C=3850.0):
        """
        parameter
        ---------
        All parameters in wavenumbers (cm-)
        Dq: float
                Crystalfield-Splitting
        B: float
                Racah-Parameter
        C: float
                Racah-Parameter

        returns
        -------
        dictionary with elements of:
                * Atomic-Termsymbols: str
                * Eigen-Energies: float numpy-array
                * Eigen-Energies of the atomic states depending on the crystalfield
        """
        self.Dq = np.float64(Dq)
        self.B = np.float64(B)
        self.C = np.float64(C)

    def T_2_2_states(self):
        # diagonal elements

        AA = -20 * self.Dq - 20 * self.B + 10 * self.C
        BB = -10 * self.Dq - 8 * self.B + 9 * self.C
        CC = -10 * self.Dq - 18 * self.B + 9 * self.C
        DD = -16 * self.B + 8 * self.C
        EE = -12 * self.B + 8 * self.C
        FF = +2 * self.B + 12 * self.C
        GG = -6 * self.B + 10 * self.C
        HH = +10 * self.Dq - 18 * self.B + 9 * self.C
        II = +10 * self.Dq - 8 * self.B + 9 * self.C
        JJ = +20 * self.Dq - 20 * self.B + 10 * self.C

        # non diagonal elements

        AB = BA = -_3sqrt6 * self.B
        AC = CA = -_sqrt6 * self.B
        AD = DA = 0.0
        AE = EA = -2 * _sqrt3 * self.B
        AF = FA = 4 * self.B + 2 * self.C
        AG = GA = 2 * self.B
        AH = HA = 0.0
        AI = IA = 0.0
        AJ = JA = 0.0

        BC = CB = 3 * self.B
        BD = DB = -_sqrt6 / 2.0 * self.B
        BE = EB = _3sqrt2 / 2.0 * self.B
        BF = FB = -_3sqrt6 / 2.0 * self.B
        BG = GB = -_3sqrt6 / 2.0 * self.B
        BH = HB = 0.0
        BI = IB = -4 * self.B + self.C
        BJ = JB = 0.0

        CD = DC = -_3sqrt6 / 2.0 * self.B
        CE = EC = _3sqrt2 / 2.0 * self.B
        CF = FC = -5 * _sqrt6 / 2.0 * self.B
        CG = GC = +5 * _sqrt6 / 2.0 * self.B
        CH = HC = -self.C
        CI = IC = 0.0
        CJ = JC = 0.0

        DE = ED = 2 * _sqrt3 * self.B
        DF = FD = 0.0
        DG = GD = 0.0
        DH = HD = -_3sqrt6 / 2.0 * self.B
        DI = ID = -_sqrt6 / 2.0 * self.B
        DJ = JD = 0.0

        EF = FE = -10 * _sqrt3 * self.B
        EG = GE = 0.0
        EH = HE = _3sqrt2 / 2.0 * self.B
        EI = IE = _3sqrt2 / 2.0 * self.B
        EJ = JE = -2 * _sqrt3 * self.B

        FG = GF = 0.0
        FH = HF = -5 * _sqrt6 / 2.0 * self.B
        FI = IF = -_3sqrt6 / 2.0 * self.B
        FJ = JF = 4 * self.B + 2 * self.C

        GH = HG = -5 * _sqrt6 / 2.0 * self.B
        GI = IG = _3sqrt6 / 2.0 * self.B
        GJ = JG = -2.0 * self.B

        HI = IH = 3 * self.B
        HJ = JH = -_sqrt6 * self.B

        IJ = JI = -_3sqrt6 * self.B

        states = np.array(
            [
                [AA, AB, AC, AD, AE, AF, AG, AH, AI, AJ],
                [BA, BB, BC, BD, BE, BF, BG, BH, BI, BJ],
                [CA, CB, CC, CD, CE, CF, CG, CH, CI, CJ],
                [DA, DB, DC, DD, DE, DF, DG, DH, DI, DJ],
                [EA, EB, EC, ED, EE, EF, EG, EH, EI, EJ],
                [FA, FB, FC, FD, FE, FF, FG, FH, FI, FJ],
                [GA, GB, GC, GD, GE, GF, GG, GH, GI, GJ],
                [HA, HB, HC, HD, HE, HF, HG, HH, HI, HJ],
                [IA, IB, IC, ID, IE, IF, IG, IH, II, IJ],
                [JA, JB, JC, JD, JE, JF, JG, JH, JI, JJ],
            ]
        )

        return self.eigensolver(states)

    def T_2_1_states(self):
        # diagonal elements

        AA = -10 * self.Dq - 22 * self.B + 9 * self.C
        BB = -10 * self.Dq - 8 * self.B + 9 * self.C
        CC = -4 * self.B + 10 * self.C
        DD = -12 * self.B + 8 * self.C
        EE = -10 * self.B + 10 * self.C
        FF = -6 * self.B + 10 * self.C
        GG = +10 * self.Dq - 8 * self.B + 9 * self.C
        HH = +10 * self.Dq - 22 * self.B + 9 * self.C

        # non diagonal elements

        AB = BA = -3 * self.B
        AC = CA = _3sqrt2 / 2.0 * self.B
        AD = DA = -_3sqrt2 / 2.0 * self.B
        AE = EA = _3sqrt2 / 2.0 * self.B
        AF = FA = _3sqrt6 / 2.0 * self.B
        AG = GA = 0.0
        AH = HA = -self.C

        BC = CB = -_3sqrt2 / 2.0 * self.B
        BD = DB = -_3sqrt2 / 2.0 * self.B
        BE = EB = -15 * _sqrt2 / 2.0 * self.B
        BF = FB = -5 * _sqrt6 / 2.0 * self.B
        BG = GB = -4 * self.B - self.C
        BH = HB = 0.0

        CD = DC = 0.0
        CE = EC = 0.0
        CF = FC = 10 * _sqrt3 * self.B
        CG = GC = _3sqrt2 / 2.0 * self.B
        CH = HC = -_3sqrt2 / 2.0 * self.B

        DE = ED = 0.0
        DF = FD = 0.0
        DG = GD = -_3sqrt2 / 2.0 * self.B
        DH = HD = -_3sqrt2 / 2.0 * self.B

        EF = FE = 2 * _sqrt3 * self.B
        EG = GE = 15 * _sqrt2 / 2.0 * self.B
        EH = HE = -_3sqrt2 / 2.0 * self.B

        FG = GF = 5 * _sqrt6 / 2.0 * self.B
        FH = HF = -_3sqrt6 / 2.0 * self.B

        GH = HG = -3 * self.B

        states = np.array(
            [
                [AA, AB, AC, AD, AE, AF, AG, AH],
                [BA, BB, BC, BD, BE, BF, BG, BH],
                [CA, CB, CC, CD, CE, CF, CG, CH],
                [DA, DB, DC, DD, DE, DF, DG, DH],
                [EA, EB, EC, ED, EE, EF, EG, EH],
                [FA, FB, FC, FD, FE, FF, FG, FH],
                [GA, GB, GC, GD, GE, GF, GG, GH],
                [HA, HB, HC, HD, HE, HF, HG, HH],
            ]
        )

        return self.eigensolver(states)

    def E_2_states(self):
        # diagonal elements

        AA = -10 * self.Dq - 4 * self.B + 12 * self.C
        BB = -10 * self.Dq - 13 * self.B + 9 * self.C
        CC = -4 * self.B + 10 * self.C
        DD = -16 * self.B + 8 * self.C
        EE = -12 * self.B + 8 * self.C
        FF = +10 * self.Dq - 13 * self.B + 9 * self.C
        GG = +10 * self.Dq - 4 * self.B + 12 * self.C

        # non diagonal elements

        AB = BA = -10 * self.B
        AC = CA = 6 * self.B
        AD = DA = 6 * _sqrt3 * self.B
        AE = EA = 6 * _sqrt2 * self.B
        AF = FA = -2 * self.B
        AG = GA = 4 * self.B + 2 * self.C

        BC = CB = 3 * self.B
        BD = DB = -3 * _sqrt3 * self.B
        BE = EB = 0.0
        BF = FB = -2 * self.B - self.C
        BG = GB = -2 * self.B

        CD = DC = 0.0
        CE = EC = 0.0
        CF = FC = -3 * self.B
        CG = GC = -6 * self.B

        DE = ED = 2 * _sqrt6 * self.B
        DF = FD = -3 * _sqrt3 * self.B
        DG = GD = 6 * _sqrt3 * self.B

        EF = FE = 0.0
        EG = GE = 6 * _sqrt2 * self.B

        FG = GF = -10 * self.B

        states = np.array(
            [
                [AA, AB, AC, AD, AE, AF, AG],
                [BA, BB, BC, BD, BE, BF, BG],
                [CA, CB, CC, CD, CE, CF, CG],
                [DA, DB, DC, DD, DE, DF, DG],
                [EA, EB, EC, ED, EE, EF, EG],
                [FA, FB, FC, FD, FE, FF, FG],
                [GA, GB, GC, GD, GE, GF, GG],
            ]
        )

        return self.eigensolver(states)

    def A_2_1_states(self):
        # diagonal elements

        AA = -10 * self.Dq - 3 * self.B + 9 * self.C
        BB = -12 * self.B + 8 * self.C
        CC = -19 * self.B + 8 * self.C
        DD = +10 * self.Dq - 3 * self.B + 9 * self.C

        # non diagonal elements

        AB = BA = _3sqrt2 * self.B
        AC = CA = 0.0
        AD = DA = -6 * self.B - self.C

        BC = CB = -4 * _sqrt3 * self.B
        BD = DB = _3sqrt2 * self.B

        CD = DC = 0.0

        states = np.array(
            [[AA, AB, AC, AD], [BA, BB, BC, BD], [CA, CB, CC, CD], [DA, DB, DC, DD]]
        )

        return self.eigensolver(states)

    def A_2_2_states(self):
        # diagonal elements

        AA = -10 * self.Dq - 23 * self.B + 9 * self.C
        BB = -12 * self.B + 8 * self.C
        CC = +10 * self.Dq - 23 * self.B + 9 * self.C

        # non diagonal elements

        AB = BA = -_3sqrt2 * self.B
        AC = CA = _2sqrt2 * self.B - self.C

        BC = CB = -_3sqrt2 * self.B

        states = np.array([[AA, AB, AC], [BA, BB, BC], [CA, CB, CC]])

        return self.eigensolver(states)

    def T_4_1_states(self):
        # diagonal elements

        AA = -10 * self.Dq - 25 * self.B + 6 * self.C
        BB = -16 * self.B + 7 * self.C
        CC = 10 * self.Dq - 25 * self.B + 6 * self.C

        # non diagonal elements

        AB = BA = _3sqrt2 * self.B
        AC = CA = -self.C

        BC = CB = -_3sqrt2 * self.B

        states = np.array([[AA, AB, AC], [BA, BB, BC], [CA, CB, CC]])

        return self.eigensolver(states)

    def T_4_2_states(self):
        # diagonal elements

        AA = -10 * self.Dq - 17 * self.B + 6 * self.C
        BB = -22 * self.B + 5 * self.C
        CC = +10 * self.Dq - 17 * self.B + 6 * self.C

        # non diagonal elements

        AB = BA = -_sqrt6 * self.B
        AC = CA = -4 * self.B - self.C

        BC = CB = -_sqrt6 * self.B

        # AB = BC = AC = 0
        states = np.array([[AA, AB, AC], [BA, BB, BC], [CA, CB, CC]])

        return self.eigensolver(states)

    def E_4_states(self):
        # diagonal elements

        AA = -22 * self.B + 5 * self.C
        BB = -21 * self.B + 5 * self.C

        # non diagonal elements

        AB = BA = -2 * _sqrt3 * self.B

        states = np.array([[AA, AB], [BA, BB]])

        return self.eigensolver(states)

    def eigensolver(self, M):
        """
        :param M: 2 dimensional square array == TS matrics of Ligand field Hamiltonian
        :return: 1 dimensional array == eigenvalues of the diagonalized Ligand field Hamiltonian
        """

        return eigh(M)[0]

    def solver(self):
        # Ligand field independent states
        GS = 35 * self.B

        A_6_1 = np.array(
            [0.0], dtype=float
        )  # Starting value is -35. * B, but has to set to zero per definition
        E_4 = self.E_4_states() + GS
        A_4_1 = np.array([-25 * self.B + 5 * self.C]) + GS
        A_4_2 = np.array([-13 * self.B + 7 * self.C]) + GS

        # Ligandfield dependent
        T_2_2 = self.T_2_2_states() + GS
        T_2_1 = self.T_2_1_states() + GS
        E_2 = self.E_2_states() + GS
        A_2_1 = self.A_2_1_states() + GS
        A_2_2 = self.A_2_2_states() + GS
        T_4_1 = self.T_4_1_states() + GS
        T_4_2 = self.T_4_2_states() + GS

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


class d6(object):
    def __init__(self, Dq=0.0, B=1065.0, C=5120.0):
        """
        parameter
        ---------
        All parameters in wavenumbers (cm-)
        Dq: float
                Crystalfield-Splitting
        B: float
                Racah-Parameter
        C: float
                Racah-Parameter

        returns
        -------
        dictionary with elements of:
                * Atomic-Termsymbols: str
                * Eigen-Energies: float numpy-array
                        Eigen-Energies of the atomic states depending on the crystalfield
        """
        self.Dq = np.float64(Dq)
        self.B = np.float64(B)
        self.C = np.float64(C)

    def T_3_1_states(self):
        # -  diagonal elements

        AA = +16 * self.Dq - 15 * self.B + 5 * self.C
        BB = +6 * self.Dq - 11 * self.B + 4 * self.C
        CC = +6 * self.Dq - 3 * self.B + 6 * self.C
        DD = -4 * self.Dq - self.B + 6 * self.C
        EE = -4 * self.Dq - 9 * self.B + 4 * self.C
        FF = -4 * self.Dq - 11 * self.B + 4 * self.C
        GG = -14 * self.Dq - 16 * self.B + 5 * self.C

        # non diagonal elements

        AB = BA = -_sqrt6 * self.B
        AC = CA = -_3sqrt2 * self.B
        AD = DA = _sqrt2 * (2 * self.B + self.C)
        AE = EA = -_2sqrt2 * self.B
        AF = FA = 0.0
        AG = GA = 0.0

        BC = CB = 5 * _sqrt3 * self.B
        BD = DB = _sqrt3 * self.B
        BE = EB = -_sqrt3 * self.B
        BF = FB = 3 * self.B
        BG = GB = _sqrt6 * self.B

        CD = DC = -3 * self.B
        CE = EC = -3 * self.B
        CF = FC = 5 * _sqrt3 * self.B
        CG = GC = _sqrt2 * (self.B + self.C)

        DE = ED = -10 * self.B
        DF = FD = 0.0
        DG = GD = _3sqrt2 * self.B

        EF = FE = -2 * _sqrt3 * self.B
        EG = GE = -_3sqrt2 * self.B

        FG = GF = _sqrt6 * self.B

        states = np.array(
            [
                [AA, AB, AC, AD, AE, AF, AG],
                [BA, BB, BC, BD, BE, BF, BG],
                [CA, CB, CC, CD, CE, CF, CG],
                [DA, DB, DC, DD, DE, DF, DG],
                [EA, EB, EC, ED, EE, EF, EG],
                [FA, FB, FC, FD, FE, FF, FG],
                [GA, GB, GC, GD, GE, GF, GG],
            ]
        )

        return self.eigensolver(states)

    def T_1_2_states(self):
        # diagonal elements

        AA = +16 * self.Dq - 9 * self.B + 7 * self.C
        BB = +6 * self.Dq - 9 * self.B + 6 * self.C
        CC = +6 * self.Dq + 3 * self.B + 8 * self.C
        DD = -4 * self.Dq - 9 * self.B + 6 * self.C
        EE = -4 * self.Dq - 3 * self.B + 6 * self.C
        FF = -4 * self.Dq + 5 * self.B + 8 * self.C
        GG = -14 * self.Dq + 7 * self.C

        # non diagonal elements

        AB = BA = _3sqrt2 * self.B
        AC = CA = -5 * _sqrt6 * self.B
        AD = DA = 0.0
        AE = EA = -_2sqrt2 * self.B
        AF = FA = _sqrt2 * (2 * self.B + self.C)
        AG = GA = 0.0

        BC = CB = -5 * _sqrt3 * self.B
        BD = DB = 3 * self.B
        BE = EB = -3 * self.B
        BF = FB = -3 * self.B
        BG = GB = -_sqrt6 * self.B

        CD = DC = -3 * _sqrt3 * self.B
        CE = EC = 5 * _sqrt3 * self.B
        CF = FC = -5 * _sqrt3 * self.B
        CG = GC = _sqrt2 * (3 * self.B + self.C)

        DE = ED = -6 * self.B
        DF = FD = 0.0
        DG = GD = -_3sqrt6 * self.B

        EF = FE = -10 * self.B
        EG = GE = _sqrt6 * self.B

        FG = GF = _sqrt6 * self.B

        states = np.array(
            [
                [AA, AB, AC, AD, AE, AF, AG],
                [BA, BB, BC, BD, BE, BF, BG],
                [CA, CB, CC, CD, CE, CF, CG],
                [DA, DB, DC, DD, DE, DF, DG],
                [EA, EB, EC, ED, EE, EF, EG],
                [FA, FB, FC, FD, FE, FF, FG],
                [GA, GB, GC, GD, GE, GF, GG],
            ]
        )

        return self.eigensolver(states)

    def A_1_1_states(self):
        # diagonal elements

        AA = +16 * self.Dq + 10 * self.C
        BB = +6 * self.Dq + 6 * self.C
        CC = -4 * self.Dq + 14 * self.B + 11 * self.C
        DD = -4 * self.Dq - 3 * self.B + 6 * self.C
        EE = -24 * self.Dq - 16 * self.B + 8 * self.C

        # non diagonal elements

        AB = BA = -12 * _sqrt2 * self.B
        AC = CA = _sqrt2 * (4 * self.B + 2 * self.C)
        AD = DA = _2sqrt2 * self.B
        AE = EA = 0.0

        BC = CB = -12 * self.B
        BD = DB = -6 * self.B
        BE = EB = 0.0

        CD = DC = 20 * self.B
        CE = EC = _sqrt6 * (2 * self.B + self.C)

        DE = ED = 2 * _sqrt6 * self.B

        states = np.array(
            [
                [AA, AB, AC, AD, AE],
                [BA, BB, BC, BD, BE],
                [CA, CB, CC, CD, CE],
                [DA, DB, DC, DD, DE],
                [EA, EB, EC, ED, EE],
            ]
        )

        return self.eigensolver(states)

    def E_1_1_states(self):
        # diagonal elements

        AA = +16 * self.Dq - 9 * self.B + 7 * self.C
        BB = +6 * self.Dq - 6 * self.B + 6 * self.C
        CC = -4 * self.Dq + 5 * self.B + 8 * self.C
        DD = -4 * self.Dq + 6 * self.B + 9 * self.C
        EE = -4 * self.Dq - 3 * self.B + 6 * self.C

        # non diagonal elements

        AB = BA = 6 * self.B
        AC = CA = _sqrt2 * (2 * self.B + self.C)
        AD = DA = -2 * self.B
        AE = EA = -4 * self.B

        BC = CB = -_3sqrt2 * self.B
        BD = DB = -12 * self.B
        BE = EB = 0.0

        CD = DC = 10 * _sqrt2 * self.B
        CE = EC = -10 * _sqrt2 * self.B

        DE = ED = 0.0

        states = np.array(
            [
                [AA, AB, AC, AD, AE],
                [BA, BB, BC, BD, BE],
                [CA, CB, CC, CD, CE],
                [DA, DB, DC, DD, DE],
                [EA, EB, EC, ED, EE],
            ]
        )

        return self.eigensolver(states)

    def T_3_2_states(self):
        # diagonal elements

        AA = +6 * self.Dq - 9 * self.B + 4 * self.C
        BB = +6 * self.Dq - 5 * self.B + 6 * self.C
        CC = -4 * self.Dq - 13 * self.B + 4 * self.C
        DD = -4 * self.Dq - 9 * self.B + 4 * self.C
        EE = -14 * self.Dq - 8 * self.B + 5 * self.C

        # non diagonal elements

        AB = BA = -5 * _sqrt3 * self.B
        AC = CA = _sqrt6 * self.B
        AD = DA = _sqrt3 * self.B
        AE = EA = -_sqrt6 * self.B

        BC = CB = -_3sqrt2 * self.B
        BD = DB = 3 * self.B
        BE = EB = _sqrt2 * (3 * self.B + self.C)

        CD = DC = -2 * _sqrt2 * self.B
        CE = EC = -6 * self.B

        DE = ED = 3 * _sqrt2 * self.B

        states = np.array(
            [
                [AA, AB, AC, AD, AE],
                [BA, BB, BC, BD, BE],
                [CA, CB, CC, CD, CE],
                [DA, DB, DC, DD, DE],
                [EA, EB, EC, ED, EE],
            ]
        )

        return self.eigensolver(states)

    def T_1_1_states(self):
        # diagonal elements

        AA = +6 * self.Dq - 3 * self.B + 6 * self.C
        BB = +6 * self.Dq - 3 * self.B + 8 * self.C
        CC = -4 * self.Dq - 3 * self.B + 6 * self.C
        DD = -14 * self.Dq - 16 * self.B + 7 * self.C

        # non diagonal elements

        AB = BA = 5 * _sqrt3 * self.B
        AC = CA = 3 * self.B
        AD = DA = _sqrt6 * self.B

        BC = CB = -5 * _sqrt3 * self.B
        BD = DB = _sqrt2 * (self.B + self.C)

        CD = DC = -_sqrt6 * self.B

        states = np.array(
            [[AA, AB, AC, AD], [BA, BB, BC, BD], [CA, CB, CC, CD], [DA, DB, DC, DD]]
        )

        return self.eigensolver(states)

    def E_3_1_states(self):
        # diagonal elements

        AA = +6 * self.Dq - 13 * self.B + 4 * self.C
        BB = -6 * self.Dq - 10 * self.B + 4 * self.C
        CC = -4 * self.Dq - 11 * self.B + 4 * self.C

        # non diagonal elements

        AB = BA = -4 * self.B
        AC = CA = 0.0

        BC = CB = -_3sqrt2 * self.B

        states = np.array([[AA, AB, AC], [BA, BB, BC], [CA, CB, CC]])

        return self.eigensolver(states)

    def A_3_2_states(self):
        # diagonal elements

        AA = +6 * self.Dq - 8 * self.B + 4 * self.C
        BB = -4 * self.Dq - 2 * self.B + 7 * self.C

        # non diagonal elements

        AB = BA = -12 * self.B

        states = np.array([[AA, AB], [BA, BB]])

        return self.eigensolver(states)

    def A_1_2_states(self):
        # diagonal elements

        AA = +6 * self.Dq - 12 * self.B + 6 * self.C
        BB = -4 * self.Dq - 3 * self.B + 6 * self.C

        # non diagonal elements

        AB = BA = 6 * self.B

        states = np.array([[AA, AB], [BA, BB]])

        return self.eigensolver(states)

    def eigensolver(self, M):
        """
        :param M: 2 dimensional square array == TS matrics of Ligand field Hamiltonian
        :return: 1 dimensional array == eigenvalues of the diagonalized Ligand field Hamiltonian
        """

        return eigh(M)[0]

    def solver(self):
        # Ligand field independent states

        # A_6_1 = np.array( [ 0 ] )  # Starting value is -35. * B, but has to set to zero per definition
        # E_4 = self.E_4_states( ) + 35 * self.B
        # A_4_1 = np.array( [ -25 * self.B + 5 * self.C ] ) + 35 * self.B
        # A_4_2 = np.array( [ -13 * self.B + 7 * self.C ] ) + 35 * self.B

        # Ligendfield single depentent states

        GS = np.array([-4 * self.Dq - 21 * self.B])

        T_5_2 = np.array([0], dtype=np.float)

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

        if A_1_1[0] <= 1e-4:
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


class d7(object):
    def __init__(self, Dq=0.0, B=971.0, C=4499.0):
        """
        parameter
        ---------
        All parameters in wavenumbers (cm-)
        Dq: float
                Crystalfield-Splitting
        B: float
                Racah-Parameter
        C: float
                Racah-Parameter

        returns
        -------
        dictionary with elements of:
                * Atomic-Termsymbols: str
                * Eigen-Energies: float numpy-array
                * Eigen-Energies of the atomic states depending on the crystalfield
        """
        self.Dq = np.float64(Dq)
        self.B = np.float64(B)
        self.C = np.float64(C)

    def T_2_2_states(self):
        # -  diagonal elements

        AA = +12 * self.Dq + 5 * self.C
        BB = +2 * self.Dq - 6 * self.B + 3 * self.C
        CC = +2 * self.Dq + 4 * self.B + 3 * self.C
        DD = -8 * self.Dq + 6 * self.B + 5 * self.C
        EE = -8 * self.Dq - 2 * self.B + 3 * self.C

        # non diagonal elements

        AB = BA = -_3sqrt3 * self.B
        AC = CA = -5 * _sqrt3 * self.B
        AD = DA = 4 * self.B + 2 * self.C
        AE = EA = 2 * self.B

        BC = CB = 3 * self.B
        BD = DB = -_3sqrt3 * self.B
        BE = EB = -_3sqrt3 * self.B

        CD = DC = -_sqrt3 * self.B
        CE = EC = +_sqrt3 * self.B

        DE = ED = 10 * self.B

        states = np.array(
            [
                [AA, AB, AC, AD, AE],
                [BA, BB, BC, BD, BE],
                [CA, CB, CC, CD, CE],
                [DA, DB, DC, DD, DE],
                [EA, EB, EC, ED, EE],
            ]
        )

        return self.eigensolver(states)

    def T_2_1_states(self):
        # -  diagonal elements

        AA = +12 * self.Dq - 6 * self.B + 3 * self.C
        BB = +2 * self.Dq + 3 * self.C
        CC = +2 * self.Dq - 6 * self.B + 3 * self.C
        DD = -8 * self.Dq - 6 * self.B + 3 * self.C
        EE = -8 * self.Dq - 2 * self.B + 3 * self.C

        # non diagonal elements

        AB = BA = -3 * self.B
        AC = CA = +3 * self.B
        AD = DA = 0.0
        AE = EA = -_2sqrt3 * self.B

        BC = CB = -3 * self.B
        BD = DB = +3 * self.B
        BE = EB = _3sqrt3 * self.B

        CD = DC = -3 * self.B
        CE = EC = -_sqrt3 * self.B

        DE = ED = _2sqrt3 * self.B

        states = np.array(
            [
                [AA, AB, AC, AD, AE],
                [BA, BB, BC, BD, BE],
                [CA, CB, CC, CD, CE],
                [DA, DB, DC, DD, DE],
                [EA, EB, EC, ED, EE],
            ]
        )

        return self.eigensolver(states)

    def E_2_states(self):
        # -  diagonal elements

        AA = +12 * self.Dq - 6 * self.B + 3 * self.C
        BB = +2 * self.Dq + 8 * self.B + 6 * self.C
        CC = +2 * self.Dq - 1 * self.B + 3 * self.C
        DD = -18 * self.Dq - 8 * self.B + 4 * self.C

        # non diagonal elements

        AB = BA = -6 * _sqrt2 * self.B
        AC = CA = -_3sqrt2 * self.B
        AD = DA = 0.0

        BC = CB = 10 * self.B
        BD = DB = +_sqrt3 * (2 * self.B + self.C)

        CD = DC = _2sqrt3 * self.B

        states = np.array(
            [[AA, AB, AC, AD], [BA, BB, BC, BD], [CA, CB, CC, CD], [DA, DB, DC, DD]]
        )

        return self.eigensolver(states)

    def T_4_1_states(self):
        # -  diagonal elements

        AA = +2 * self.Dq - 3 * self.B
        BB = -8 * self.Dq - 12 * self.B

        # non diagonal elements

        AB = BA = 6 * self.B

        states = np.array([[AA, AB], [BA, BB]])

        return self.eigensolver(states)

    def eigensolver(self, M):
        """
        :param M: 2 dimensional square array == TS matrics of Ligand field Hamiltonian
        :return: 1 dimensiona                                 l array == eigenvalues of the diagonalized Ligand field Hamiltonian
        """

        return eigh(M)[0]

    def solver(self):
        # Ligand field independent states

        # Ligandfield multi depnedent state become GS

        T_4_1 = self.T_4_1_states()

        # Ligendfield single depentent states

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


class d8(object):
    def __init__(self, Dq=0.0, B=1030.0, C=4850.0):
        """
        parameter
        ---------
        All parameters in wavenumbers (cm-)
        Dq: float
                Crystalfield-Splitting
        B: float
                Racah-Parameter
        C: float
                Racah-Parameter

        returns
        -------
        dictionary with elements of:
                * Atomic-Termsymbols: str
                * Eigen-Energies: float numpy-array
                * Eigen-Energies of the atomic states depending on the crystalfield
        """
        self.Dq = np.float64(Dq)
        self.B = np.float64(B)
        self.C = np.float64(C)

    def A_1_1_states(self):
        # -  diagonal elements

        AA = +8 * self.Dq + 10 * self.B + 5 * self.C
        BB = -12 * self.Dq + 8 * self.B + 4 * self.C

        # non diagonal elements

        AB = BA = _sqrt6 * (2 * self.B + self.C)

        states = np.array([[AA, AB], [BA, BB]])

        return self.eigensolver(states)

    def E_1_states(self):
        # -  diagonal elements

        AA = -12 * self.Dq + self.B + 2 * self.C
        BB = +2 * self.Dq + 2 * self.C

        # non diagonal elements

        AB = BA = -_2sqrt3 * self.B

        states = np.array([[AA, AB], [BA, BB]])

        return self.eigensolver(states)

    def T_1_2_states(self):
        # -  diagonal elements

        AA = +8 * self.Dq + self.B + 2 * self.C
        BB = -2 * self.Dq + 2 * self.C

        # non diagonal elements

        AB = BA = +_2sqrt3 * self.B

        states = np.array([[AA, AB], [BA, BB]])

        return self.eigensolver(states)

    def T_3_1_states(self):
        # -  diagonal elements

        AA = +8 * self.Dq - 5 * self.B
        BB = -2 * self.Dq + 4 * self.B

        # non diagonal elements

        AB = BA = 6 * self.B

        states = np.array([[AA, AB], [BA, BB]])

        return self.eigensolver(states)

    def eigensolver(self, M):
        """
        :param M: 2 dimensional square array == TS matrics of Ligand field Hamiltonian
        :return: 1 dimensiona                                 l array == eigenvalues of the diagonalized Ligand field Hamiltonian
        """

        return eigh(M)[0]

    def solver(self):
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


if __name__ == "__main__":
    # print( d5( Dq=0, B=1293., C=4823. ).E_4_states( ) )
    import matplotlib.pylab as plt

    for i in np.linspace(0, 1500, 30):
        states = d6(Dq=i).solver()
        states = states["1_A_1"]
        # en_step = np.full( len( states ), i )
        # plt.plot( en_step, states, 'o', color='r' )
        plt.plot(i, states[0], "o", color="r")

    for i in np.linspace(0, 1500, 30):
        states = d6(Dq=i).solver()
        states = states["3_T_2"]
        # en_step = np.full( len( states ), i )
        # plt.plot( en_step, states, 'o', color='g' )
        plt.plot(i, states[0], "o", color="g")

    for i in np.linspace(0, 1500, 30):
        states = d6(Dq=i).solver()
        states = states["3_T_1"]
        # en_step = np.full( len( states ), i )
        # plt.plot( en_step, states, 'v', color='b' )
        plt.plot(i, states[0], "v", color="b")
    plt.show()
