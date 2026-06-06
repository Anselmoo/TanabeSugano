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
    dq_bounds: tuple[float, float] = (500.0, 30000.0),
    b_bounds: tuple[float, float] = (200.0, 1200.0),
) -> tuple[float, float, float, float, list[tuple[float, str]]]:
    """Fit observed absorption peaks to find optimal Dq and B parameters."""

    # 1. Setup: convert inputs
    observed = np.asarray(observed_peaks_cm1, dtype=float)

    # 2. Strategy enclosure: define the objective function in a closure
    def objective(params: np.ndarray) -> float:
        dq, b = params
        # Bounds enforcement
        if dq < dq_bounds[0] or dq > dq_bounds[1]:
            return 1e6
        if b < b_bounds[0] or b > b_bounds[1]:
            return 1e6
        # Core computation
        try:
            terms = compute_point(d_count, dq, b, C)
            transitions = _extract_transition_energies(terms)
            predicted = np.array([t[0] for t in transitions])
            return _match_peaks(observed, predicted)
        except Exception:
            return 1e6

    # 3. Algorithm selection: explicit choice of Nelder-Mead
    initial_guess = np.array([5000.0, 600.0])
    result = minimize(
        objective,           # <-- Objective passed as callable
        initial_guess,
        method="Nelder-Mead",  # <-- Algorithm explicitly named
        options={"maxiter": 500, "xatol": 1e-2, "fatol": 1.0},
    )

    # 4. Extract results
    if not result.success:
        msg = f"Fitting failed to converge: {result.message}"
        raise ValueError(msg)

    fitted_dq, fitted_b = result.x
    # ... return fitted parameters
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
dq, b, c, rmse, transitions = fit_spectrum(observed_peaks, d_count)
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
2. **Forward model**: Compute the theoretical spectrum at this (dq, b)
3. **Fitness metric**: How close is the theoretical spectrum to observed?

```python
if dq < dq_bounds[0] or dq > dq_bounds[1]:
    return 1e6  # Penalty: out of bounds

try:
    terms = compute_point(d_count, dq, b, C)  # Forward model
    transitions = _extract_transition_energies(terms)
    predicted = np.array([t[0] for t in transitions])
    return _match_peaks(observed, predicted)  # Fitness
except Exception:
    return 1e6  # Penalty: computation failed
```

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
    dq, b, c, rmse, transitions = fit_spectrum(8, observed_peaks)

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
| **Readability counts** | `fit_spectrum(observed, d_count)` is clear; intent is obvious |
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
