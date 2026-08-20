"""Regenerate the committed Tanabe-Sugano CSV and interactive-HTML artifacts.

These CSVs are CLI output that had been produced ad hoc, with no script to
reproduce them. That meant they silently went stale whenever the CLI changed --
and by the time this script was written they were wrong on three counts at once:

1. term keys ``1_T_3`` and ``*_E_1``, renamed to ``1_T_2`` and ``*_E``;
2. the ``delta_B`` column, which held Dq/B while being labelled and exported as
   Delta/B -- off by a factor of 10, since Delta_o == 10Dq;
3. the cm^-1 -> eV factor, which was 0.00012 (~1/8333) instead of 1/8065.54.

Every parameter is recovered from the existing FILENAMES, so no file is renamed
and no manifest needs updating:

    TS-diagram_d{N}_10Dq_{int(Dq*10)}_B_{int(B)}_C_{int(C)}.csv
    DD-energies_d{N}_10Dq_{int(Dq*10)}_B_{int(B)}_C_{int(C)}.csv
    TS_Cut_d{N}_10Dq_{int(cut)}_B_{int(B)}_C_{int(C)}.csv

A deliberate fidelity choice: the filename truncates C to an integer, so the
original C is not exactly recoverable -- d8 was generated with
C = 4.709 * 1030 = 4850.27 while its name says 4850. This script uses the
FILENAME value, which makes name and content agree for the first time (they
previously disagreed by the truncated fraction). The resulting energies differ
from the originals in the fifth significant figure; C is a fixed input here, not
a fitted quantity, so this is a labelling correction rather than a physics
change. Note also that two names disagree with the package defaults by 1 cm^-1
(d3 C_4132 vs DEFAULTS 4133; d7 C_4498 vs 4499); the filename wins, so the
artifacts stay self-describing.

Usage:
    uv run python scripts/regenerate_ts_diagrams.py [--check]

``--check`` regenerates into a temporary directory and reports which committed
files differ, without writing anything.

Comparison is deliberately NOT byte-exact, because byte-exact is not portable.
CI proved it: with identical numpy/scipy/pandas/matplotlib/plotly versions, all
42 full-precision sweep CSVs differed between macOS/arm64 and Linux/x86_64
while all 21 TS_Cut tables -- which round to integers and 4 decimals -- matched
exactly. Different BLAS, last-ulp differences. A byte gate on floating-point
output can only ever pass on the machine that happened to generate the files.

So: CSV headers are compared exactly (a renamed or reordered column fails, and
that is the drift this gate first caught), values within VALUE_RTOL, and HTML
by its term-key vocabulary rather than its 4.9 MB embedded plotly bundle.

The Plotly ``.html`` diagrams are covered too, and they went stale exactly the
way the CSVs did -- the committed ones still name ``1_T_3``, an irrep that does
not exist in Oh, because nothing regenerated them after the rename. Two of them
also carry names from an older, buggy scheme (``B_918.0_C_4132``,
``C_413``); those are removed rather than kept alongside the correct name.

Comparing HTML needs one wrinkle: Plotly stamps a fresh random UUID into the
container ``<div>`` on every write, so two runs of identical input differ in
exactly that one string and nowhere else (verified: same byte length, identical
after normalising the UUID). :func:`_normalise_html` replaces it before
comparison, which is what makes an HTML drift gate possible at all -- comparing
raw bytes would report drift on every run and the check would have to be
abandoned.

HTML is only written into directories that already contain HTML. ``docs/`` is
the Vite app; it reads the CSVs through ``manifest.json`` and has never held
HTML, so nothing is created there.

Requires the ``plotly`` extra for the HTML half. Without it the CSVs are still
checked and HTML is reported as skipped, rather than the whole run failing.
"""

from __future__ import annotations

import argparse
import contextlib
import csv
import json
import math
import os
import re
import shutil
import sys
import tempfile

from pathlib import Path
from typing import NamedTuple


REPO_ROOT = Path(__file__).resolve().parent.parent
TARGET_DIRS = (
    REPO_ROOT / "ts-diagrams",
    REPO_ROOT / "docs" / "ts-diagrams",
    REPO_ROOT / "docs-site" / "public" / "ts-diagrams",
)

_NAME_RE = re.compile(
    r"^(?P<kind>TS-diagram|DD-energies|TS_Cut)_d(?P<d>\d)_10Dq_(?P<tendq>\d+)"
    r"_B_(?P<b>\d+)_C_(?P<c>\d+)\.csv$",
)

# nroots used for the sweeps. Recovered from the committed files, which carry
# 1000 data rows -- NOT the CLI default of 500.
NROOTS = 1000


class Spec(NamedTuple):
    """Parameters recovered from one artifact filename."""

    d_count: int
    dq: float
    b: float
    c: float
    cut: float | None


def parse_specs(directory: Path) -> dict[int, Spec]:
    """Recover one Spec per d-count from the filenames in ``directory``."""
    sweep: dict[int, dict] = {}
    for path in sorted(directory.rglob("*.csv")):
        match = _NAME_RE.match(path.name)
        if not match:
            continue
        d_count = int(match.group("d"))
        entry = sweep.setdefault(d_count, {})
        entry["b"] = float(match.group("b"))
        entry["c"] = float(match.group("c"))
        if match.group("kind") == "TS_Cut":
            entry["cut"] = float(match.group("tendq"))
        else:
            entry["dq"] = float(match.group("tendq")) / 10.0
    return {
        d: Spec(d, v["dq"], v["b"], v["c"], v.get("cut"))
        for d, v in sorted(sweep.items())
        if "dq" in v
    }


_UUID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
)


VALUE_RTOL = 1e-9
"""Relative tolerance when comparing regenerated numbers against committed ones.

Byte comparison is NOT portable here, and CI proved it: with identical numpy,
scipy, pandas, matplotlib and plotly versions, all 42 full-precision sweep CSVs
differed between macOS/arm64 and Linux/x86_64 while all 21 TS_Cut tables --
which round to integers and 4 decimals -- matched exactly. That is the
signature of last-ulp differences from a different BLAS/LAPACK, not staleness.

The tolerance is chosen from the gap between the two, not measured off a run:
BLAS disagreement is ~1e-15 relative, while every defect this gate was built to
catch is enormous by comparison -- a `delta_B` column off by 10x, a cm^-1 -> eV
factor wrong by ~30%, a renamed or reordered column. 1e-9 sits six orders above
the noise and six below the smallest real defect, so it cannot be a tolerance
that quietly absorbs a regression.

Structure is still compared EXACTLY: a header that renamed or reordered a
column fails regardless of tolerance, and that was the actual drift this gate
first caught.
"""


def _csv_difference(fresh: Path, existing: Path) -> str | None:
    """Return why two CSVs differ, or None when they are equivalent."""
    fresh_rows = list(csv.reader(fresh.read_text(encoding="utf-8").splitlines()))
    old_rows = list(csv.reader(existing.read_text(encoding="utf-8").splitlines()))
    if not fresh_rows or not old_rows:
        return "one file is empty"
    if fresh_rows[0] != old_rows[0]:
        added = sorted(set(fresh_rows[0]) - set(old_rows[0]))
        removed = sorted(set(old_rows[0]) - set(fresh_rows[0]))
        if added or removed:
            return f"columns changed (+{added} -{removed})"
        return "columns reordered"
    if len(fresh_rows) != len(old_rows):
        return f"row count {len(old_rows)} -> {len(fresh_rows)}"
    rows = zip(fresh_rows[1:], old_rows[1:], strict=True)
    for line_no, (a, b) in enumerate(rows, start=2):
        if len(a) != len(b):
            return f"line {line_no}: {len(b)} fields -> {len(a)}"
        for column, (x, y) in enumerate(zip(a, b, strict=True)):
            try:
                fx, fy = float(x), float(y)
            except ValueError:
                if x != y:
                    return f"line {line_no} col {column}: {y!r} -> {x!r}"
                continue
            if not math.isclose(fx, fy, rel_tol=VALUE_RTOL, abs_tol=VALUE_RTOL):
                return f"line {line_no} col {column} ({fresh_rows[0][column]}): {fy!r} -> {fx!r}"
    return None


def _html_term_keys(path: Path) -> set[str]:
    """Every octahedral term key named in a Plotly diagram's embedded data.

    Full-precision floats are baked into these files, so they inherit the same
    cross-platform instability as the CSVs and cannot be byte-compared either.
    What actually went stale in them was the *vocabulary*: the committed
    diagrams still named ``1_T_3``, an irrep that does not exist in Oh, years
    after the rename. Comparing the term-key set catches precisely that, and
    does so identically on any platform.
    """
    return set(_TERM_IN_HTML_RE.findall(path.read_text(encoding="utf-8")))


# Deliberately matches the general SHAPE, not the valid vocabulary. A pattern
# restricted to legal keys cannot see `1_T_3` -- the exact stale key this check
# exists to catch -- because T subscripts are only ever 1 or 2. Verified: with
# the narrow pattern, substituting 1_T_3 into a committed diagram was reported
# as no drift at all.
_TERM_IN_HTML_RE = re.compile(r"\b([1-6]_[ATE](?:_\d+)*)\b")


def _normalise_html(path: Path) -> str:
    """HTML text with Plotly's random container UUID replaced by a constant.

    Plotly writes a fresh UUID into the plot ``<div>`` id on every call, so two
    writes of identical data differ in that one string and nowhere else --
    verified by generating the same figure twice: same byte length, and equal
    once the UUID is normalised. Without this the drift gate would fire on
    every run and would have to be deleted, which is how the CSVs went
    unguarded in the first place.
    """
    return _UUID_RE.sub("UUID", path.read_text(encoding="utf-8"))


def _build_manifest(target_dir: Path) -> str:
    """Rebuild ``manifest.json`` from the CSVs actually present under target_dir.

    Grouped by d-count and sorted throughout, so the output is a pure function
    of the directory contents -- otherwise the drift gate would report churn
    from dict ordering rather than from real change. ``type`` follows the
    filename prefix, which is how the docs app distinguishes the two families.
    """
    entries: dict[str, list[dict[str, str]]] = {}
    for csv_path in sorted(target_dir.rglob("*.csv")):
        match = re.search(r"_d(\d)_", csv_path.name)
        if match is None:
            continue
        entries.setdefault(f"d{match.group(1)}", []).append(
            {
                "name": csv_path.name,
                "path": str(csv_path.relative_to(target_dir.parent)),
                "type": "DD" if csv_path.name.startswith("DD-") else "TS",
            },
        )
    ordered = {
        key: sorted(value, key=lambda e: e["name"]) for key, value in sorted(entries.items())
    }
    return json.dumps(ordered, indent=2) + "\n"


def html_supported() -> bool:
    """Whether the optional plotly extra is importable."""
    try:
        import plotly.express  # noqa: F401
    except ImportError:
        return False
    return True


def generate(spec: Spec, out_dir: Path, *, with_html: bool = True) -> None:
    """Run the CLI pipeline for one configuration, writing artifacts into out_dir."""
    from tanabesugano.cmd import CMDmain

    previous = Path.cwd()
    os.chdir(out_dir)
    try:
        cmd = CMDmain(
            Dq=spec.dq,
            B=spec.b,
            C=spec.c,
            nroots=NROOTS,
            d_count=spec.d_count,
        )
        cmd.calculation()
        cmd.savetxt()
        if with_html:
            cmd.interactive_plot()
        if spec.cut is not None:
            with contextlib.redirect_stdout(None):
                cmd.ci_cut(dq_ci=spec.cut)
    finally:
        os.chdir(previous)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="report differences without writing",
    )
    args = parser.parse_args()

    reference = TARGET_DIRS[0]
    if not reference.is_dir():
        sys.stderr.write(f"missing artifact directory: {reference}\n")
        return 1
    specs = parse_specs(reference)
    if not specs:
        sys.stderr.write(f"no parsable artifacts under {reference}\n")
        return 1

    with_html = html_supported()
    if not with_html:
        sys.stdout.write(
            "note: plotly is not installed, so .html artifacts are neither "
            "checked nor written (install the [plotly] extra to cover them)\n",
        )

    with tempfile.TemporaryDirectory() as tmp:
        staging = Path(tmp)
        for spec in specs.values():
            generate(spec, staging, with_html=with_html)
        produced = {p.name: p for p in staging.glob("*.csv")}
        produced_html = {p.name: p for p in staging.glob("*.html")}

        stale: list[str] = []
        for target_dir in TARGET_DIRS:
            if not target_dir.is_dir():
                continue
            for existing in sorted(target_dir.rglob("*.csv")):
                fresh = produced.get(existing.name)
                if fresh is None:
                    continue
                reason = _csv_difference(fresh, existing)
                if reason is not None:
                    stale.append(f"{existing.relative_to(REPO_ROOT)} -- {reason}")
                    if not args.check:
                        shutil.copyfile(fresh, existing)

            if not with_html:
                continue
            # Only directories that already hold HTML get HTML: docs/ is the
            # Vite app, which reads the CSVs via manifest.json and has never
            # had any. Creating it there would add ~9 MB the site never loads.
            html_dirs = {p.parent for p in target_dir.rglob("*.html")}
            if not html_dirs:
                continue
            for existing in sorted(target_dir.rglob("*.html")):
                fresh = produced_html.get(existing.name)
                if fresh is None:
                    # A name the current CLI no longer produces -- an older,
                    # buggy naming scheme (B_918.0_C_4132, a truncated C_413).
                    # Leaving it would ship a second, stale copy of a diagram
                    # under a name nothing regenerates.
                    stale.append(f"{existing.relative_to(REPO_ROOT)} (orphaned name)")
                    if not args.check:
                        existing.unlink()
                    continue
                fresh_terms = _html_term_keys(fresh)
                old_terms = _html_term_keys(existing)
                if fresh_terms != old_terms:
                    added = sorted(fresh_terms - old_terms)
                    removed = sorted(old_terms - fresh_terms)
                    stale.append(
                        f"{existing.relative_to(REPO_ROOT)} -- term keys (+{added} -{removed})",
                    )
                    if not args.check:
                        shutil.copyfile(fresh, existing)
            # Names the CLI produces that are absent here.
            present = {p.name for p in target_dir.rglob("*.html")}
            for name, fresh in sorted(produced_html.items()):
                if name in present:
                    continue
                d_match = re.search(r"_d(\d)_", name)
                if d_match is None:
                    continue
                destination = target_dir / f"d{d_match.group(1)}" / name
                stale.append(f"{destination.relative_to(REPO_ROOT)} (missing)")
                if not args.check:
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(fresh, destination)

        # manifest.json is the index the Vite docs app reads to find the CSVs.
        # It had no generator and no guard, so a renamed or added CSV would
        # have desynchronised it silently -- the same gap that let the CSVs
        # themselves go stale. Rebuilt from what is actually on disk.
        for target_dir in TARGET_DIRS:
            manifest = target_dir / "manifest.json"
            if not manifest.is_file():
                continue
            rebuilt = _build_manifest(target_dir)
            current = manifest.read_text(encoding="utf-8")
            if rebuilt != current:
                stale.append(str(manifest.relative_to(REPO_ROOT)))
                if not args.check:
                    manifest.write_text(rebuilt, encoding="utf-8")

        verb = "differ from" if args.check else "regenerated against"
        sys.stdout.write(f"{len(stale)} file(s) {verb} the current CLI\n")
        for name in stale:
            sys.stdout.write(f"  {name}\n")
        return 1 if (args.check and stale) else 0


if __name__ == "__main__":
    raise SystemExit(main())
