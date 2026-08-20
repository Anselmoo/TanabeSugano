#!/usr/bin/env python
"""Regenerate the demo artifacts under ``examples/``.

These existed with no generator, which is how they went stale: the committed
``TS_Cut`` table still named ``5_E_1``/``3_E_1``/``1_E_1`` — the pre-rename
spelling of Eg terms, which carry no Mulliken subscript in Oh — and the two
figures the README displays were *screenshots of a matplotlib window*, macOS
title bar and toolbar included, drawn in the old rainbow all-dashed style that
predates ``plot_style``'s colour-by-multiplicity palette.

Parameters are taken from the committed filenames (d6, B = 1080, C = 4773 cm-1,
10Dq up to 25065 cm-1) so the regenerated set stays comparable with what it
replaces.

Run:  uv run python scripts/regenerate_examples.py
"""

from __future__ import annotations

import contextlib
import os

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = REPO_ROOT / "examples"

D_COUNT = 6
B = 1080.0
C = 4773.0
DQ_MAX = 2506.5  # 10Dq = 25065 cm-1, matching the committed filenames
CUT = 24000.0
NROOTS = 500


def main() -> int:
    """Rewrite the example tables and figures. Returns a process exit code."""
    from tanabesugano.cmd import CMDmain
    from tanabesugano.mcp.plotting import render_diagram

    EXAMPLES.mkdir(exist_ok=True)

    # Tables, via the CLI pipeline — the same path that produces ts-diagrams/.
    previous = Path.cwd()
    os.chdir(EXAMPLES)
    try:
        cmd = CMDmain(Dq=DQ_MAX, B=B, C=C, nroots=NROOTS, d_count=D_COUNT)
        cmd.calculation()
        cmd.savetxt()
        with contextlib.redirect_stdout(None):
            cmd.ci_cut(dq_ci=CUT)
    finally:
        os.chdir(previous)

    # Figures, via the shared renderer rather than a screenshot, so they carry
    # the same palette and ground-term emphasis as every other figure the
    # package produces.
    for name, normalize in (
        ("dd-diagram_for_d6.png", False),
        ("TanabeSugano-diagram4d6.png", True),
    ):
        png = render_diagram(
            d_count=D_COUNT,
            dq_min=0.0,
            dq_max=DQ_MAX,
            steps=200,
            B=B,
            C=C,
            normalize=normalize,
            dpi=200,
        )
        (EXAMPLES / name).write_bytes(png)

    for path in sorted(EXAMPLES.iterdir()):
        if path.is_file():
            print(f"  {path.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
