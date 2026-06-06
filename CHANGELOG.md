# Changelog

## [Unreleased]

### Added
- add rrt pre-commit hooks and unified cicd workflow
- add spectrum fitting tool (`ts_fit_spectrum`) to extract Dq and B parameters from observed UV-Vis absorption peaks
- add scipy dependency for least-squares optimization in spectrum fitting
- add comprehensive test suite for spectrum fitting with validation against real coordination complex spectra
- add pattern documentation for Algorithm Selection + Lazy Computation dogma in spectrum fitting
- add nephelauxetic analysis tool (`ts_nephelauxetic`) interpreting a fitted Racah B as metal-ligand bond covalency via β = B(complex)/B(free ion), with free-ion B tables and ligand-series suggestions
- add UV-Vis reference spectra assets (`assets/uvvis/`) with a generator script (`scripts/plot_uvvis_fits.py`) for the Ni(II) spectrum-fitting examples
- export UV-Vis reference spectra as self-describing tab-separated ASCII `.txt` datasets (wavenumber / wavelength / absorbance) alongside the figures
- harden MCP tool input validation (`ts_plot_png`, `ts_terms_table_data`, `ts_plot_view`, `ts_reverse_fit`) to return structured errors instead of raising
- add Playwright screenshot tests (`test_screenshots.py`, `screenshot` mark) and gitignore the generated `test-screenshots/` output
- update `.gitignore` to exclude python and node modules in the correct fashion
- update `cicd.yml` to use the correct version of `repo-release-tools` for validating release policies
- add initial `tree.lock.toml` for dependency management

---

## Before v1.2.0

* Adding `Changelog.md`
* Add `poetry` for dependecy mangament
  * `setup.py` depends now on the `project.toml`
* Modified the `GitHub-Actions`
* Introduced `TanabeSugano` batch for extending analysis of correlation matrices
