![Python package](https://github.com/Anselmoo/TanabeSugano/workflows/Python%20package/badge.svg)
[![CodeFactor](https://www.codefactor.io/repository/github/anselmoo/tanabesugano/badge)](https://www.codefactor.io/repository/github/anselmoo/tanabesugano)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.3403688.svg)](https://doi.org/10.5281/zenodo.3403688)
[![GitHub](https://img.shields.io/github/license/Anselmoo/TanabeSugano)](https://github.com/Anselmoo/TanabeSugano/blob/master/LICENSE)
[![GitHub release (latest by date including pre-releases)](https://img.shields.io/github/v/release/Anselmoo/TanabeSugano?include_prereleases)](https://github.com/Anselmoo/TanabeSugano/releases)



# TanabeSugano
A python-based Eigensolver for Tanabe-Sugano- & Energy-Correlation-Diagrams based on the original three proposed studies of *Yukito Tanabe and Satoru Sugano* for d<sup>2</sup>-d<sup>8</sup> transition metal ions:

1. On the Absorption Spectra of Complex Ions. I

    **Yukito Tanabe, Satoru Sugano**
    *Journal of the Physical Society of Japan*, 9, 753-766 (1954)
    **DOI:** 10.1143/JPSJ.9.753
    https://journals.jps.jp/doi/10.1143/JPSJ.9.753

2. On the Absorption Spectra of Complex Ions II

    **Yukito Tanabe, Satoru Sugano**
    *Journal of the Physical Society of Japan*, 9, 766-779 (1954)
    **DOI:** 10.1143/JPSJ.9.766
    https://journals.jps.jp/doi/10.1143/JPSJ.9.766

3. On the Absorption Spectra of Complex Ions, III The Calculation of the Crystalline Field Strength

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

    ```console
    #via PyPi
    pip install TanabeSugano
    
    #via pip+git
    pip git+https://github.com/Anselmoo/TanabeSugano.git
    
    # Via local
    python setup.py install
    python -m tanabe
    ```


The options of the **TanabeSugano**-application are:

    ```console
    python -m tanabe --help

    usage: __main__.py [-h] [-d D] [-Dq DQ] [-cut CUT] [-B B B] [-C C C] [-n N]
                   [-ndisp] [-ntxt] [-slater]

    optional arguments:
    -h, --help  show this help message and exit
    -d D        Number of unpaired electrons (default d5)
    -Dq DQ      10Dq crystal field splitting (default 10Dq = 8065 cm-)
    -cut CUT    10Dq crystal field splitting (default 10Dq = 8065 cm-)
    -B B B      Racah Parameter B and the corresponding reduction (default B = 860 cm- * 1.)
    -C C C      Racah Parameter C and the corresponding reduction (default C = 4.477*860 cm- * 1.)
    -n N        Number of roots (default nroots = 500)
    -ndisp      Plot TS-diagram (default = on)
    -ntxt       Save TS-diagram and dd energies (default = on)
    -slater     Using Slater-Condon F2,F4 parameter instead Racah-Parameter B,C (default = off)
    ```    

**Reference-Example** for d<sup>6</sup> for *B = 860 cm<sup>-</sup>* and *C = 3850 cm<sup>-</sup>*:
![alt text-1](https://github.com/Anselmoo/TanabeSugano/blob/master/examples/TanabeSugano-diagram4d6.png "title-1")
