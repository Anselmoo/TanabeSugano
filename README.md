[![Build Status](https://travis-ci.com/Anselmoo/TanabeSugano.svg?token=77iF1sqpzPpkXGuLWRs9&branch=master)](https://travis-ci.com/Anselmoo/TanabeSugano)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

# TanabeSugano
A python-based eigensolver for Tanabe-Sugano- & Energy-Correlation-Diagrams based on the original three proposed studies of *Yukito Tanabe and Satoru Sugano* for d<sup>3</sup>-d<sup>8</sup> transition metal ions:

1.  On the Absorption Spectra of Complex Ions. I
    
    **Yukito Tanabe, Satoru Sugano**  
    *Journal of the Physical Society of Japan*, 9, 753-766 (1954)  
    **DOI:** 10.1143/JPSJ.9.753  
    https://journals.jps.jp/doi/10.1143/JPSJ.9.753

2.  On the Absorption Spectra of Complex Ions II

    **Yukito Tanabe, Satoru Sugano**  
    *Journal of the Physical Society of Japan*, 9, 766-779 (1954)  
    **DOI:** 10.1143/JPSJ.9.766  
    https://journals.jps.jp/doi/10.1143/JPSJ.9.766
    
3.  On the Absorption Spectra of Complex Ions, III The Calculation of the Crystalline Field Strength

    **Yukito Tanabe, Satoru Sugano**  
    *Journal of the Physical Society of Japan*, 11, 864-877 (1956)  
    **DOI:** 10.1143/JPSJ.11.864  
    https://journals.jps.jp/doi/10.1143/JPSJ.11.864
    
It provides:

- Tanabe-Sugano- & Energy-Correlation-Diagrams plotted via `matplotlib`
- Tanabe-Sugano- & Energy-Correlation-Diagrams exported as `txt`-file
- Atomic-Termsymbols and their eigen-energies for a given 10Dq and oxidation state as exported table via `prettytable`
- Set-up individuall **C/B**-ratios
- Working with Slater-Condon-Parameters **F<sup>2</sup>, F<sup>4</sup>** instead of Racah-Parameters **B, C**

The **TanabeSugano**-application can be installed and run:

    python setup.py install
    python -m tanabe
