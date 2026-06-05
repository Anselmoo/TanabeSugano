# UV-Vis reference spectra

Reference absorption spectra for the spectrum-fitting examples. Each figure
shows the observed d-d absorption envelope of an octahedral Ni(II) complex with
the three spin-allowed bands assigned, plus the reference ligand-field
parameters (Dq, Racah B) and the nephelauxetic ratio β = B(complex) / B(free ion).

| File | Complex | Bands (cm⁻¹) | Dq | B | β |
|---|---|---|---|---|---|
| `uvvis_fit_ni_aqua.png` | [Ni(H₂O)₆]²⁺ | 8500, 13800, 25300 | 850 | 890 | 0.855 (weakly covalent) |
| `uvvis_fit_ni_ammine.png` | [Ni(NH₃)₆]²⁺ | 10800, 17500, 27800 | 1080 | 870 | 0.836 (moderately covalent) |

Band assignments (low → high energy):
³A₂g → ³T₂g, ³A₂g → ³T₁g(F), ³A₂g → ³T₁g(P).

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
