# UV-Vis reference spectra

Reference absorption spectra for the spectrum-fitting examples. Each complex
ships as a **figure** (`.png`) and a **downloadable ASCII dataset** (`.txt`).
The figure shows the observed d-d absorption envelope of an octahedral Ni(II)
complex with the three spin-allowed bands assigned, plus the reference
ligand-field parameters (Dq, Racah B) and the nephelauxetic ratio
β = B(complex) / B(free ion).

| Complex | Figure / Data | Bands (cm⁻¹) | Dq | B | β |
|---|---|---|---|---|---|
| [Ni(H₂O)₆]²⁺ | `uvvis_fit_ni_aqua.png` / `.txt` | 8500, 13800, 25300 | 850 | 890 | 0.855 (weakly covalent) |
| [Ni(NH₃)₆]²⁺ | `uvvis_fit_ni_ammine.png` / `.txt` | 10800, 17500, 27800 | 1080 | 870 | 0.836 (moderately covalent) |

Band assignments (low → high energy):
³A₂g → ³T₂g, ³A₂g → ³T₁g(F), ³A₂g → ³T₁g(P).

## ASCII data format

Each `.txt` is a self-describing, tab-separated table with a commented (`#`)
header recording provenance, reference parameters, and band maxima:

```
# columns: wavenumber_cm-1    wavelength_nm    absorbance_au
4000.000000     2500.000000     0.015306
...
```

Load it with NumPy (the header lines are skipped automatically):

```python
import numpy as np
wn, wl, ab = np.loadtxt("uvvis_fit_ni_aqua.txt", comments="#", unpack=True)
```

## Regenerating

```bash
uv run python scripts/plot_uvvis_fits.py
```

## Sources

- Band maxima: Chemistry LibreTexts; Doc Brown's chemistry notes.
- Free-ion Racah B and reference parameters: A.B.P. Lever,
  *Inorganic Electronic Spectroscopy*, 2nd ed. (1984).
- These are the spectra the fitter is validated against in
  `src/tanabesugano/test/test_spectrum_fitting.py`.
