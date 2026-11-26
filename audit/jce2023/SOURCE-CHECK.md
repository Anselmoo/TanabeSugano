# JCE 2023 Tables 1/2 against the original sources (checked 2026-11-25)

Source PDFs read: 18 of 40 refs. Text layer via pdftotext; TS 1954 (ref 1) via
OCR, key numbers confirmed on the rendered page. "calc" = a value the original lists as calculated.

## Differences between the JCE tables and the original sources

| System | JCE | Original | Consequence |
|---|---|---|---|
| MnI2, MnBr2, MnCl2, MnF2, [Mn(H2O)6]2+ (ref 30, Foster & Gill 1968, Table 2) | bands e.g. [Mn(H2O)6]2+ 19070/22710/24500 | these are the **calc** columns; observed 18870/23120/24960 (MnF2 obs 19440/23500/25200, MnCl2 18900/22220/23870, MnBr2 18800/21930/23420, MnI2 18180/21110/22420). Parameters (Table 3: Δ, B, C) match JCE | bands are model output at the published (Dq, B, C): a fit at the reported point is exact by construction. At [Mn(H2O)6]2+'s published Dq 760, B 827.9, C 3242.8 the determinant oracle gives 19064.422/22706.212/24493.000, reproducing the calc column to 5.6 cm-1 RMS (max 7.0); against the observed column the RMS is 377.3. ts-mcp-bench Study 1 tasks for MnBr2, MnCl2, MnF2, [Mn(H2O)6]2+ state these as observed bands |
| LiGa5O8:Fe3+ (ref 15, Neto 1981) | 18349/21505/24627/27036 | table headed "Calculated values"; observed (Table 1) 18350, 21510 (4c), 24630 (3c), 26870 | same as above |
| CoSiF6·6H2O (ref 35, Srivastava 1971) | 8480/16305/20360/21001 | **calc** column; observed 9042 (and 8437), 16221, 20359, 21487/21739 | 4T2 off by ~560 cm-1; ts-mcp-bench C-literature_all-15 uses these |
| [Mn(CN)6]3- (ref 29, Alexander & Gray 1968) | 31100 listed as d-d band E(3E) | 31100 assigned as **charge transfer** (t1u -> t2g); 33150 as 3T1g -> 3Eg/3A1g; parameters Δ 34000, B 660, C 3280 match JCE | a CT band is fitted as d-d |
| [Cr(NH3)6]3+ (refs 1, 7) | Dq 2170, Dq/B 3.303 | Shriver & Atkins 5th ed., Example 20.8: bands 21550/28500, Δ/B = 33.0 read off the TS diagram, B 657, Δ 21700 (graphical). Tanabe & Sugano 1954: Dq = 2140. In the model nu1 = 10Dq = 21550 | JCE copies a textbook graphical estimate; the model-consistent Dq is 2155 |
| K3Cr(CN)6 (ref 29) | Dq/B 5.542 (B 480), C/B 5.563 | Δ 26600, B 485, C 2800 (12820 is an emission line) | C/B 5.77, not 5.563 |
| [Co(NH3)6]3+ Table 2 (refs 20, 31) | Dq 2293, Dq/B 3.611, C/B 6.121 | Yarranton 2022: diagonal 10Dq 24760, B 475, C 3710; full 23430, B 580, C 3550 | neither row; probably ref 31 (Riordan, not checked) |

## Consistent, but derived in a way the reference must say

| System | Note |
|---|---|
| MgO:Ni2+ (ref 24, Pappalardo 1961) | Dq 815 = nu1 (8010) + predicted spin-orbit stabilisation, stated as an upper limit; **C/B = 4.4 is assumed**, not fitted; the 1E "≈13670" is not a separate observed band (1E expected strongly mixed with 3T1a, absorption starts at 13700). Our model has no spin-orbit coupling: nu1/10 = 801 is the model-consistent Dq |
| [Cr(H2O)6]3+ (ref 1) | TS Dq 1720 fitted to KCr(SO4)2·12H2O crystal bands 18.0/24.6/36.6 kK with C/B (γ) = 4.0; JCE pairs it with solution bands 17400/24700 |
| [Ni(NH3)6]2+ (ref 1) | TS Dq 1030 with B, C taken over from [Ni(H2O)6]2+; obs nu1 10.6 kK (calc 10.3) |
| [V(H2O)6]2+ (ref 3, König 1971) | B 633 = König method (c), sum of 2nd + 3rd band; methods (a)/(b) give 693/596 |
| [Cr(oxalate)3]3- (ref 22, Yager 1979) | Δ 17500, B 660 read off a TS diagram |
| Al2O3:Cr3+ (ref 21) | bands from nm: 551 -> 18149, 407 -> 24570; 694.2 nm -> 14405 (JCE 14420) |
| [V(H2O)6]3+ (ref 28, Hitchman 1988) | gives trigonally split crystal bands (17300/19500, 25300/27800, AOM, B 644), not the JCE 17200/25600 |

## Confirmed as printed

KZnClSO4·3H2O:Cr3+ (ref 14: Dq 1724, B 724, C 2484), AgCl:Co2+ and AgCl:Ni2+ (ref 33: 680/790/3320,
670/805/3130), CoCl2 and KCoF3 bands (ref 34), Co(bipy)3Br2·6H2O (ref 36: Dq 1267, B 791),
LiGa5O8:Ni2+ (ref 38: obs 9770/12987/16050/26740; 977/900/3150), [Ni(H2O)6]2+ Table 2 (ref 39:
860/940/4.1B), [Co(NH3)6]3+ Table 1 triplets (ref 32: 13.4, (17.23) kK), LiGa5O8:Fe3+ parameters
(ref 15: B 594, C 3737), ZnO:Ni2+ Dq 405 and B 795 (ref 24, Td site).

## Figgis & Hitchman 2000 (ref 27), Section 8.2, OCR

| System | Book | JCE |
|---|---|---|
| [NiF6]4- | bands 7400, 12660, 23840; shoulders 15150 and 21275 (spin-forbidden); Δ 7400, Δ/B 7.8 graphical, B 950 | match (21275 not listed) |
| [V(H2O)6]3+ | bands 17200, 25600 (aqueous); Δ 18600, B 665 from the TS diagram | match |
| [Co(H2O)6]2+ | bands 8100, 19400, shoulder 21600 (doublet); 19400 assigned to 4T1(P), 4A2 (~16000) not observed; Δ 9200, B 850 | match |

All three parameter sets are read off TS diagrams (graphical), not least-squares fits.

## Shriver & Atkins 5th ed. (ref 7)
Table 20.1: Δ(Cr3+, H2O) 17400, Δ(Cr3+, NH3) 21500; Example 20.8 as in the table above.

## Not checked (sources not supplied)
Refs 25 (Pontnau & Adde: title is about Cr2+/Cr4+, cited for V3+ and Cr3+ in Al2O3), 26 and 37
(Jørgensen 1955), 31 (Riordan 2005), book 11 (Sugano, Tanabe, Kamimura 1970).
