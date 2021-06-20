# -*- coding: utf-8 -*-
from setuptools import setup

packages = ["tanabesugano"]

package_data = {"": ["*"]}

install_requires = [
    "matplotlib>=3.4.2,<4.0.0",
    "numpy>=1.20.3,<2.0.0",
    "pandas>=1.2.4,<2.0.0",
    "prettytable>=2.1.0,<3.0.0",
]

setup_kwargs = {
    "name": "tanabesugano",
    "version": "1.2.0",
    "description": "A python-solver for Tanabe-Sugano and Energy-Correlation diagrams",
    "long_description": "[![Python package](https://github.com/Anselmoo/TanabeSugano/workflows/Python%20package/badge.svg)](https://github.com/Anselmoo/TanabeSugano/actions?query=workflow%3A%22Python+package%22)\n[![CodeFactor](https://www.codefactor.io/repository/github/anselmoo/tanabesugano/badge)](https://www.codefactor.io/repository/github/anselmoo/tanabesugano)\n[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.4430571.svg)](https://doi.org/10.5281/zenodo.4430571)\n[![GitHub](https://img.shields.io/github/license/Anselmoo/TanabeSugano)](https://github.com/Anselmoo/TanabeSugano/blob/master/LICENSE)\n[![GitHub release (latest by date including pre-releases)](https://img.shields.io/github/v/release/Anselmoo/TanabeSugano?include_prereleases)](https://github.com/Anselmoo/TanabeSugano/releases)\n[![PyPI](https://img.shields.io/pypi/v/TanabeSugano?logo=Pypi&logoColor=yellow)](https://pypi.org/project/TanabeSugano/)\n[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/TanabeSugano?logo=Python&logoColor=yellow)](https://pypi.org/project/TanabeSugano/)\n\n# TanabeSugano\nA python-based Eigensolver for Tanabe-Sugano- & Energy-Correlation-Diagrams based on the original three proposed studies of *Yukito Tanabe and Satoru Sugano* for d<sup>2</sup>-d<sup>8</sup> transition metal ions:\n\n1. On the Absorption Spectra of Complex Ions. I\n\n    **Yukito Tanabe, Satoru Sugano**\n    *Journal of the Physical Society of Japan*, 9, 753-766 (1954)\n    **DOI:** 10.1143/JPSJ.9.753\n    https://journals.jps.jp/doi/10.1143/JPSJ.9.753\n\n2. On the Absorption Spectra of Complex Ions II\n\n    **Yukito Tanabe, Satoru Sugano**\n    *Journal of the Physical Society of Japan*, 9, 766-779 (1954)\n    **DOI:** 10.1143/JPSJ.9.766\n    https://journals.jps.jp/doi/10.1143/JPSJ.9.766\n\n3. On the Absorption Spectra of Complex Ions, III The Calculation of the Crystalline Field Strength\n\n    **Yukito Tanabe, Satoru Sugano**\n    *Journal of the Physical Society of Japan*, 11, 864-877 (1956)\n    **DOI:** 10.1143/JPSJ.11.864\n    https://journals.jps.jp/doi/10.1143/JPSJ.11.864\n\nIt provides:\n\n- Tanabe-Sugano- & Energy-Correlation-Diagrams plotted via `matplotlib`\n- Tanabe-Sugano- & Energy-Correlation-Diagrams exported as `txt`-file\n- Atomic-Termsymbols and their eigen-energies for a given 10Dq and oxidation state as exported table via `prettytable`\n- Set-up individuall **C/B**-ratios\n- Working with Slater-Condon-Parameters **F<sup>2</sup>, F<sup>4</sup>** instead of Racah-Parameters **B, C**\n\nThe **TanabeSugano**-application can be installed and run:\n\n```console\n    #via PyPi\n    pip install TanabeSugano\n    \n    #via pip+git\n    pip git+https://github.com/Anselmoo/TanabeSugano.git\n    \n    #locally\n    python setup.py install\n    python -m tanabe\n```\n\n\nThe options of the **TanabeSugano**-application are:\n\n```console\n    python -m tanabe --help\n\n    usage: __main__.py [-h] [-d D] [-Dq DQ] [-cut CUT] [-B B B] [-C C C] [-n N]\n                   [-ndisp] [-ntxt] [-slater]\n\n    optional arguments:\n    -h, --help  show this help message and exit\n    -d D        Number of unpaired electrons (default d5)\n    -Dq DQ      10Dq crystal field splitting (default 10Dq = 8065 cm-)\n    -cut CUT    10Dq crystal field splitting (default 10Dq = 8065 cm-)\n    -B B B      Racah Parameter B and the corresponding reduction (default B = 860 cm- * 1.)\n    -C C C      Racah Parameter C and the corresponding reduction (default C = 4.477*860 cm- * 1.)\n    -n N        Number of roots (default nroots = 500)\n    -ndisp      Plot TS-diagram (default = on)\n    -ntxt       Save TS-diagram and dd energies (default = on)\n    -slater     Using Slater-Condon F2,F4 parameter instead Racah-Parameter B,C (default = off)\n```    \n\n**Reference-Example** for d<sup>6</sup> for *B = 860 cm<sup>-</sup>* and *C = 3850 cm<sup>-</sup>*:\n![placeholder](https://github.com/Anselmoo/TanabeSugano/blob/master/examples/dd-diagram_for_d6.png?raw=true)\n",
    "author": "Anselm Hahn",
    "author_email": "Anselm.Hahn@gmail.com",
    "maintainer": "Anselm Hahn",
    "maintainer_email": "Anselm.Hahn@gmail.com",
    "url": "https://pypi.org/project/TanabeSugano",
    "packages": packages,
    "package_data": package_data,
    "install_requires": install_requires,
    "python_requires": ">=3.7.1,<4.0",
}


setup(**setup_kwargs)
