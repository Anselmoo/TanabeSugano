# JCE 2023 literature systems

Numeric transcription of Tables 1 and 2 of

> M. García Rojas and A. Pérez Torres, *J. Chem. Educ.* **2023**, 100, 251–258.
> DOI: [10.1021/acs.jchemed.2c00885](https://doi.org/10.1021/acs.jchemed.2c00885)

Transcribed 2026-11-24. Only numeric values (band positions, Dq, Dq/B, C/B), the term
labels as printed and the paper's own reference numbers are reproduced; no text,
figures or table layout. The "reported" parameters come from the primary sources the
paper cites (its refs 1–39), which are not resolved here.

| File | Content |
|---|---|
| `jce2023_table1_bands.csv` | Table 1: band positions with term labels; `approx=True` marks values printed with "~" |
| `jce2023_table2_parameters.csv` | Table 2: Dq and the `_reported` and `_graphical` Dq/B and C/B ratios |
| `jce2023_tables.json` | both tables, with citation and transcription notes |
| `extract_jce2023.py` | writes the three files above and re-checks every value against `pdftotext -layout` output of the paper (obtain the PDF yourself: `python3 extract_jce2023.py <paper.pdf> <outdir>`) |

`scripts/audit_fit_paths.py` uses only the `_reported` columns as references. The d5 and
d6 rows are flagged R1-tainted: published d5/d6 Tanabe–Sugano diagrams carry a
propagated error (Hormann & Shaw, *J. Chem. Educ.* **1987**, 64, 918), so those rows
serve as a comparison only.
