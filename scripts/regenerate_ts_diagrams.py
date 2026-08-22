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
)
FIGURE_AND_HTML_DIR = REPO_ROOT / "ts-diagrams"
"""The one tree that carries diagrams and figures, not just tables.

Declared rather than inferred. The previous rule was "a directory gets HTML if
it already contains HTML", which reads the answer off the thing it is deciding:
delete every .html once and the tree can never regenerate itself, because the
sniff now says this directory was never meant to have any. Observed exactly
that -- `rm ts-diagrams/d*/*.html` followed by a regen reported "0 file(s)
regenerated" and restored nothing.

``docs/ts-diagrams`` is excluded on purpose: it feeds the Vite app, which
renders interactively from the CSVs via manifest.json and would gain ~14 MB it
never loads.
"""

"""Where committed artifacts live.

``docs-site/public/ts-diagrams`` used to be here and was removed with the tree
itself: it held 80 MB across 36 tracked files with no ``package.json`` and no
``src/`` around them, and no workflow ever built it. The live Vite app is
``docs/`` -- whose ``package.json`` is *named* ``docs-site``, which is how the
stray copy came to exist. Only this script ever wrote to it.
"""

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


class VacuousGateError(RuntimeError):
    """Raised when a diagram carries no level identifiers to compare at all."""


def _html_level_uids(path: Path) -> set[str]:
    """Every ``Level.uid`` stamped into a Plotly diagram's trace metadata.

    Full-precision floats are baked into these files, so they inherit the same
    cross-platform instability as the CSVs and cannot be byte-compared either.
    What actually went stale in them was the *vocabulary*: the committed
    diagrams still named ``1_T_3``, an irrep that does not exist in Oh, years
    after the rename. Comparing the identifier set catches precisely that, and
    does so identically on any platform.

    This reads ``trace.meta.uid`` rather than grepping term keys out of the
    embedded data, and the difference is load-bearing. Trace names are now
    typeset plotly markup (``<sup>3</sup>T<sub>1g</sub>(F)``), so the raw keys
    the old pattern searched for are simply not in the file any more -- and a
    set that comes back empty for BOTH sides compares equal, so the gate would
    report every diagram as current forever. `cmd.interactive_plot` stamps the
    uid for exactly this reason.

    Deliberately extracts whatever the ``uid`` field holds, without filtering
    to a legal shape. A pattern restricted to valid keys cannot see ``1_T_3``
    -- the exact stale key this check exists to catch -- because T subscripts
    are only ever 1 or 2. Verified: with a narrow pattern, substituting 1_T_3
    into a committed diagram was reported as no drift at all.

    Raises:
        VacuousGateError: when the file names no levels. Without this the gate
            silently degrades into a no-op, which is the failure mode that let
            these artifacts rot for years in the first place.

    """
    uids = set(_UID_IN_HTML_RE.findall(path.read_text(encoding="utf-8")))
    if not uids:
        msg = (
            f"{path.name} carries no trace uid metadata, so there is nothing to "
            f"compare -- an empty set would match any other empty set and the "
            f"drift gate would pass vacuously. Regenerate with a current "
            f"tanabesugano (cmd.interactive_plot stamps trace.meta.uid)."
        )
        raise VacuousGateError(msg)
    return uids


# Matches the uid stamped by `cmd.interactive_plot`, e.g. `"uid":"3_T_1#0"`.
# Plotly escapes `<` and `>` as \uXXXX inside its JSON payload but leaves
# `#`, letters and digits alone, so the value needs no unescaping.
_UID_IN_HTML_RE = re.compile(r'"uid"\s*:\s*"([^"]{1,32})"')


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


def _series_block(csv_path: Path, spec: Spec) -> dict[str, dict[str, object]]:
    """The drawing contract for one CSV, keyed by its own column names.

    This is what makes a shared colour standard possible across languages. The
    React docs app used to carry a hand-written palette in TypeScript that
    mapped a quartet to orange where matplotlib maps it to green, and a label
    formatter that turned ``3_T_1_0`` into ``3 T 1 0``. Neither could be kept in
    step with Python by anything but discipline, and it wasn't.

    Emitting the decision as DATA -- into the manifest the app already
    fetches -- means the app carries no palette and no formatter at all, and the
    existing manifest drift gate guards the whole contract for free.

    Keys come from the CSV header rather than from the level machinery, so what
    the app looks up is exactly what it will find in the file it parses.
    """
    from tanabesugano.figure_style import column_to_uid
    from tanabesugano.figure_style import series_styles

    styles = series_styles(spec.d_count, spec.dq, spec.b, spec.c)
    header = csv_path.read_text(encoding="utf-8").splitlines()[0]
    block: dict[str, dict[str, object]] = {}
    for column in next(csv.reader([header]))[1:]:
        style = styles.get(column_to_uid(column))
        if style is None:
            # A header the level machinery cannot place means the CSV writer and
            # the naming layer have drifted. Loud beats a silently unstyled curve.
            msg = f"{csv_path.name}: column {column!r} matches no level of d{spec.d_count}"
            raise KeyError(msg)
        block[column] = style.as_manifest_entry()
    return block


def _build_manifest(target_dir: Path, specs: dict[int, Spec]) -> str:
    """Rebuild ``manifest.json`` from the CSVs actually present under target_dir.

    Grouped by d-count and sorted throughout, so the output is a pure function
    of the directory contents -- otherwise the drift gate would report churn
    from dict ordering rather than from real change. ``type`` follows the
    filename prefix, which is how the docs app distinguishes the two families.

    Each entry carries a ``series`` block: see :func:`_series_block`.
    """
    entries: dict[str, list[dict[str, object]]] = {}
    for csv_path in sorted(target_dir.rglob("*.csv")):
        match = re.search(r"_d(\d)_", csv_path.name)
        if match is None:
            continue
        d_count = int(match.group(1))
        entry: dict[str, object] = {
            "name": csv_path.name,
            "path": str(csv_path.relative_to(target_dir.parent)),
            "type": "DD" if csv_path.name.startswith("DD-") else "TS",
        }
        # Only the two sweep families carry per-level curves. TS_Cut is a
        # different shape entirely -- a state/cm/eV table at a single 10Dq --
        # and has no series to style.
        spec = specs.get(d_count)
        if spec is not None and csv_path.name.startswith(("TS-diagram", "DD-energies")):
            entry["series"] = _series_block(csv_path, spec)
        entries.setdefault(f"d{d_count}", []).append(entry)
    ordered = {
        key: sorted(value, key=lambda e: str(e["name"])) for key, value in sorted(entries.items())
    }
    return json.dumps(ordered, indent=2) + "\n"


FIGURE_FORMATS = ("png", "pdf")
"""Raster for a README or an issue, vector for a manuscript.

SVG is deliberately not committed even though ``render_diagram`` supports it: a
1000-point sweep of ~40 curves is megabytes of path data per file, while the
same figure as PDF is a fraction of that and is the format a journal asks for.
``render_diagram(fmt="svg")`` remains available on demand.
"""

FIGURE_STEPS = 200
"""Sweep points used for the committed figures, against 1000 for the CSVs.

A figure 9 inches wide cannot resolve 1000 points; 200 is visually identical
and keeps the vector files small. The full-resolution data stays in the CSVs,
which is where anyone doing arithmetic should be reading it from anyway.
"""


def _d_count_of(name: str) -> int | None:
    """Recover the d-electron count from an artifact filename."""
    match = re.search(r"_d(\d)_", name)
    return int(match.group(1)) if match else None


def _mark_redrawn(redrawn: set[int], name: str) -> None:
    """Note that this configuration's figures are out of date.

    A name with no ``_d{N}_`` in it is simply not one of ours and is skipped --
    the guard is what keeps ``None`` out of a ``set[int]``.
    """
    d_count = _d_count_of(name)
    if d_count is not None:
        redrawn.add(d_count)


def _figure_defect(path: Path) -> str | None:
    """Why a committed figure is unusable, or None when it is fine.

    Deliberately NOT a content gate, and the distinction matters enough to
    write down. matplotlib output is not byte-reproducible across platforms --
    the same reason :data:`VALUE_RTOL` exists for the CSVs -- so there is no
    honest way to compare two renderings pixel for pixel in CI.

    It does not need to be a content gate. The figures and the ``.html``
    diagrams are drawn from the same ``figure_style.series_styles`` call, so a
    figure cannot carry a vocabulary or a palette that the HTML does not also
    carry, and the HTML *is* gated on its level uids. What is left for this
    check is the failure the uid gate cannot see: a figure that is missing,
    truncated or not an image at all.
    """
    if not path.is_file():
        return "missing"
    head = path.read_bytes()[:8]
    if path.suffix == ".png" and head[:8] != b"\x89PNG\r\n\x1a\n":
        return "not a PNG"
    if path.suffix == ".pdf" and head[:5] != b"%PDF-":
        return "not a PDF"
    minimum_plausible_bytes = 4096
    if path.stat().st_size < minimum_plausible_bytes:
        return f"truncated ({path.stat().st_size} bytes)"
    return None


def _render_figures(spec: Spec, out_dir: Path, stem_ts: str, stem_dd: str) -> list[Path]:
    """Write the PNG and PDF pair for both views of one configuration."""
    from tanabesugano.mcp.plotting import render_diagram

    written: list[Path] = []
    for stem, normalize in ((stem_ts, True), (stem_dd, False)):
        for fmt in FIGURE_FORMATS:
            target = out_dir / f"{stem}.{fmt}"
            target.write_bytes(
                render_diagram(
                    d_count=spec.d_count,
                    dq_min=0.0,
                    dq_max=spec.dq,
                    steps=FIGURE_STEPS,
                    B=spec.b,
                    C=spec.c,
                    normalize=normalize,
                    dpi=200,
                    fmt=fmt,
                ),
            )
            written.append(target)
    return written


OFFLINE_DIR = REPO_ROOT / "ts-diagrams-offline"
"""Where ``--offline`` puts self-contained diagrams.

Separate from the committed tree on purpose. The committed ``.html`` reference
plotly.js from the CDN, which is what took that tree from 160 MB to a few MB;
writing the inlined copies over them would undo that and make every run look
like drift. Anyone who needs to read a diagram without a network gets their own
copy here, and it is gitignored.
"""


def _write_offline_tree() -> int:
    """Regenerate every diagram with a shared local plotly.min.js."""
    specs = parse_specs(TARGET_DIRS[0])
    if not specs:
        sys.stderr.write(f"no parsable artifacts under {TARGET_DIRS[0]}\n")
        return 1
    if not html_supported():
        sys.stderr.write("plotly is not installed; install the [plotly] extra\n")
        return 1

    from tanabesugano.cmd import CMDmain

    OFFLINE_DIR.mkdir(parents=True, exist_ok=True)
    previous = Path.cwd()
    written = 0
    for spec in specs.values():
        destination = OFFLINE_DIR / f"d{spec.d_count}"
        destination.mkdir(parents=True, exist_ok=True)
        os.chdir(destination)
        try:
            cmd = CMDmain(
                Dq=spec.dq,
                B=spec.b,
                C=spec.c,
                nroots=NROOTS,
                d_count=spec.d_count,
            )
            cmd.calculation()
            cmd.interactive_plot(include_plotlyjs="directory")
            written += 2
        finally:
            os.chdir(previous)
    sys.stdout.write(
        f"wrote {written} self-contained diagram(s) to {OFFLINE_DIR.relative_to(REPO_ROOT)}/\n",
    )
    return 0


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
        _render_figures(spec, Path.cwd(), cmd.title_TS, cmd.title_DD)
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
    parser.add_argument(
        "--offline",
        action="store_true",
        help=(
            "write a self-contained copy of the .html diagrams (with a shared "
            f"local plotly.min.js) into {OFFLINE_DIR.name}/ and exit"
        ),
    )
    args = parser.parse_args()

    if args.offline:
        return _write_offline_tree()

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
        produced_figures = {p.name: p for fmt in FIGURE_FORMATS for p in staging.glob(f"*.{fmt}")}

        stale: list[str] = []
        # d-counts whose data actually changed. Figures are rewritten only for
        # these (or when missing/corrupt), so a no-op `poe regen-diagrams` does
        # not restage 56 binary files and show up as churn in every diff.
        redrawn: set[int] = set()

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
                    _mark_redrawn(redrawn, existing.name)
                    if not args.check:
                        shutil.copyfile(fresh, existing)

            if not with_html:
                continue
            if target_dir != FIGURE_AND_HTML_DIR:
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
                fresh_uids = _html_level_uids(fresh)
                try:
                    old_uids = _html_level_uids(existing)
                except VacuousGateError as exc:
                    _mark_redrawn(redrawn, existing.name)
                    # A committed diagram from before uid stamping. It is stale
                    # by definition -- say so rather than letting the missing
                    # metadata read as "nothing to compare, so no drift".
                    stale.append(f"{existing.relative_to(REPO_ROOT)} -- {exc}")
                    if not args.check:
                        shutil.copyfile(fresh, existing)
                    continue
                if fresh_uids != old_uids:
                    added = sorted(fresh_uids - old_uids)
                    removed = sorted(old_uids - fresh_uids)
                    stale.append(
                        f"{existing.relative_to(REPO_ROOT)} -- level uids (+{added} -{removed})",
                    )
                    _mark_redrawn(redrawn, existing.name)
                    if not args.check:
                        shutil.copyfile(fresh, existing)
            # Figures live beside the diagrams they depict. Only in the
            # artifact tree, not in docs/ts-diagrams: that one feeds the Vite
            # app, which renders interactively from the CSVs and would gain
            # several MB it never loads.
            for name, fresh in sorted(produced_figures.items()):
                d_count = _d_count_of(name)
                if d_count is None:
                    continue
                destination = target_dir / f"d{d_count}" / name
                defect = _figure_defect(destination)
                if defect is not None:
                    stale.append(f"{destination.relative_to(REPO_ROOT)} ({defect})")
                elif d_count not in redrawn:
                    continue
                if not args.check:
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(fresh, destination)

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
            rebuilt = _build_manifest(target_dir, specs)
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
