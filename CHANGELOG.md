# Changelog

## [Unreleased]

### Added
- add rrt pre-commit hooks and unified cicd workflow
- add spectrum fitting tool (`ts_fit_spectrum`) to extract Dq and B parameters from observed UV-Vis absorption peaks
- add scipy dependency for least-squares optimization in spectrum fitting
- add comprehensive test suite for spectrum fitting with validation against real coordination complex spectra
- add pattern documentation for Algorithm Selection + Lazy Computation dogma in spectrum fitting
- add nephelauxetic analysis tool (`ts_nephelauxetic`) interpreting a fitted Racah B as metal-ligand bond covalency via β = B(complex)/B(free ion), with free-ion B tables and ligand-series suggestions

---

## Before v1.2.0

* Adding `Changelog.md`
* Add `poetry` for dependecy mangament
  * `setup.py` depends now on the `project.toml`
* Modified the `GitHub-Actions`
* Introduced `TanabeSugano` batch for extending analysis of correlation matrices
