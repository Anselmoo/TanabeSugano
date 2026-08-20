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

# 🤖 Install with MCP server support (Claude Desktop, Cursor, VS Code, …)
pip install TanabeSugano[mcp]

# 🌐 Install from GitHub (latest development version)
pip install git+https://github.com/Anselmoo/TanabeSugano.git
```

> **Note:** TanabeSugano now uses the [`uv_build`](https://docs.astral.sh/uv/concepts/build-backend/) backend and requires Python ≥ 3.12.

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
- **Export Formats**: PNG, PDF, SVG, HTML, CSV
- **Publication-Ready** vector output

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
- **Diagrams** as raster (PNG) or vector (PDF/SVG)
- **Data** as CSV
- **Reproducible** matplotlib source via `ts_fit_script`

</td>
</tr>
</table>

---

## 📖 Usage

### Command Line Interface

<details>
<summary>🔧 <strong>View all CLI options</strong></summary>

```console
$ tanabesugano --help
usage: tanabesugano [-h] [-d D] [-Dq DQ] [-cut CUT] [-B B B] [-C C C] [-n N] [-ndisp]
                    [-ntxt] [-slater] [-v] [-html]

A python-based Eigensolver for Tanabe-Sugano- & Energy-Correlation-Diagrams based on
studies by *Yukito Tanabe and Satoru Sugano* for d3-d8 transition metal ions: For
further help, please use tanabe '--help'

options:
  -h, --help     show this help message and exit
  -d D           Number of d electrons, 2-8 (default d5)
  -Dq DQ         10Dq crystal field splitting (default 10Dq = 8065 cm-)
  -cut CUT       10Dq crystal field splitting (default 10Dq = 8065 cm-)
  -B B B         Racah Parameter B and the corresponding reduction (default B = 860 cm-
                 * 1.)
  -C C C         Racah Parameter C and the corresponding reduction (default C =
                 4.477*860 cm- * 1.)
  -n N           Number of roots (default nroots = 500)
  -ndisp         Plot TS-diagram (default = on)
  -ntxt          Save TS-diagram and dd energies (default = on)
  -slater        Using Slater-Condon F2,F4 parameter instead Racah-Parameter B,C
                 (default = off)
  -v, --version  Print version number and exit
  -html          Save TS-diagram and dd energies (default = off)
```

> The MCP layer uses **per-configuration** Racah defaults rather than the CLI's
> single d5 free-ion pair — see `src/tanabesugano/mcp/_defaults.py`.

</details>

### Python API

> **Changed in 2.0.0.** `solver()` returns a `LevelSet`, not a `dict`.
> `LevelSet` is **not** a Mapping — `states[key]`, `.items()` and `len()` raise
> `TypeError`. Call `.as_dict()` for the previous shape, or iterate `.levels`.

```python
from tanabesugano.levels import LevelSet

# Solve the d8 manifold at one ligand-field strength.
manifold = LevelSet.solve(8, dq=850.0, b=1030.0, c=4850.0)

print(manifold.ground.label)          # 3_A_2
print(manifold.level_count)           # 11 levels ...
print(manifold.total_degeneracy)      # ... accounting for C(10,8) = 45 microstates

# Levels are typed objects, not bare arrays, and carry free-ion parentage:
# 3T_1g(F) / 3T_1g(P), the notation the literature uses, rather than a
# positional (a)/(b).
for level in manifold.spin_allowed():
    print(f"{level.parent_unicode:10} {level.energy_cm1:9.1f} cm-1")
# 3T_2g        8500.0 cm-1     <- nu1 = 10Dq exactly, for d3 and d8
# 3T_1g(F)    14283.0 cm-1
# 3T_1g(P)    26667.0 cm-1

# Name a transition the way a caption would.
excited = manifold.for_term("3_T_1")[1]
print(manifold.transition_unicode(excited))   # 3A_2g -> 3T_1g(P)
```

Sweeping a range of ligand-field strengths, and exporting a figure:

```python
from pathlib import Path

from tanabesugano.batch import Batch
from tanabesugano.mcp.plotting import render_diagram

# Sweep Dq while holding the Racah parameters fixed.
# Each parameter is [start, stop, steps]; hold B and C fixed with one step.
batch = Batch(Dq=[500.0, 1500.0, 20], B=[1030.0, 1030.0, 1], C=[4850.0, 4850.0, 1], d_count=8)
batch.calculation()

# Publication figure: "png" (default), "pdf" or "svg".
Path("d8.pdf").write_bytes(
    render_diagram(d_count=8, dq_max=1500.0, B=1030.0, C=4850.0, fmt="pdf"),
)
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

## 🤖 MCP Server (Claude Desktop, Cursor, …)

TanabeSugano ships an optional [Model Context Protocol](https://modelcontextprotocol.io/) server so AI assistants can compute diagrams, evaluate term symbols, and render plots as first-class tools.

### Install

```bash
pip install "TanabeSugano[mcp]"
# or with uv:
uv add "TanabeSugano[mcp]"
```

### Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "tanabesugano": {
      "command": "uvx",
      "args": ["--from", "tanabesugano[mcp]", "tanabesugano-mcp"]
    }
  }
}
```

### One-click via `.mcpb` bundle

Every release attaches a `tanabesugano-<version>.mcpb` artifact (built by the `Build .mcpb bundle` job in [`cicd.yml`](.github/workflows/cicd.yml)) that Claude Desktop can install in one step — drag the file onto the Claude Desktop window. The bundle pins the exact published version and launches the `tanabesugano-mcp` entry point with the `[mcp]` extra; both are asserted by `scripts/validate_mcpb.py` before the release is created.

### Exposed tools

#### Compute & analysis tools

| Tool | Description |
|---|---|
| `ts_supported_configs` | List supported d-configurations (d²–d⁸). |
| `ts_terms_table_data` | All eigenvalues at one (Dq, B, C), sorted ascending with multiplicity (machine-readable rows). |
| `ts_fit_spectrum` | Fit observed UV-Vis absorption peaks → Dq and Racah B. |
| `ts_nephelauxetic` | Interpret a fitted B as metal-ligand covalency (nephelauxetic β). |
| `ts_plot_png` | Matplotlib figure for any client. `format="png"` (default) returns an inline image; `format="pdf"` / `"svg"` return true vector output as an embedded resource — the only vector export route in the package. |
| `ts_fit_script` | Runnable matplotlib **source** for an observed-vs-computed fit figure. Carries the fitter's own numbers as literals and imports matplotlib only, so a reviewer can reproduce a published figure without installing this package. |
| `ts_plot_view` | Interactive Chart.js line plot (capable clients only). |
| `ts_explain` | One-paragraph ground-state description. |
| `ts_emit_png` | Internal export sink — each Chart.js iframe's "Send PNG to chat" button calls it with the rendered canvas. Not called directly. |

> **Note.** `ts_compute` and `ts_diagram` (raw nested-dict eigenvalue payloads) were removed because the output was unusable without further rendering — Claude's "next steps" devolved into "save to CSV / render PNG" suggestions the client cannot execute. Use `ts_compute_app` / `ts_diagram_app` for in-chat tables and charts, or `ts_terms_table_data` for machine-readable rows.

#### Interactive app tools (Prefab / Chart.js UI — capable clients only)

| App | Description |
|---|---|
| `ts_dashboard_app` | Overview of all d²–d⁸ with ground terms, example ions, matrix sizes, and a concrete absorption-band number per configuration. |
| `ts_compute_app` | Sorted DataTable of every eigenvalue at one (Dq, B, C). Replaces the raw `ts_compute`. |
| `ts_diagram_app` | Full Tanabe-Sugano diagram as an interactive Chart.js line plot. |
| `ts_compare_app` | Multiple d-configurations overlaid on one shared Chart.js plot. |
| `ts_overlay_app` | Overlay multiple d-configurations on one shared chart. |
| `ts_oxidation_landscape_app` | Every eigenvalue of d²–d⁸ at fixed (Dq, B, C): `style="scatter"` (default) renders discrete dots per d-count, `style="density"` renders a Gaussian-broadened 2D heatmap (control σ via `broadening_cm`). |
| `ts_orgel_diagram_app` | Orgel diagram — E (cm⁻¹) vs Δ (cm⁻¹), the classic unnormalised companion to `ts_diagram_app`. d²/d³/d⁸ render smoothly; d⁴–d⁷ show the HS↔LS kink. |
| `ts_spin_crossover_app` | For d⁴/d⁵/d⁶/d⁷ only: ground-term energy of the candidate HS and LS curves vs Δ with the critical Dq annotated. Returns the numeric `critical_Dq_cm1`. |
| `ts_correlation_diagram_app` | Three-axis correlation diagram (free ion ↔ weak field ↔ strong field) — the classical Tsuchida/Cotton pedagogical bridge between free-ion term symbols and strong-field t₂g^x e_g^y configurations. |
| `ts_spectrum_app` | Simulated Lorentzian UV-Vis spectrum (spin-allowed + spin-forbidden). |
| `ts_reverse_fit_app` | Grid-search Dq and B to best-fit observed peak positions. |
| `ts_ratio_fit_app` | Derive Dq and B from 2–3 measured bands via the ratio method. |
| `ts_fit_plot_app` | Observed vs computed bands for a fit, plotted as residuals (computed − observed). A ~100 cm⁻¹ misfit is narrower than a marker on an 8,000–26,000 cm⁻¹ axis, so raw positions would show coincident dots; the raw values travel in the structured payload. |

#### Prompts & resources

Prompts: `tanabesugano_why` (discovery context) and `tanabesugano_explain_complex` (guided spectrum interpretation from measured absorption peaks).

Resources at `tanabesugano://version`, `tanabesugano://configs`, `tanabesugano://config/{d}` provide static metadata.

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
