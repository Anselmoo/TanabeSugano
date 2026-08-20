"""End-to-end screenshot tests for MCP app tools via Playwright.

Skips when either fastmcp or playwright is not installed.

Run with:
    uv run pytest -m screenshot --browser chromium

Screenshots are saved to test-screenshots/ at the project root.
"""

from __future__ import annotations

import asyncio
import base64
import concurrent.futures
import contextlib
import json
import tempfile

from pathlib import Path

import pytest


pytest.importorskip("fastmcp", reason="install with `pip install tanabesugano[mcp]`")
pytest.importorskip("playwright", reason="install with `uv sync --group screenshot`")

pytestmark = pytest.mark.screenshot

_SCREENSHOTS_DIR = Path(__file__).parents[3] / "test-screenshots"


# ─────────────────────────── shared helpers ──────────────────────────────────


def _call(tool: str, args: dict) -> object:
    """Call an MCP tool via a worker thread (owns a fresh event loop).

    Running asyncio.run() from the main thread fails when anyio's pytest
    plugin has already started a loop there.  A ThreadPoolExecutor worker
    always starts loop-free, so asyncio.run() works unconditionally.
    """
    from fastmcp import Client

    from tanabesugano.mcp.server import create_server

    async def _go():
        server = create_server()
        async with Client(server) as client:
            return await client.call_tool(tool, args)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(lambda: asyncio.run(_go())).result()


def _prefab_html(structured_content: dict) -> str:
    """Build a self-contained (bundled) HTML page from a PrefabApp structured_content dict."""
    from prefab_ui.app import PrefabApp

    app = PrefabApp.model_validate(structured_content)
    return app.html(renderer_mode="bundled")


def _take_screenshot(
    page: object,
    html: str,
    filename: str,
    *,
    wait_selector: str = "#root > *",
    paint_selector: str | None = "svg.recharts-surface",
    timeout: int = 45_000,
) -> Path:
    """Load *html* in *page* via a temp file, wait for content to paint, save PNG.

    Writing to a temp file and using page.goto() is more reliable than
    set_content() for large HTML blobs (>1 MB) because the browser reads
    from disk rather than receiving the HTML over an internal pipe.
    """
    _SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    dest = _SCREENSHOTS_DIR / filename

    with tempfile.NamedTemporaryFile(
        suffix=".html",
        delete=False,
        mode="w",
        encoding="utf-8",
    ) as tmp:
        tmp.write(html)
        tmp_path = Path(tmp.name)
    try:
        page.goto(f"file://{tmp_path}", wait_until="load")  # type: ignore[attr-defined]
        if wait_selector:
            page.wait_for_selector(wait_selector, timeout=timeout)  # type: ignore[attr-defined]
        if paint_selector:
            # Best-effort: wait for chart SVG after React mounts.
            with contextlib.suppress(Exception):
                page.wait_for_selector(paint_selector, timeout=10_000)  # type: ignore[attr-defined]
        page.screenshot(path=str(dest), full_page=True)  # type: ignore[attr-defined]
    finally:
        tmp_path.unlink(missing_ok=True)
    return dest


# ─────────────────────────── PrefabApp tools ─────────────────────────────────


# ts_diagram_app d5 and d6 — the reference case from the user story.
# ts_compare_app overlays multiple d-configurations on one chart.
@pytest.mark.parametrize(
    ("tool", "args", "filename"),
    [
        pytest.param(
            "ts_diagram_app",
            {"d_count": 5, "steps": 15},
            "ts_diagram_app_d5.png",
            marks=pytest.mark.xfail(
                reason="ts_diagram_app has a Slider with reactive state; "
                "its Prefab renderer requires a live MCP bridge to mount React. "
                "Use ts_compare_app for static d-config screenshots.",
                strict=False,
            ),
        ),
        pytest.param(
            "ts_diagram_app",
            {"d_count": 6, "steps": 15},
            "ts_diagram_app_d6.png",
            marks=pytest.mark.xfail(
                reason="ts_diagram_app has a Slider with reactive state; "
                "its Prefab renderer requires a live MCP bridge to mount React. "
                "Use ts_compare_app for static d-config screenshots.",
                strict=False,
            ),
        ),
        (
            "ts_dashboard_app",
            {},
            "ts_dashboard.png",
        ),
    ],
)
def test_prefab_app_screenshot(page: object, tool: str, args: dict, filename: str) -> None:
    """Render a PrefabApp tool to a PNG screenshot via bundled Prefab renderer."""
    result = _call(tool, args)
    sc = result.structured_content  # type: ignore[attr-defined]
    assert sc is not None, f"{tool} returned no structured_content"
    assert "$prefab" in sc, "structured_content missing $prefab key"

    html = _prefab_html(sc)
    dest = _take_screenshot(page, html, filename)
    assert dest.exists()
    assert dest.stat().st_size > 0


# ─────────────────────────── ts_plot_png (no Playwright) ─────────────────────


@pytest.mark.parametrize(
    ("d_count", "filename", "normalize"),
    [
        (5, "ts_plot_png_d5.png", True),
        (6, "ts_plot_png_d6.png", True),
        (3, "ts_plot_png_d3.png", True),
        (5, "ts_plot_png_d5_eV.png", False),
        (6, "ts_plot_png_d6_eV.png", False),
    ],
)
def test_plot_png_saves_file(d_count: int, filename: str, normalize: bool) -> None:
    """ts_plot_png already returns raw PNG bytes — decode and save directly."""
    result = _call("ts_plot_png", {"d_count": d_count, "steps": 60, "normalize": normalize})
    image_content = next(
        (c for c in result.content if getattr(c, "type", None) == "image"),  # type: ignore[attr-defined]
        None,
    )
    assert image_content is not None, "ts_plot_png returned no image content"
    png_bytes = base64.b64decode(image_content.data)

    _SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    dest = _SCREENSHOTS_DIR / filename
    dest.write_bytes(png_bytes)
    assert dest.stat().st_size > 0


# ─────────────────────────── Chart.js ToolResult tools ───────────────────────


@pytest.mark.parametrize(
    ("tool", "args", "filename", "x_max", "y_max"),
    [
        (
            # d5 (Mn2+/Fe3+): half-filled shell, spin-forbidden lines near 2.5-3 eV.
            # dq_max=2500 cm-1 keeps the y-axis in the 0-3 eV window.
            "ts_plot_view",
            {"d_count": 5, "steps": 60, "normalize": False, "energy_unit": "eV", "dq_max": 2500.0},
            "ts_plot_view_d5_eV.png",
            None,
            3.0,
        ),
        (
            # d6 (Fe2+/Co3+): 5D ground term; 5T2->5E rises to 3 eV at Dq=2500 cm-1.
            "ts_plot_view",
            {"d_count": 6, "steps": 60, "normalize": False, "energy_unit": "eV", "dq_max": 2500.0},
            "ts_plot_view_d6_eV.png",
            None,
            3.0,
        ),
        (
            # d6 simulated spectrum: Dq=1000 cm-1 (typical Fe2+/Co3+).
            # Spin-allowed 5T2->5E at ~1.24 eV; x_max=3 clips display to 0-3 eV.
            "ts_spectrum_app",
            {"d_count": 6, "Dq": 1000.0, "energy_unit": "eV", "broadening": 2000.0},
            "ts_spectrum_d6_eV.png",
            3.0,
            None,
        ),
    ],
)
def test_chartjs_tool_screenshot(
    page: object,
    tool: str,
    args: dict,
    filename: str,
    x_max: float | None,
    y_max: float | None,
) -> None:
    """Render a Chart.js ToolResult tool via a lightweight standalone HTML page."""
    result = _call(tool, args)
    text_content = next(
        (c.text for c in result.content if hasattr(c, "text")),  # type: ignore[attr-defined]
        None,
    )
    assert text_content, f"{tool} returned no text content"

    payload = json.loads(text_content)
    html = _build_chartjs_html(payload, x_max=x_max, y_max=y_max)

    # Chart.js renders into <canvas id="c"> (no #root div); paint is synchronous.
    dest = _take_screenshot(page, html, filename, wait_selector="canvas#c", paint_selector=None)
    assert dest.exists()
    assert dest.stat().st_size > 0


def _build_chartjs_html(
    payload: dict,
    *,
    x_max: float | None = None,
    y_min: float | None = None,
    y_max: float | None = None,
) -> str:
    """Minimal self-contained Chart.js page from a ts_plot_view JSON payload.

    y_min / y_max clip the y-axis to a specific range (e.g. 0-3 eV).
    Pass None to let Chart.js auto-scale.
    """
    series_json = json.dumps(payload.get("series", []))
    title = json.dumps(payload.get("title", ""))
    x_label = json.dumps(payload.get("x_label", ""))
    y_label = json.dumps(payload.get("y_label", ""))
    x_max_js = json.dumps(x_max)
    y_min_js = json.dumps(y_min)
    y_max_js = json.dumps(y_max)
    return f"""\
<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>TS Chart</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>
</head>
<body style="margin:0;padding:1rem;background:#fff">
  <canvas id="c" width="900" height="550"></canvas>
  <script>
    const series = {series_json};
    new Chart(document.getElementById("c"), {{
      type: "line",
      data: {{
        datasets: series.map(s => ({{
          label: s.label || s.data_key,
          borderColor: s.color || "#888",
          borderDash: s.borderDash,
          data: s.data,
          pointRadius: 0,
          borderWidth: 1.5,
          tension: 0,
        }}))
      }},
      options: {{
        responsive: false,
        animation: false,
        plugins: {{
          title: {{ display: true, text: {title} }},
          legend: {{ position: "right" }},
        }},
        scales: {{
          x: {{ type: "linear", max: {x_max_js}, title: {{ display: true, text: {x_label} }} }},
          y: {{
            min: {y_min_js},
            max: {y_max_js},
            title: {{ display: true, text: {y_label} }},
          }},
        }},
      }},
    }});
  </script>
</body>
</html>"""
