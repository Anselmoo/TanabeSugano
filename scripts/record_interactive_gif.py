#!/usr/bin/env python
"""Record the README's interactive-diagram GIF instead of screen-capturing one.

``examples/d6_ts_interactive.gif`` was a hand-made screen recording, which is
why it outlived several notation changes: nothing could regenerate it, so
nobody did. It still showed the old raw ``3_T_1_0`` legend keys long after the
package had stopped producing them.

This drives the real diagram in a real browser and assembles the frames, so the
GIF is a product of the current code the same way every other committed
artifact now is.

Deliberately NOT part of ``poe regen-all`` and NOT covered by the drift gate:

* it needs a browser (``uv sync --group screenshot`` plus
  ``playwright install chromium``), which the other artifact scripts do not;
* a recording is not reproducible frame-for-frame -- font rasterisation and
  animation timing differ per machine -- so a byte or near-byte gate on it
  could only ever pass where it was generated. The *diagram* it records is
  gated, via ``scripts/regenerate_ts_diagrams.py``; the recording is a view of
  an already-guarded artifact.

Run:  uv run poe regen-gif
"""

from __future__ import annotations

import argparse
import contextlib
import os
import sys
import tempfile

from pathlib import Path
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from playwright.sync_api import FloatRect
    from playwright.sync_api import Page
    from playwright.sync_api import ViewportSize


REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT = REPO_ROOT / "examples" / "d6_ts_interactive.gif"

# Matches the committed d6 example tables, so the GIF and examples/*.csv show
# the same complex rather than two unrelated parameter sets.
D_COUNT = 6
B = 1080.0
C = 4773.0
DQ_MAX = 2506.5
NROOTS = 240

VIEWPORT: ViewportSize = {"width": 920, "height": 660}
FRAME_MS = 110
"""Delay per frame. ~9 fps: fast enough to read as motion, slow enough that a
hover tooltip stays on screen long enough to actually be read."""

HOLD_MS = 650
"""How long a frame marking the end of a gesture stays on screen.

A recording with no pauses reads as a twitch. Expressed as a per-frame duration
rather than by repeating the frame: Pillow collapses identical consecutive
frames when writing a GIF, so repetition silently became a single frame at the
base delay and every pause vanished. Observed: 56 captured frames became 21 in
the file, and the tooltip flashed past unreadably.
"""

GIF_COLORS = 128
"""Palette size. A Tanabe-Sugano diagram is a handful of hues on white; 128
colours covers the lightness ramp and antialiasing with no visible banding, at
roughly half the size of a full 256-colour palette."""


def _display_path(path: Path) -> Path:
    """Repo-relative when it is inside the repo, absolute otherwise.

    ``--output`` may point anywhere, and a bare ``relative_to`` raises for a
    path outside the repo -- *after* the GIF has been written, so a successful
    run reported itself as a traceback.
    """
    resolved = path.resolve()
    return resolved.relative_to(REPO_ROOT) if resolved.is_relative_to(REPO_ROOT) else resolved


def _build_offline_diagram(out_dir: Path) -> Path:
    """Write a self-contained d6 diagram for the recorder to drive.

    Inlines plotly.js rather than using the committed CDN build: a recording
    that silently produces an empty page when the network is down is worse than
    one that cannot start.
    """
    from tanabesugano.cmd import CMDmain

    previous = Path.cwd()
    os.chdir(out_dir)
    try:
        cmd = CMDmain(Dq=DQ_MAX, B=B, C=C, nroots=NROOTS, d_count=D_COUNT)
        cmd.calculation()
        with contextlib.redirect_stdout(None):
            cmd.interactive_plot(include_plotlyjs=True)
        return out_dir / f"{cmd.title_TS}.html"
    finally:
        os.chdir(previous)


def _record(
    page: Page,
    plot_box: FloatRect,
    shots: list[tuple[bytes, int]],
) -> None:
    """Drive one pass of hover -> isolate -> zoom -> reset, capturing frames."""
    left = plot_box["x"]
    top = plot_box["y"]
    width = plot_box["width"]
    height = plot_box["height"]

    def shoot(hold_ms: int = FRAME_MS) -> None:
        shots.append((page.screenshot(type="png"), hold_ms))

    shoot(HOLD_MS)

    # 1. Sweep the cursor across the diagram: plotly raises a hover tooltip at
    #    the nearest point, which is the whole reason the diagram is interactive.
    for step in range(10):
        fraction = 0.12 + 0.76 * step / 9
        page.mouse.move(left + width * fraction, top + height * 0.62)
        page.wait_for_timeout(90)
        shoot()
    shoot(HOLD_MS)

    # 2. Double-click a legend entry to isolate one term -- the gesture that
    #    turns a 43-curve diagram into a readable single band.
    legend = page.query_selector_all(".legendtoggle")
    if legend:
        legend[min(2, len(legend) - 1)].dblclick()
        page.wait_for_timeout(700)
        shoot(HOLD_MS + 350)
        legend[min(2, len(legend) - 1)].dblclick()
        page.wait_for_timeout(700)
        shoot(HOLD_MS)

    # 3. Drag-zoom into the low-field region, then double-click to reset.
    page.mouse.move(left + width * 0.10, top + height * 0.25)
    page.mouse.down()
    for step in range(1, 7):
        page.mouse.move(
            left + width * (0.10 + 0.32 * step / 6),
            top + height * (0.25 + 0.50 * step / 6),
        )
        page.wait_for_timeout(60)
        shoot()
    page.mouse.up()
    page.wait_for_timeout(800)
    shoot(HOLD_MS + 350)

    page.mouse.dblclick(left + width * 0.5, top + height * 0.5)
    page.wait_for_timeout(900)
    shoot(HOLD_MS)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT,
        help=f"where to write the GIF (default: {OUTPUT.relative_to(REPO_ROOT)})",
    )
    args = parser.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sys.stderr.write(
            "playwright is not installed. Run:\n"
            "  uv sync --group screenshot\n"
            "  uv run playwright install chromium\n",
        )
        return 1

    import io

    from PIL import Image

    with tempfile.TemporaryDirectory() as tmp:
        diagram = _build_offline_diagram(Path(tmp))
        shots: list[tuple[bytes, int]] = []
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            try:
                page = browser.new_page(viewport=VIEWPORT, device_scale_factor=1)
                page.goto(diagram.as_uri())
                page.wait_for_selector(".js-plotly-plot", timeout=60_000)
                page.wait_for_timeout(2_500)
                plot = page.query_selector(".js-plotly-plot")
                box = plot.bounding_box() if plot is not None else None
                if box is None:
                    sys.stderr.write("the plot never laid out; nothing to record\n")
                    return 1
                _record(page, box, shots)
            finally:
                browser.close()

    if not shots:
        sys.stderr.write("no frames captured\n")
        return 1

    frames = [Image.open(io.BytesIO(shot)).convert("RGB") for shot, _hold in shots]
    durations = [hold for _shot, hold in shots]
    quantized = [
        frame.quantize(colors=GIF_COLORS, method=Image.Quantize.MEDIANCUT) for frame in frames
    ]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    quantized[0].save(
        args.output,
        save_all=True,
        append_images=quantized[1:],
        duration=durations,
        loop=0,
        optimize=True,
        disposal=2,
    )
    size_mb = args.output.stat().st_size / 1e6
    sys.stdout.write(
        f"wrote {_display_path(args.output)} ({len(quantized)} frames, {size_mb:.1f} MB)\n",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
