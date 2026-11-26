"""Transcribe Tables 1 and 2 of García Rojas & Pérez Torres, J. Chem. Educ. 2023, 100, 251-258
(DOI 10.1021/acs.jchemed.2c00885) into JSON and CSV.

Values were typed from the PDF; column placement of rows with empty cells was checked against the
rendered page (pages 2 and 4). The script then re-checks every row against `pdftotext -layout`
output: each row's numbers must appear on the source line in the same order, else it aborts.

Table 2 "graphical" values are the authors' readings from their auxiliary TS diagrams (steps
0.05 in Dq/B, 0.25 in C/B); they are not literature values.

Usage: python3 extract_jce2023.py <paper.pdf> <outdir>
"""
import csv, json, re, subprocess, sys
from pathlib import Path

pdf, out = Path(sys.argv[1]), Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
text = subprocess.run(["pdftotext", "-layout", str(pdf), "-"], capture_output=True, text=True, check=True).stdout

N = None  # empty cell
# Table 1: block -> (header labels as printed, rows). Label "o^mI": ordinal, multiplicity, irrep; "^3E" has no ordinal printed.
T1 = {
 "d2(Oh)/d8(Td)": (["1^3T2", "2^3T1", "1^3A2", "1^1E"], [
   ("ZnO:Ni2+", [4400, 15500, N, N], "ref 24"),
   ("Al2O3:V3+", [17500, 25000, N, 9748], "ref 25"),
   ("[V(H2O)6]3+", [17200, 25600, N, N], "refs 26-28")]),
 "d3(Oh)/d7(Td)": (["1^4T2", "1^4T1", "2^4T1", "1^2E"], [
   ("[V(H2O)6]2+", [12300, 18500, 27900, N], "ref 3"),
   ("[Cr(H2O)6]3+", [17400, 24700, "~36600", 14800], "refs 1,26"),
   ("KZnClSO4·3H2O:Cr3+", [17235, 24385, N, 11975], "ref 14"),
   ("[Cr(oxalate)3]3-", [17500, 23800, N, 14300], "ref 22"),
   ("Al2O3:Cr3+", [18149, 24570, N, 14420], "refs 11,21,25"),
   ("[Cr(NH3)6]3+", [21550, 28500, N, 15200], "refs 1,7"),
   ("K3Cr(CN)6", [26600, 32500, N, 12820], "ref 29")]),
 "d4(Oh)/d6(Td)": (["^3E", "^3A1", "1^1T2", "1^1A1"], [
   ("[Mn(CN)6]3-", [31100, 33150, N, 21000], "ref 29")]),
 "d5(Oh,Td)": (["1^4T1", "1^4T2", "1^4E", "2^4T2"], [
   ("MnI2", [18450, 20960, 22000, N], "ref 30"),
   ("MnBr2", [19240, 21890, 23000, N], "ref 30"),
   ("MnCl2", [19180, 22130, 23370, N], "ref 30"),
   ("MnF2", [19720, 23260, 24980, N], "ref 30"),
   ("[Mn(H2O)6]2+", [19070, 22710, 24500, N], "ref 30"),
   ("LiGa5O8:Fe3+", [18349, 21505, 24627, 27036], "ref 15")]),
 "d6(Oh)/d4(Td)": (["1^1T1", "1^1T2", "1^3T1", "1^3T2"], [
   ("[Co(oxalate)3]3-", [16611, 23529, N, N], "ref 31"),
   ("[Co(H2O)6]3+", [16474, 25381, N, N], "refs 26,31"),
   ("[Co(NH3)6]3+", [21053, 29499, 13400, 17230], "refs 31,32"),
   ("[Co(NO2)6]3-", [27397, 34483, N, N], "ref 31")]),
 "d7(Oh)/d3(Td)": (["1^4T2", "1^4A2", "2^4T1", "2^2T1"], [
   ("AgCl:Co2+", [6150, 12400, 16850, 19000], "ref 33"),
   ("CoCl2", [6600, 13300, 17150, 19030], "ref 34"),
   ("KCoF3", [7150, 15200, 19200, 21130], "ref 34"),
   ("[Co(H2O)6]2+", [8100, N, 19400, 21600], "ref 27"),
   ("CoSiF6·6H2O", [8480, 16305, 20360, 21001], "ref 35"),
   ("Co(bipy)3Br2·6H2O", [11300, N, 22000, 18500], "ref 36")]),
 "d8(Oh)/d2(Td)": (["1^3T2", "1^3T1", "2^3T1", "1^1E"], [
   ("AgCl:Ni2+", [6680, 11250, 20920, 12470], "ref 33"),
   ("[NiF6]4-", [7400, 12660, 23840, 15150], "ref 27"),
   ("MgO:Ni2+", [8010, 13670, 24070, "~13670"], "ref 24"),
   ("[Ni(H2O)6]2+", [8500, 13500, 25300, 15400], "refs 26,37"),
   ("LiGa5O8:Ni2+", [9770, 16050, 26740, 12987], "ref 38"),
   ("[Ni(NH3)6]2+", [10600, 17500, 27600, N], "ref 1")]),
}
# Table 2: Dq, Dq/B reported (graphical), C/B reported (graphical); see the module docstring.
T2 = [
 ("d2(Oh)/d8(Td)", "ZnO:Ni2+", 405, "0.509", "0.60", N, N, "ref 24"),
 ("d2(Oh)/d8(Td)", "Al2O3:V3+", 1823, "3.198", "3.20", "4.561", "5.00", "ref 25"),
 ("d2(Oh)/d8(Td)", "[V(H2O)6]3+", 1860, "2.8", "2.80", N, N, "ref 27"),
 ("d3(Oh)/d7(Td)", "[V(H2O)6]2+", 1230, "1.942", "1.95", N, N, "ref 3"),
 ("d3(Oh)/d7(Td)", "[Cr(H2O)6]3+", 1720, "2.248", "2.35", "4", "4.25", "ref 1"),
 ("d3(Oh)/d7(Td)", "KZnClSO4·3H2O:Cr3+", 1724, "2.381", "2.40", "3.431", "3.13", "ref 14"),
 ("d3(Oh)/d7(Td)", "[Cr(oxalate)3]3-", 1750, "2.652", "2.85", N, "5.25", "ref 22"),
 ("d3(Oh)/d7(Td)", "Al2O3:Cr3+", 1810, "2.785", "2.95", "4.800", "5.25", "ref 25"),
 ("d3(Oh)/d7(Td)", "[Cr(NH3)6]3+", 2170, "3.303", "3.30", N, "5.25", "refs 1,7"),
 ("d3(Oh)/d7(Td)", "K3Cr(CN)6", 2660, "5.542", "5.10", "5.563", "5.50", "ref 29"),
 ("d4(Oh)/d6(Td)", "[Mn(CN)6]3-", 3400, "5.152", "6.20", "4.970", "6.00", "ref 29"),
 ("d5(Oh,Td)", "MnI2", 550, "0.798", "0.75", "4.386", "4.00", "ref 30"),
 ("d5(Oh,Td)", "MnBr2", 580, "0.804", "0.75", "4.380", "4.00", "ref 30"),
 ("d5(Oh,Td)", "MnCl2", 620, "0.805", "0.80", "4.068", "4.00", "ref 30"),
 ("d5(Oh,Td)", "MnF2", 750, "0.909", "0.90", "4.068", "4.00", "ref 30"),
 ("d5(Oh,Td)", "[Mn(H2O)6]2+", 760, "0.918", "0.95", "3.917", "4.00", "ref 30"),
 ("d5(Oh,Td)", "LiGa5O8:Fe3+", 906, "1.525", "1.50", "6.289", "6.25", "ref 15"),
 ("d6(Oh)/d4(Td)", "[Co(oxalate)3]3-", 1815, "3.389", "3.45", N, N, "ref 31"),
 ("d6(Oh)/d4(Td)", "[Co(H2O)6]3+", 1841, "2.611", "2.55", N, N, "ref 31"),
 ("d6(Oh)/d4(Td)", "[Co(NH3)6]3+", 2293, "3.611", "3.65", "6.121", "5.63", "refs 20,31"),
 ("d6(Oh)/d4(Td)", "[Co(NO2)6]3-", 2900, "6.611", "5.85", N, N, "ref 31"),
 ("d7(Oh)/d3(Td)", "AgCl:Co2+", 680, "0.861", "0.90", "4.203", "4.75", "ref 33"),
 ("d7(Oh)/d3(Td)", "CoCl2", 690, "0.885", "0.95", "4.40", "4.63", "ref 34"),
 ("d7(Oh)/d3(Td)", "KCoF3", 770, "0.875", "0.90", "4.40", "4.50", "ref 34"),
 ("d7(Oh)/d3(Td)", "[Co(H2O)6]2+", 920, "1.082", "1.10", N, "5.00", "ref 27"),
 ("d7(Oh)/d3(Td)", "CoSiF6·6H2O", 965, "1.109", "1.10", "4.5", "4.50", "ref 35"),
 ("d7(Oh)/d3(Td)", "Co(bipy)3Br2·6H2O", 1267, "1.602", "1.55", N, "4.00", "ref 36"),
 ("d8(Oh)/d2(Td)", "AgCl:Ni2+", 670, "0.832", "0.80", "3.888", "3.75", "ref 33"),
 ("d8(Oh)/d2(Td)", "[NiF6]4-", 740, "0.78", "0.80", N, "4.50", "ref 27"),
 ("d8(Oh)/d2(Td)", "MgO:Ni2+", 815, "0.916", "0.90", "4.4", "4.00", "ref 24"),
 ("d8(Oh)/d2(Td)", "[Ni(H2O)6]2+", 860, "0.915", "0.90", "4.1", "4.50", "ref 39"),
 ("d8(Oh)/d2(Td)", "LiGa5O8:Ni2+", 977, "1.086", "1.05", "3.500", "3.25", "ref 38"),
 ("d8(Oh)/d2(Td)", "[Ni(NH3)6]2+", 1030, N, "1.20", N, N, "ref 1"),
]

lines = text.splitlines()
def tokens(line):
    """Return the numeric tokens of one pdftotext line, keeping a leading ≈."""
    return re.findall(r"≈?\d+(?:\.\d+)?", line)
def check(name, expected):
    """Abort unless some PDF line naming ``name`` carries ``expected`` in order."""
    exp = [str(v).replace("~", "≈") for v in expected if v is not None]
    key = name.replace("-", "−")[:6]
    for ln in lines:
        if key in ln:
            it = iter(tokens(ln))
            if all(any(e == t for t in it) for e in exp):
                return
    sys.exit(f"CHECK FAILED: {name} {exp}")
for blk, (_, rows) in T1.items():
    for n, vals, _ in rows:
        check(n, vals)
for r in T2:
    check(r[1], [r[2], r[3], r[4], r[5], r[6]])
assert sum(len(r) for _, r in T1.values()) == 33 and len(T2) == 33

def term(lbl):
    """Split a printed term label like ``2^3T1`` into ordinal, multiplicity and irrep."""
    m = re.fullmatch(r"(\d)?\^(\d)([ATE]\d?)", lbl)
    return {"printed": f"E({lbl})", "ordinal": int(m[1]) if m[1] else None, "multiplicity": int(m[2]), "irrep": m[3]}
def num(v):
    """Return ``(value, approx)`` for a cell; ``~`` marks an approximate value."""
    if v is None: return None, False
    if isinstance(v, str) and v.startswith("~"): return float(v[1:]), True
    return float(v), False

source = {"citation": "García Rojas, V.; Pérez Torres, J. F. Derivation of Dq/B and C/B from Electronic Spectra of Transition Metal Ions in Cubic Fields Using Auxiliary Tanabe–Sugano Diagrams. J. Chem. Educ. 2023, 100, 251-258",
          "doi": "10.1021/acs.jchemed.2c00885",
          "transcribed": "2026-11-24, from the PDF; checked against pdftotext -layout and the rendered pages",
          "notes": ["Wavenumbers in cm-1; term labels as printed (cubic, no g subscript); '^3E' carries no ordinal in the source.",
                    "approx=true marks values printed with ≈.",
                    "Table 2 'reported' values come from the cited original works; 'graphical' values are the authors' readings from auxiliary TS diagrams.",
                    "refs are the paper's own reference numbers, not resolved citations.",
                    "Text example (p. 4) gives a 17330 cm-1 band for [Co(H2O)6]2+ that Table 1 does not list."]}
t1 = []
for blk, (hdr, rows) in T1.items():
    for n, vals, ref in rows:
        bands = []
        for h, v in zip(hdr, vals):
            x, ap = num(v)
            if x is not None:
                bands.append({**term(h), "wavenumber_cm1": x, "approx": ap})
        t1.append({"block": blk, "system": n, "bands": bands, "refs": ref})
f = lambda s: None if s is None else float(s)
t2 = [{"block": b, "system": n, "Dq_cm1": float(dq), "Dq_over_B_reported": f(r1), "Dq_over_B_graphical": f(g1),
       "C_over_B_reported": f(r2), "C_over_B_graphical": f(g2), "refs": ref} for b, n, dq, r1, g1, r2, g2, ref in T2]
(out / "jce2023_tables.json").write_text(json.dumps({"source": source, "table1": t1, "table2": t2}, ensure_ascii=False, indent=1) + "\n")

with open(out / "jce2023_table1_bands.csv", "w", newline="") as fh:
    w = csv.writer(fh); w.writerow(["block", "system", "band_col", "term_printed", "ordinal", "multiplicity", "irrep", "wavenumber_cm1", "approx", "refs"])
    for blk, (hdr, rows) in T1.items():
        for n, vals, ref in rows:
            for i, (h, v) in enumerate(zip(hdr, vals), 1):
                x, ap = num(v)
                if x is None: continue
                t = term(h); w.writerow([blk, n, i, t["printed"], t["ordinal"] or "", t["multiplicity"], t["irrep"], int(x), ap, ref])
with open(out / "jce2023_table2_parameters.csv", "w", newline="") as fh:
    w = csv.writer(fh); w.writerow(list(t2[0].keys()))
    for r in t2: w.writerow(["" if v is None else v for v in r.values()])
print("ok", len(t1), len(t2))
