<div align="center">

# 🔬 TanabeSugano

**A Python-based Eigensolver for Tanabe-Sugano & Energy-Correlation Diagrams**

*Interactive visualization of d-orbital splitting in transition metal complexes*

---

### 📊 Build & Quality

[![Python Package](https://github.com/Anselmoo/TanabeSugano/actions/workflows/python-package.yml/badge.svg)](https://github.com/Anselmoo/TanabeSugano/actions/workflows/python-package.yml)
[![CodeFactor](https://www.codefactor.io/repository/github/anselmoo/tanabesugano/badge)](https://www.codefactor.io/repository/github/anselmoo/tanabesugano)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)

### 📦 Package Info

[![PyPI](https://img.shields.io/pypi/v/TanabeSugano?logo=Pypi&logoColor=yellow)](https://pypi.org/project/TanabeSugano/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/TanabeSugano?logo=Python&logoColor=yellow)](https://pypi.org/project/TanabeSugano/)
[![Downloads](https://static.pepy.tech/badge/tanabesugano)](https://pepy.tech/project/tanabesugano)
[![GitHub release (latest by date including pre-releases)](https://img.shields.io/github/v/release/Anselmoo/TanabeSugano?include_prereleases)](https://github.com/Anselmoo/TanabeSugano/releases)

### 📚 Resources

[![DOI](https://zenodo.org/badge/206847682.svg)](https://zenodo.org/badge/latestdoi/206847682)
[![GitHub](https://img.shields.io/github/license/Anselmoo/TanabeSugano)](https://github.com/Anselmoo/TanabeSugano/blob/master/LICENSE)
[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/Anselmoo/TanabeSugano/blob/master/Tanabe_Sugano.ipynb)

---

[**🚀 Quick Start**](#-quick-start) • 
[**✨ Features**](#-features) • 
[**📖 Documentation**](#-scientific-background) • 
[**🎨 Examples**](#-examples) • 
[**🤝 Contributing**](CONTRIBUTING.md)

</div>

---
## 📋 Table of Contents

- [Overview](#-overview)
- [Quick Start](#-quick-start)
- [Features](#-features)
- [Usage](#-usage)
- [Examples](#-examples)
- [Interactive Diagrams](#-interactive-diagrams)
- [Scientific Background](#-scientific-background)
- [Contributing](#-contributing)
- [Citation](#-citation)
- [License](#-license)

---

## 🌟 Overview

**TanabeSugano** is a comprehensive Python package for calculating and visualizing Tanabe-Sugano and Energy-Correlation diagrams for d<sup>2</sup>-d<sup>8</sup> transition metal ions. Based on the pioneering work of Yukito Tanabe and Satoru Sugano, this tool provides both computational accuracy and interactive visualization capabilities.

### Why TanabeSugano?

- 🎯 **Accurate Calculations** - Based on rigorous quantum mechanical principles
- 📊 **Beautiful Visualizations** - Generate publication-quality diagrams
- 🔄 **Interactive Exploration** - Explore diagrams with Plotly integration
- 🚀 **Easy to Use** - Simple CLI and Python API
- 📱 **Cloud-Ready** - Run in Google Colab or locally

---

## 🚀 Quick Start

### Installation

Choose your preferred installation method:

```bash
# 📦 Install from PyPI (recommended)
pip install TanabeSugano

# 🔧 Install with interactive plotting support
pip install TanabeSugano[plotly]

# 🌐 Install from GitHub (latest development version)
pip install git+https://github.com/Anselmoo/TanabeSugano.git
```

### Basic Usage

Generate a Tanabe-Sugano diagram in seconds:

```bash
# Generate diagram for d6 configuration
tanabesugano -d 6

# Customize parameters
tanabesugano -d 6 -Dq 8000 -B 860 1.0 -C 3850 1.0
```

**🎮 Try it now:** [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/Anselmoo/TanabeSugano/blob/master/Tanabe_Sugano.ipynb)

---

## ✨ Features

<table>
<tr>
<td width="50%">

### 📊 Visualization

- **Static Plots** via Matplotlib
- **Interactive Diagrams** via Plotly
- **Export Formats**: PNG, HTML, TXT
- **Publication-Ready** output quality

</td>
<td width="50%">

### ⚙️ Calculations

- **Eigen-Energies** for all term symbols
- **Customizable Parameters**: B, C ratios
- **Slater-Condon Parameters**: F², F⁴
- **Crystal Field Splitting**: 10Dq control

</td>
</tr>
<tr>
<td width="50%">

### 🎯 Supported Systems

- d² through d⁸ configurations
- Octahedral complexes
- Atomic term symbols
- Energy correlations

</td>
<td width="50%">

### 📤 Export Options

- **Tables** via PrettyTable
- **Diagrams** as images or HTML
- **Data** as text files
- **Interactive** HTML exports

</td>
</tr>
</table>

---

## 📖 Usage

### Command Line Interface

<details>
<summary>🔧 <strong>View all CLI options</strong></summary>

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

</details>

### Python API

```python
from tanabesugano import TanabeSugano

# Create a d6 configuration
ts = TanabeSugano(d=6, Dq=8065, B=860, C=3850)

# Generate and display diagram
ts.plot()

# Export to HTML for interactive use
ts.export_html('d6_diagram.html')
```

---

## 🎨 Examples

### Static Matplotlib Plot

High-quality diagram for d<sup>6</sup> configuration with B = 860 cm⁻¹ and C = 3850 cm⁻¹:

<div align="center">

![Tanabe-Sugano Diagram for d6](https://github.com/Anselmoo/TanabeSugano/blob/master/examples/dd-diagram_for_d6.png?raw=true)

*Figure: Tanabe-Sugano diagram showing energy levels as a function of crystal field strength*

</div>

### Interactive Plotly Visualization

Interactive diagram for d<sup>6</sup> with Slater-Condon parameters F² = 1065 cm⁻¹ and F⁴ = 5120 cm⁻¹:

<div align="center">

![Interactive Tanabe-Sugano Diagram](https://github.com/Anselmoo/TanabeSugano/blob/master/examples/d6_ts_interactive.gif?raw=true)

*Figure: Interactive diagram with hover tooltips and zoom capabilities*

</div>

---

## 🌐 Interactive Diagrams

> **✨ NEW:** Explore all Tanabe-Sugano diagrams online!

All diagrams (d² through d⁸) are now available on our interactive GitHub Pages site with full Plotly integration:

<div align="center">

### **[🔗 View Interactive Diagrams →](https://anselmoo.github.io/TanabeSugano/)**

*No installation required - just click and explore!*

</div>

---

## 📚 Scientific Background

This implementation is based on the seminal work of Yukito Tanabe and Satoru Sugano:

### 📄 Original Publications

<details>
<summary><strong>📖 Paper I: Absorption Spectra of Complex Ions</strong></summary>

**Authors:** Yukito Tanabe, Satoru Sugano  
**Journal:** Journal of the Physical Society of Japan, Vol. 9, pp. 753-766 (1954)  
**DOI:** [10.1143/JPSJ.9.753](https://doi.org/10.1143/JPSJ.9.753)  
**Link:** https://journals.jps.jp/doi/10.1143/JPSJ.9.753

</details>

<details>
<summary><strong>📖 Paper II: Absorption Spectra of Complex Ions</strong></summary>

**Authors:** Yukito Tanabe, Satoru Sugano  
**Journal:** Journal of the Physical Society of Japan, Vol. 9, pp. 766-779 (1954)  
**DOI:** [10.1143/JPSJ.9.766](https://doi.org/10.1143/JPSJ.9.766)  
**Link:** https://journals.jps.jp/doi/10.1143/JPSJ.9.766

</details>

<details>
<summary><strong>📖 Paper III: Calculation of Crystalline Field Strength</strong></summary>

**Authors:** Yukito Tanabe, Satoru Sugano  
**Journal:** Journal of the Physical Society of Japan, Vol. 11, pp. 864-877 (1956)  
**DOI:** [10.1143/JPSJ.11.864](https://doi.org/10.1143/JPSJ.11.864)  
**Link:** https://journals.jps.jp/doi/10.1143/JPSJ.11.864

</details>

---

## 🤝 Contributing

We welcome contributions! Whether you're fixing bugs, adding features, or improving documentation, your help is appreciated.

- 📖 Read our [Contributing Guide](CONTRIBUTING.md)
- 🐛 Report issues on [GitHub Issues](https://github.com/Anselmoo/TanabeSugano/issues)
- 💡 Suggest features or improvements
- 🔧 Submit pull requests

---

## 📝 Citation

If you use TanabeSugano in your research, please cite:

```bibtex
@software{tanabesugano,
  author       = {Anselm Hahn},
  title        = {TanabeSugano: Python-based Eigensolver for Tanabe-Sugano Diagrams},
  year         = {2024},
  publisher    = {Zenodo},
  doi          = {10.5281/zenodo.206847682},
  url          = {https://github.com/Anselmoo/TanabeSugano}
}
```

[![DOI](https://zenodo.org/badge/206847682.svg)](https://zenodo.org/badge/latestdoi/206847682)

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

<div align="center">

**Made with ❤️ for the scientific community**

⭐ Star us on GitHub — it helps!

[Report Bug](https://github.com/Anselmoo/TanabeSugano/issues) · 
[Request Feature](https://github.com/Anselmoo/TanabeSugano/issues) · 
[Discussions](https://github.com/Anselmoo/TanabeSugano/discussions)

</div>
