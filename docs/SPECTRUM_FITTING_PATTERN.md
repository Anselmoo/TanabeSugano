# Spectrum Fitting Pattern: Algorithm Selection + Lazy Optimization

## Problem Shape

Coordination chemists measure UV-Vis absorption spectra in the lab and want to extract ligand field parameters (Dq, B) that generated those spectra. This is an **inverse problem**: given output (observed peaks), find input (parameters).

The pattern must:
1. Select an appropriate optimization algorithm (many choices: Powell, BFGS, Nelder-Mead, etc.)
2. Defer computation until explicitly called (lazy evaluation)
3. Compose multiple sub-objectives (peak matching, bounds checking)
4. Return structured results with metadata

## Dogma: Algorithm Selection + Lazy Computation

### Pattern Classification

| Aspect | Classification |
|---|---|
| **Primary dogma** | Algorithm Selection (which optimizer?) |
| **Secondary dogma** | Lazy Computation (compute only on demand) |
| **Zen principle** | "Explicit is better than implicit" — the optimization is a distinct step, not hidden in initialization |
| **Python paradigm** | Callable-based dispatch (function passed to `scipy.optimize.minimize`) |

### Standard Variant (Factory Pattern)

In traditional GoF, you'd create an `OptimizerFactory` class:

```python
class OptimizerFactory:
    _optimizers = {
        'nelder_mead': lambda obj, x0: minimize(obj, x0, method='Nelder-Mead'),
        'bfgs': lambda obj, x0: minimize(obj, x0, method='BFGS'),
    }

    @staticmethod
    def create(method_name):
        return OptimizerFactory._optimizers[method_name]
```

**Problem**: Over-engineered for a single use case. Introduces indirection without benefit.

### Python-Specific Variant (Direct Callable)

Our implementation uses **Python's function-as-first-class-citizen** approach:

```python
def fit_spectrum(
    d_count: int,
    observed_peaks_cm1: list[float],
    C: float | None = None,
    *,
    spin_state: SpinState = "high",
    include_spin_forbidden: bool = False,
    dq_bounds: tuple[float, float] | None = None,
    b_bounds: tuple[float, float] = (200.0, 1500.0),
) -> SpectrumFit:
    """Fit observed absorption peaks to find optimal Dq and B parameters."""

    # 1. Refuse ill-posed inputs up front, loudly.
    #    High-spin d5 has ZERO spin-allowed d-d transitions; d4/d6 have exactly
    #    one (= 10Dq), so B is unidentifiable. Returning a number here would be
    #    a confident lie.
    if not seed_candidates:
        raise ValueError("... no spin-allowed d-d transitions ...")
    if len(seed_candidates) < observed.size:
        raise ValueError("... the fit is under-determined ...")

    # 2. Seed from physics, not from a constant. For d3/d8 the closed form
    #    Dq = nu1/10, B = (nu3 + nu2 - 3*nu1)/15 is exact, so the optimizer
    #    starts on the answer.
    dq_seed, b_seed = closed_form_dq_b(d_count, observed.tolist())

    # 3. Objective. Two rules make it honest:
    def objective(params: np.ndarray) -> float:
        dq, b = params
        # (a) The penalty is FINITE, scale-aware and sloped back toward the
        #     feasible box. A constant sentinel (the old `return 1e6`) makes the
        #     objective perfectly flat wherever nothing matches -- and
        #     Nelder-Mead reports success on a flat plateau, so the caller gets
        #     the untouched seed back with a sentinel RMSE and no error.
        if out_of_bounds:
            return base * (2.0 + excess)
        found_ground, candidates = transition_candidates(
            compute_point(d_count, dq, b, C),
            spin_allowed_only=not include_spin_forbidden,
        )
        # (b) Pin the spin regime. Low-spin manifolds are far denser (d5: 31
        #     lines vs 0), and a nearest-neighbour residual is minimised by a
        #     dense forest -- so an unconstrained search is *rewarded* for
        #     crossing the spin crossover into a physically wrong regime.
        if found_ground != reference:
            return base * 2.0
        # (c) Every observed peak contributes to BOTH numerator and denominator.
        #     The old metric gated on a 500 cm^-1 tolerance and divided by the
        #     matched count, so "match one peak, ignore the rest" scored 0.0.
        return peak_rmse(observed, np.array([e for e, _a, _s in candidates]))

    # 4. Multi-start, then REFUSE a result that never escaped the penalty region.
    #    `result.success` alone is not enough -- see (a).
    if result.fun >= base:
        raise ValueError("fit never escaped the penalty region ...")
```

## Why This Pattern?

### What Each Component Reveals

| Component | What It Reveals About Python |
|---|---|
| **Closure (`objective` function)** | Functions capture scope; the inner `objective` sees `observed`, `bounds`, `d_count`, `C` without explicit dependency injection |
| **Callable strategy** | Pass functions to `minimize()`; algorithm is parameterized without class hierarchy |
| **Lazy computation** | Optimization happens when `fit_spectrum()` is called, not at import time or in `__init__` |
| **Bounds enforcement in objective** | Constraints are embedded in the objective, not as separate constraint objects |

### Why Not a Class-Based Approach?

```python
# ❌ Over-engineered: Spectrum as a class
class Spectrum:
    def __init__(self, observed_peaks, d_count):
        self.observed_peaks = observed_peaks
        self.d_count = d_count
        self._optimizer = self._choose_optimizer()  # Premature commitment

    def _choose_optimizer(self):
        return "Nelder-Mead"  # Hardcoded; no flexibility

    def fit(self):
        # ... fitting logic

spectrum = Spectrum([...], 8)
result = spectrum.fit()
```

**Problems**:
- State bloat: instance holds both input and computed results
- Tight coupling: can't easily swap optimizers
- Unclear what triggers computation
- Over-abstracts a simple computation

### Why This Simple Function Works

```python
# ✓ Clean: Computation is a function
fit = fit_spectrum(d_count, observed_peaks)   # note: d_count FIRST
```

**Advantages**:
- Single responsibility: fit peaks → return parameters
- Lazy: only computes when called
- Testable: pure function (same input → same output)
- Composable: output directly feeds into downstream tools
- Flexible: caller chooses initial guess, bounds, C parameter

## Implementation Deep Dive

### Closure Captures Strategy State

```python
def objective(params: np.ndarray) -> float:
    dq, b = params
    # Closure sees these from parent scope:
    # - observed (input peaks)
    # - dq_bounds, b_bounds (constraints)
    # - d_count, C (configuration)
    # - compute_point() (helper function)
    ...
```

This is **Strategy without a class**: the objective function *is* the strategy. When `minimize()` calls `objective()`, it's executing the strategy defined by the closure.

### Sub-objectives Composed

The objective function chains three computations:

1. **Bounds check**: Is (dq, b) within allowed ranges?
2. **Spin-regime check**: Is this point still on the requested side of the crossover?
3. **Forward model**: Compute the theoretical spectrum at this (dq, b)
4. **Fitness metric**: How close is the theoretical spectrum to observed?

```python
# Graded, finite penalty -- never a constant. A constant makes the objective
# flat, and a flat objective makes Nelder-Mead "converge" without moving.
if excess > 0 or dq <= 0 or b <= 0:
    return base * (2.0 + excess)

try:
    terms = compute_point(d_count, dq, b, C)          # Forward model
    found_ground, candidates = transition_candidates(  # Ground term + spin filter
        terms, spin_allowed_only=not include_spin_forbidden,
    )
except (ValueError, KeyError, np.linalg.LinAlgError):
    return base * 3.0

if found_ground != reference or not candidates:
    return base * 2.0                                  # Wrong spin regime

return peak_rmse(observed, np.array([e for e, _a, _s in candidates]))  # Fitness
```

> **Three traps this shape exists to avoid**, each of which shipped in an
> earlier version of this file:
>
> 1. **Never normalise a residual by the number of peaks you managed to match.**
>    If unmatched peaks leave both the numerator and the denominator, ignoring
>    data becomes the global optimum and a one-of-three match scores 0.0.
> 2. **Never use a constant as an out-of-bounds penalty.** It flattens the
>    objective; `scipy` then reports `success=True` on the plateau and hands back
>    the untouched seed. A convergence guard on `result.success` will not fire.
> 3. **Never take the ground term from `next(iter(term_energies))`.** Dict order
>    is not energy order -- that expression names the wrong term for all seven
>    configurations. Derive it with `min()` over the energies, per point.

### Algorithm Selection Is Explicit

```python
result = minimize(
    objective,
    initial_guess,
    method="Nelder-Mead",  # <-- Algorithm explicitly chosen
    options={"maxiter": 500, "xatol": 1e-2, "fatol": 1.0},
)
```

To swap optimizers, change `method="Nelder-Mead"` to `method="BFGS"`, `method="Powell"`, etc. No factory class needed.

## When to Use This Pattern

### ✓ Use When:
- You have a **well-defined objective function** (minimize RMSE)
- **Algorithm choice is explicit** and not frequently swapped
- **Computation is expensive** enough to defer (lazy)
- Result can be returned as **simple data** (not a stateful object)
- You want **functional, testable code** with no hidden state

### ✗ Don't Use When:
- You need to **track state across multiple calls** (use a class)
- The objective function is **highly parameterized** (consider a class)
- You need **interactive progress updates** (requires polling/callbacks)
- Algorithm swapping is a **first-class use case** (use a factory)

## Validation: Test-Driven Documentation

The test suite (`test_spectrum_fitting.py`) documents the pattern in action:

### Test: Real Coordination Complex Data

```python
def test_nickel_aqua_complex(self) -> None:
    """Fit [Ni(H₂O)₆]²⁺ from literature absorption data.

    Literature:
        - Wavelengths: 450 nm (22,222 cm⁻¹), 700 nm (14,286 cm⁻¹)
        - Appears green: absorbs blue and red
    """
    observed_peaks = [10**7 / 450, 10**7 / 700]
    fit = fit_spectrum(8, observed_peaks)

    # Assertion: recovered parameters are physically sensible
    assert 4500 < dq < 6000, f"Dq={dq:.0f} unreasonable for aqua Ni²⁺"
    assert 500 < b < 800, f"B={b:.0f} unreasonable for Ni²⁺"
```

This test **documents that the pattern works**: given real UV-Vis data from the literature, the algorithm recovers sensible parameters. This is how pattern validity is proven—not through theory, but through real-world validation.

## Connection to Zen of Python

| Zen Principle | How This Pattern Honors It |
|---|---|
| **Explicit is better than implicit** | Algorithm choice is named in `method=` parameter; bounds are explicit in function signature |
| **Simple is better than complex** | A function is simpler than a factory + multiple optimizer classes |
| **Readability counts** | `fit_spectrum(d_count, observed)` is clear; intent is obvious |
| **Errors should never pass silently** | Exceptions from `compute_point()` are caught and penalized, but fitting still returns result |
| **There should be one way** | One function, one optimizer (Nelder-Mead), one algorithm selection mechanism |

## References

- **Pattern source**: [scipy.optimize.minimize documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.minimize.html)
- **Test documentation**: [test_spectrum_fitting.py](../src/tanabesugano/test/test_spectrum_fitting.py)
- **Real data source**: [Chemistry LibreTexts: Electronic Spectra of Coordination Compounds](https://chem.libretexts.org/Bookshelves/Inorganic_Chemistry/Inorganic_Chemistry_(LibreTexts)/11:_Coordination_Chemistry_III_-_Electronic_Spectra/11.03:_Electronic_Spectra_of_Coordination_Compounds)

## Dogma Summary

**Dogma**: Algorithm Selection + Lazy Computation

**Problem**: Find parameters that reproduce observed spectra

**Solution**: Closure-based objective function passed to scipy.optimize

**Why it works**: Python treats functions as first-class values; closures capture state without needing classes; `scipy` expects callables, not objects

**Cost**: Less flexible if you need frequent algorithm swaps (but explicit when you do swap)

**Benefit**: Clear, testable, composable, Pythonic
