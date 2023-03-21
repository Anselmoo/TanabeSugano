[![Python package](https://github.com/Anselmoo/TanabeSugano/workflows/Python%20package/badge.svg)](https://github.com/Anselmoo/TanabeSugano/actions?query=workflow%3A%22Python+package%22)
[![CodeFactor](https://www.codefactor.io/repository/github/anselmoo/tanabesugano/badge)](https://www.codefactor.io/repository/github/anselmoo/tanabesugano)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.4430571.svg)](https://doi.org/10.5281/zenodo.4430571)
[![GitHub](https://img.shields.io/github/license/Anselmoo/TanabeSugano)](https://github.com/Anselmoo/TanabeSugano/blob/master/LICENSE)
[![GitHub release (latest by date including pre-releases)](https://img.shields.io/github/v/release/Anselmoo/TanabeSugano?include_prereleases)](https://github.com/Anselmoo/TanabeSugano/releases)
[![PyPI](https://img.shields.io/pypi/v/TanabeSugano?logo=Pypi&logoColor=yellow)](https://pypi.org/project/TanabeSugano/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/TanabeSugano?logo=Python&logoColor=yellow)](https://pypi.org/project/TanabeSugano/)

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
- Atomic-Termsymbols and their **Eigen-Energies** for a given 10Dq and oxidation state as exported table via `prettytable`
- Set-up individually **C/B**-ratios
- Working with Slater-Condon-Parameters **F<sup>2</sup>, F<sup>4</sup>** instead of Racah-Parameters **B, C**
- Export of the **Tanabe-Sugano-Diagram** as a `html`-file via `plotly` for interactive use

The **TanabeSugano**-application can be installed and run:

```console
    # via PyPi
    pip install TanabeSugano

    # via pip+git
    pip git+https://github.com/Anselmoo/TanabeSugano.git

    # locally
    python setup.py install
    tanabesugano

    # for plotly-export
    pip install TanabeSugano[plotly]
```


The options for the **TanabeSugano**-application are:

```console
    tanabesugano --help

    usage: __main__.py [-h] [-d D] [-Dq DQ] [-cut CUT] [-B B B] [-C C C] [-n N]
                   [-ndisp] [-ntxt] [-slater]

    optional arguments:
    -h, --help     show this help message and exit
    -d D           Number of unpaired electrons (default d5)
    -Dq DQ         10Dq crystal field splitting (default 10Dq = 8065 cm-)
    -cut CUT       10Dq crystal field splitting (default 10Dq = 8065 cm-)
    -B B B         Racah Parameter B and the corresponding reduction (default B = 860 cm- * 1.)
    -C C C         Racah Parameter C and the corresponding reduction (default C = 4.477*860 cm- * 1.)
    -n N           Number of roots (default nroots = 500)
    -ndisp         Plot TS-diagram (default = on)
    -ntxt          Save TS-diagram and dd energies (default = on)
    -slater        Using Slater-Condon F2,F4 parameter instead Racah-Parameter B,C (default = off)
    -v, --version  Print version number and exit
    -html          Save TS-diagram and dd energies (default = on)
```

**Reference-Example** for d<sup>6</sup> for *B = 860 cm<sup>-</sup>* and *C = 3850 cm<sup>-</sup>* as regular `matplotlib`-plot:
![placeholder](https://github.com/Anselmoo/TanabeSugano/blob/master/examples/dd-diagram_for_d6.png?raw=true)


**Reference-Example** for d<sup>6</sup> for *F<sup>2</sup> = 860 cm<sup>-</sup>* and *F<sup>4</sup> = 3850 cm<sup>-</sup>* as interactive `plotly`-plot:

![placeholder](https://github.com/Anselmoo/TanabeSugano/blob/feature/readme/examples/d6_ts_interactive.gif?raw=true)
