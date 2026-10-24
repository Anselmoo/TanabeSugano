# Determinant-basis oracle for `matrices.py`

**Verdict: the hand-written ligand-field matrices in `src/tanabesugano/matrices.py` are correct for
d2–d8.** Every level of every (S, Γ) block agrees with an independent full d^n calculation in the
Slater-determinant basis. The largest deviation over all configurations and parameter points is
2.3 × 10⁻¹⁰ cm⁻¹. The tolerance, 1 × 10⁻⁶ cm⁻¹, was fixed before the first comparison. Term labels
(multiplicity, A₁/A₂/E/T₁/T₂) and the number of levels per term agree everywhere. `matrices.py`
was not changed.

**d5 and d6 agree.** The error described by Hormann & Shaw (*J. Chem. Educ.* **1987**, 64, 918)
is therefore in the printed diagrams, not in this package. Rule R1 in CLAUDE.md (never validate a
d5/d6 fixture against a published TS *diagram*) stays.

No `IonFixture` in `test_ion_case_studies.py` changes.

## What was compared

| | Oracle (`test/_determinant_oracle.py`) | Package (`matrices.py`) |
|---|---|---|
| Basis | all C(10, n) determinants of the 10 d spin-orbitals, Condon–Shortley phases | one hand-written block per (S, Γ) |
| Repulsion | Slater–Condon in second quantisation; c^k from 3j symbols (Racah formula, exact integer factorials); F² = 49B + 7C, F⁴ = 63C/5 | closed expressions in B, C |
| Field | one-electron Oh operator in the complex m basis | Dq terms per basis function |
| Spin | S² = S₋S₊ + S_z² + S_z, sector M_S = S | implicit in the block |
| Symmetry | projectors P_Γ = (d_Γ/24) Σ χ_Γ(g) R(g) over the 24 rotations of O (generated from C4(z), C4(y), lifted to determinants as minors) | implicit in the block |

The oracle imports nothing from `tanabesugano` and copies no expression from `free_ion.py`. The
comparison calls only `matrices.d{n}(Dq, B, C).solver().as_dict()` (ground state at 0, cm⁻¹) and
compares the full multiset (multiplicity, irrep, E − E_ground).

**Points** (`TestPackageAgainstOracle::test_all_levels_match_at_every_point`, 112 per configuration):

- Dq = 0 (B = 900, C = 4000)
- 81 values of Dq from 0 to 4000 cm⁻¹ in steps of 50 (B = 900, C = 4000); every d4–d7 spin
  crossover falls between two grid points, without using the package's crossover routine
- 30 random points, Dq ∈ [0, 4000], B ∈ [400, 1200], C/B ∈ [3, 6] (seed 20261024)

**Maximum |package − oracle| per configuration (cm⁻¹):**

| d^n | blocks | levels | Dq = 0 | sweep (81) | random (30) |
|---|---|---|---|---|---|
| d2 | 7 | 11 | 5.1e-11 | 5.1e-11 | 4.4e-11 |
| d3 | 8 | 20 | 2.9e-11 | 8.7e-11 | 5.1e-11 |
| d4 | 12 | 43 | 4.4e-11 | 1.2e-10 | 1.5e-10 |
| d5 | 11 | 43 | 5.1e-11 | 1.5e-10 | 1.5e-10 |
| d6 | 12 | 43 | 6.5e-11 | 2.3e-10 | 2.2e-10 |
| d7 | 8 | 20 | 1.0e-10 | 1.6e-10 | 1.5e-10 |
| d8 | 7 | 11 | 7.3e-11 | 1.5e-10 | 1.7e-10 |

Tolerance 1e-6 cm⁻¹: `eigh` is backward stable, error O(dim·ε·‖H‖) ≈ 252 · 2.2e-16 · 1e5 ≈ 6e-9
cm⁻¹. Not read off the implementation.

## Self-validation of the oracle (before any comparison)

Each test was observed red against a deliberately broken oracle; the observed text is in its
docstring.

| Check | Source of the expected value | Mutation that turned it red |
|---|---|---|
| eg +6Dq (×2), t2g −4Dq (×3) | definition of Dq | ⟨2\|V\|−2⟩ = 3Dq |
| O: 24 elements, classes 1/8/3/6/6, unitary, [D, V] = 0 | character table of O | C4(y) at π/3 → `generated 29 rotations, expected 24` |
| χ(D²) = χ(E) + χ(T₂) | character table of O | T₁/T₂ characters swapped |
| d2 at Dq = 0: 3P 15B, 1D 5B+2C, 1G 12B+2C, 1S 22B+7C above 3F, with Oh labels | Racah's d2 terms (textbook) | F⁴ = 63C/7 |
| B = C = 0: levels −4p + 6q with C(6,p)·C(4,q) states | counting | m = 0 diagonal of V = 5Dq |
| d^n(Dq) = d^(10−n)(−Dq), d5 onto itself | particle–hole conjugation | field × 1.01 for n < 5 |
| block levels × (2S+1)·d_Γ = full C(10, n) spectrum; [H, S²] = 0 | `math.comb(10, n)`, unprojected H | S² window shifted → `assert 0 == 45` |
| second opinion: oracle at Dq = 0 = `free_ion.py`, d2–d8 | `free_ion.py`, read only after the textbook check | F⁴ = 63C/7 |

The `free_ion.py` check validates the oracle, not the solver; the solver's free-ion assertions stay
in `test_matrices_invariants.py`.

## Mutation check (valid red for the comparison)

In the patched solver class one off-diagonal element in one block is negated. The test first
checks that the element is a non-zero multiple of B alone (independent of Dq and C, linear in B);
the comparison must then fail and name exactly that block as the worst term.

| Mutation | observed report (worst first) |
|---|---|
| d4 ³T₁ (0,1) = −√6·B | `d4 3_T_1: max deviation 2.06e+03 cm^-1; d4 1_E: max deviation 270 cm^-1; ...` |
| d5 ²T₂ (0,1) = 3√6·B | `d5 2_T_2: max deviation 5.79e+03 cm^-1; d5 2_T_1: max deviation 619 cm^-1; ...` |
| d6 ¹T₂ (1,2) = −5√3·B | `d6 1_T_2: max deviation 9.51e+03 cm^-1` |

In d4 and d5 other terms move too: the broken block becomes the ground state at some points and
shifts the zero point of every term.

## Files, runtime

- `src/tanabesugano/test/_determinant_oracle.py`: the oracle, no package imports
- `src/tanabesugano/test/test_determinant_oracle.py`: 42 tests (self-validation, comparison,
  mutation check), about 3 s, no `slow` marker needed

## Limits

- The spectrum per (S, Γ) is checked; the choice of basis inside a block is not (it does not
  affect energies). Eigenvectors and parentage (`levels.py`) are outside this comparison.
- Dq < 0 is checked only inside the oracle (hole equivalence), not against the package.
- Spin–orbit coupling is in neither the package nor the oracle.
