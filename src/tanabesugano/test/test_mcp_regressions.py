"""Regression guards for defects found while driving the MCP server by hand.

Scope note. A session against ``2.0.0-alpha.1`` reported eleven defects; on
re-verification against this tree four had already been fixed and one was never
ours. Only what still reproduces is guarded here:

``TestZeroFieldIsNotASamplePoint``
    root cause A -- the ground term is read off the Dq = 0 sample point.
``TestDashboardSparkline``
    W6 -- the dashboard's first-excited-state curve spikes at the origin.
``TestHeatmapEnergyAxis``
    F7 -- the density heatmap's energy axis is not explicitly oriented, so
    it renders inverted: 0 at the top, 40,000 at the bottom.
``TestDocumentedBehaviour``
    W8 -- the landscape silently drops every d-count's ground manifold.
    W3 -- ``dq_max`` is in Dq, while the same chart's axis is Delta = 10*Dq.
``TestFitReportsWhetherCWasConstrained``
    W1 -- a fit reports C with no way to tell a fitted value from a default.

Deliberately NOT guarded here, to keep one claim in one place
(CLAUDE.md Testing rule 3):

- ``reference_ground_term`` agreeing with ``HIGH_SPIN_GROUND_TERM`` for all
  seven configurations. ``test_spectrum_fitting.py`` already pins that, and a
  second copy at a second tolerance would let the looser mask the tighter.
- Free-ion term *energies*. ``test_matrices_invariants.py`` is the only place
  that asserts against ``free_ion``. This module consumes the ``OH_REDUCTION``
  character table but never re-pins a closed form.
"""

from __future__ import annotations

import ast
import asyncio
import inspect
import json
import pathlib
import re
import shutil
import subprocess
import tempfile

from typing import TYPE_CHECKING

import pytest

from tanabesugano.free_ion import free_ion_levels
from tanabesugano.mcp import _compute as ts_compute
from tanabesugano.mcp import apps as ts_apps
from tanabesugano.mcp import plotting as ts_plotting
from tanabesugano.mcp._compute import SUPPORTED_D_COUNTS
from tanabesugano.mcp._compute import compute_point
from tanabesugano.mcp._defaults import DEFAULTS
from tanabesugano.mcp.server import create_server


if TYPE_CHECKING:
    from types import ModuleType


D_COUNTS = sorted(SUPPORTED_D_COUNTS)

# Every module under mcp/ that sweeps Dq and could be tempted to read the
# degenerate sample point. plotting.py is included precisely because it does
# use `points[0]` -- legitimately, for `.keys()`, which the ban exempts.
MCP_MODULES = (ts_apps, ts_compute, ts_plotting)


def defaults_for(d_count: int) -> tuple[float, float]:
    """The (B, C) this configuration's own tools use when the caller omits them."""
    cfg = DEFAULTS[d_count]
    return cfg["default_B"], cfg["default_C"]


def call_tool(name: str, **kwargs):
    """Invoke a registered MCP tool by name and return its raw result."""

    async def go():
        server = create_server()
        tool = await server.get_tool(name)
        return tool.fn(**kwargs)

    return asyncio.run(go())


@pytest.fixture(scope="module")
def density_payload() -> dict:
    """The Chart.js payload of the density-mode oxidation landscape."""
    result = call_tool("ts_oxidation_landscape_app", style="density")
    assert not result.is_error, result.content[0].text
    return json.loads(result.content[0].text)


# The sandbox globals the widget script touches before it reaches Chart.js, plus
# a Chart stand-in that records the config instead of drawing it. The network
# import of the MCP Apps SDK is stripped: it is unreachable from a test runner,
# and nothing below the toolbar wiring depends on the real App.
_JS_HARNESS_PRELUDE = """
const captured = [];
class Chart {
  constructor(_ctx, cfg) { captured.push(cfg); }
  destroy() {}
  toBase64Image() { return ""; }
}
class App { connect() {} callServerTool() {} }
const el = () => ({
  style: {}, classList: { toggle() {}, add() {}, remove() {} },
  addEventListener() {}, getContext: () => ({}), toBlob() {}, textContent: "",
});
const document = { getElementById: el };
const setTimeout = () => {};
"""

_JS_HARNESS_EPILOGUE = """
app.ontoolresult({ content: [{ type: "text", text: process.argv[2] }] });
console.log(JSON.stringify(captured[0].options.scales.y));
"""


def _brace_block(text: str, search_from: int) -> str:
    """The balanced ``{ ... }`` run starting at the first brace at or after an index."""
    depth = 0
    for offset in range(text.index("{", search_from), len(text)):
        if text[offset] == "{":
            depth += 1
        elif text[offset] == "}":
            depth -= 1
            if depth == 0:
                return text[search_from : offset + 1]
    msg = f"unbalanced braces from offset {search_from}"
    raise AssertionError(msg)


def _chart_scripts() -> list[str]:
    """Every ``<script>`` body in the module that constructs a Chart.js chart."""
    source = inspect.getsource(ts_apps)
    return [
        body
        for body in re.findall(r"<script[^>]*>(.*?)</script>", source, re.DOTALL)
        if "new Chart(" in body
    ]


def _y_scale_blocks(script: str) -> list[str]:
    """Every ``y: { ... }`` found inside a ``scales: { ... }`` in one script.

    Anchored on ``scales:`` rather than on a bare ``y:`` because the payload's
    own cells are ``{x, y, v}`` objects and would otherwise match.
    """
    blocks = []
    for scales in re.finditer(r"\bscales:\s*\{", script):
        scope = _brace_block(script, scales.start())
        for y_at in re.finditer(r"\by:\s*\{", scope):
            blocks.append(_brace_block(scope, y_at.start()))
    return blocks


def _render_y_scale(style: str) -> dict:
    """The y-scale Chart.js would receive, by running the widget's own script."""
    bodies = [b for b in _chart_scripts() if "chart_type === 'heatmap'" in b]
    assert len(bodies) == 1, f"expected one live chart <script> in apps.py, found {len(bodies)}"
    script = re.sub(r"^\s*import \{ App \}.*$", "", bodies[0], count=1, flags=re.MULTILINE)

    result = call_tool("ts_oxidation_landscape_app", style=style)
    assert not result.is_error, result.content[0].text

    with tempfile.TemporaryDirectory() as tmp:
        entry = pathlib.Path(tmp) / "widget.mjs"
        entry.write_text(_JS_HARNESS_PRELUDE + script + _JS_HARNESS_EPILOGUE)
        completed = subprocess.run(  # noqa: S603 - fixed argv, no shell
            [shutil.which("node") or "node", str(entry), result.content[0].text],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    assert completed.returncode == 0, f"widget JS failed:\n{completed.stderr}"
    return json.loads(completed.stdout)


class TestZeroFieldIsNotASamplePoint:
    """Why no code may read the Dq = 0 point to decide *which* term is lowest.

    At Dq = 0 the ligand field vanishes, so every octahedral component of the
    free-ion ground term sits at exactly the same energy. Picking a minimum
    there is a tie-break over equals, and ``ground_term``'s ``sorted()`` names
    an arbitrary member -- ``5_E`` for d6, where the weak-field answer is
    ``5_T_2``. ``_compute.crossover_dq`` documents this; ``_compute.
    reference_ground_term`` is the supported way to ask the question.
    """

    @pytest.mark.parametrize("d_count", D_COUNTS)
    def test_zero_field_ground_manifold_is_exactly_degenerate(self, d_count: int) -> None:
        """The tie is real, and as wide as the character table says.

        The expected count is *derived* from ``free_ion.OH_REDUCTION`` (F -> 3
        components, D -> 2, S -> 1), not hardcoded here, so this cannot drift
        from the reduction it is meant to describe. Passes today and must keep
        passing: it is the standing justification for the two guards below,
        not a bug report.
        """
        B, C = defaults_for(d_count)
        free_ion_ground = min(free_ion_levels(d_count, B, C), key=lambda lv: lv.energy_cm1)
        expected_components = len(free_ion_ground.oh_irreps)

        levels = compute_point(d_count, 0.0, B, C)
        lowest = min(min(v) for v in levels.values() if len(v))
        tied = [t for t, v in levels.items() if len(v) and min(v) <= lowest + 1e-6]

        assert len(tied) == expected_components, (
            f"d{d_count}: free-ion ground term {free_ion_ground.symbol} reduces to "
            f"{free_ion_ground.oh_irreps} ({expected_components} components) but "
            f"{len(tied)} terms are degenerate at Dq=0: {sorted(map(str, tied))}"
        )

    def test_sweep_payload_derives_no_ground_term(self) -> None:
        """``_sweep_payload`` must not return a ground-state y value.

        It used to compute one by taking ``min(points[0], key=...)`` -- the
        forbidden pattern -- and every one of its seven call sites discarded
        the result. A wrong value nobody reads produces no failing test and no
        complaint, which is how this survived the pass that fixed three
        sibling call sites. The slot is removed rather than corrected so there
        is no tempting local ``min()`` left to copy.

        Observed failure before the fix::

            AssertionError: _sweep_payload returns 7 values; the 7th is the
            ground_y computed from the Dq=0 point. Expected 6.
        """
        returned = ts_apps._sweep_payload(
            d_count=3,
            dq_min=0.0,
            dq_max=1500.0,
            steps=10,
            b_val=918.0,
            c_val=4133.0,
            normalize=True,
        )
        assert len(returned) == 6, (
            f"_sweep_payload returns {len(returned)} values; the 7th is the "
            f"ground_y computed from the Dq=0 point. Expected 6."
        )

    @pytest.mark.parametrize("module", MCP_MODULES, ids=lambda m: m.__name__.rsplit(".", 1)[-1])
    def test_no_mcp_module_indexes_the_zero_field_point(self, module: ModuleType) -> None:
        """Ban ``points[0]`` as a value anywhere under ``mcp/``.

        Paired with the numeric guard above rather than standing alone: a
        structural test cannot prove the physics, but it is the only thing that
        catches the pattern being reintroduced at a seventh call site.

        Parsed, not grepped. A text search cannot tell code from the prose
        *describing* the code, and the first draft of this test duly failed on
        the docstring in ``_sweep_payload`` that explains why the pattern was
        removed -- a false positive, so the test was wrong and was fixed rather
        than the source being reworded around it.

        ``points[0].keys()`` is exempt and reached on purpose: naming the terms
        is fine at any Dq, because the *set* of terms does not change across
        the sweep. Only reading energies at the degenerate point is banned,
        which is what every other use of the subscript does.

        Two observed failures, and they are different observations. The
        grep-based first draft, run against the real unfixed source::

            AssertionError: ground term derived from the Dq=0 sample point in
            apps.py: ['        points[0],', '        key=lambda t:
            min(points[0][t]) if points[0][t] else float("inf"),']

        This AST version never saw that source -- it was written after the fix,
        to clear the docstring false positive -- so its red was produced by
        reintroducing the pattern deliberately and confirming it fires::

            AssertionError: apps.py reads energies from the Dq=0 sample point
            at line(s) [160, 160]
        """
        tree = ast.parse(inspect.getsource(module))
        exempt = {
            id(node.value)
            for node in ast.walk(tree)
            if isinstance(node, ast.Attribute) and node.attr == "keys"
        }
        offenders = sorted(
            node.lineno
            for node in ast.walk(tree)
            if isinstance(node, ast.Subscript)
            and isinstance(node.value, ast.Name)
            and node.value.id == "points"
            and isinstance(node.slice, ast.Constant)
            and node.slice.value == 0
            and id(node) not in exempt
        )
        assert not offenders, (
            f"{module.__name__.rsplit('.', 1)[-1]}.py reads energies from the "
            f"Dq=0 sample point at line(s) {offenders}"
        )


class TestDashboardSparkline:
    """W6 -- the dashboard's 'first excited state vs Dq' curve.

    ``ground_eps`` correctly excludes the ground manifold, but at exactly
    Dq = 0 the first *excited* component is inside that same degenerate
    manifold, so the search falls through to the next free-ion term entirely --
    a gap tens of thousands of cm-1 above the curve it belongs to.
    """

    @pytest.mark.parametrize("d_count", D_COUNTS)
    def test_curve_has_no_origin_spike(self, d_count: int) -> None:
        """The first two points must not differ by more than 3x.

        3x is deliberately generous: the real defect is 26x-48x, and the
        genuine physical rise between adjacent Dq steps is about 2x (the
        second point is roughly twice the first once the field is on). d5 is
        the control -- 6S is an orbital singlet, so it has no zero-field
        degeneracy and never spiked.

        Observed failure before the fix (d6, worst case)::

            AssertionError: d6: first excited state jumps 24,740 -> 517 cm^-1
            between the first two Dq points (47.8x) -- the Dq=0 point reports a
            different manifold than the rest of the curve.
        """
        B, C = defaults_for(d_count)
        curve = ts_apps._first_excited_curve(d_count, B, C)

        first, second = curve[0], curve[1]
        ratio = first / second if second else float("inf")
        assert ratio <= 3.0, (
            f"d{d_count}: first excited state jumps {first:,.0f} -> {second:,.0f} cm^-1 "
            f"between the first two Dq points ({ratio:.1f}x) -- the Dq=0 point "
            f"reports a different manifold than the rest of the curve."
        )

    @pytest.mark.parametrize("d_count", D_COUNTS)
    def test_curve_keeps_every_requested_sample(self, d_count: int) -> None:
        """``steps`` points requested, ``steps`` points returned.

        Guards the fix from the other side. Deleting the offending sample would
        also silence the ratio test above, and would quietly hand the caller a
        29-point curve for a 30-step sweep; the supported fix is to start the
        sweep above zero, which keeps the resolution the caller asked for.

        Passes today -- the current curve is the right length and merely wrong
        at one end -- so this is a constraint on the fix, not a bug report.

        (An earlier draft asserted the curve was non-decreasing. That is false
        physics: for high-spin d5 the lowest excited level is 4T1(G), which
        *descends* as the field turns on, by 497 cm^-1 per step here. The test
        was wrong, not the code.)
        """
        B, C = defaults_for(d_count)
        curve = ts_apps._first_excited_curve(d_count, B, C, steps=30)
        assert len(curve) == 30, (
            f"d{d_count}: asked for 30 sweep points, got {len(curve)} -- the origin "
            f"spike was removed by dropping a sample rather than by moving the "
            f"sweep start above Dq=0."
        )


class TestHeatmapEnergyAxis:
    """F7 -- ``ts_oxidation_landscape_app(style='density')`` renders y inverted.

    ``chartjs-chart-matrix`` lays cells out row-major like a spreadsheet, so an
    unconstrained linear y-scale puts the first row at the top: 0 cm-1 at the
    top of the figure and 40,000 at the bottom. The figure then asserts that
    energy decreases upward, which is false, and disagrees with every other
    chart the package draws.
    """

    @pytest.mark.skipif(shutil.which("node") is None, reason="needs node to run the widget JS")
    @pytest.mark.parametrize(
        ("style", "expect_bounds"),
        [("density", True), ("scatter", False)],
    )
    def test_rendered_scale_orients_energy_upward(self, style: str, expect_bounds: bool) -> None:
        """Run the real widget JS on the real payload and read the scale back.

        The two source assertions below can only see that the *characters*
        ``reverse`` and ``min`` appear near a ``y:``. They would pass just as
        happily if the JS read ``p.y_minimum`` while the payload sent
        ``y_min``, which is the whole failure mode -- a wiring bug between two
        languages that neither language's tooling checks. Executing the branch
        is the only thing that proves the payload actually reaches the axis.

        Skipped rather than failed where node is absent, so this can never
        report a false green.
        """
        scale = _render_y_scale(style)
        assert scale.get("reverse") is False, (
            f"{style}: rendered y-scale does not force energy upward: {scale}"
        )
        if expect_bounds:
            assert scale.get("min") == pytest.approx(0.0)
            assert scale.get("max") == pytest.approx(40000.0)

    def test_payload_declares_its_energy_bounds(self, density_payload: dict) -> None:
        """The bounds must be pinned by the payload, not inferred from cells.

        The data assertion, paired with the source assertions below: which
        cells happen to be present depends on ``max_energy_cm`` and on how many
        eigenvalues clear the ground threshold, so letting Chart.js infer the
        extent makes the axis depend on the data rather than on the request.

        Observed failure before the fix::

            KeyError: 'y_min'
        """
        assert density_payload["y_min"] == pytest.approx(0.0)
        assert density_payload["y_max"] == pytest.approx(40000.0)

    def test_heatmap_y_scale_is_explicitly_oriented(self) -> None:
        """The heatmap y-scale must state its direction and its bounds.

        Observed failure before the fix::

            AssertionError: heatmap y-scale does not set 'reverse': "y: {
            type: 'linear', title: { display: true, text: p.y_label || '',
            font: { size: 12 } } }"
        """
        block = self._y_scale_block("chart_type === 'heatmap'")
        for key in ("reverse", "min", "max"):
            assert key in block, f"heatmap y-scale does not set {key!r}: {block!r}"

    def test_scatter_y_scale_is_explicitly_oriented(self) -> None:
        """The scatter mode reads correctly today; pin it so it stays that way.

        Observed failure before the fix::

            AssertionError: scatter y-scale does not set 'reverse': "y: {
            title: { display: true, text: p.y_label || '', font: { size: 12 }
            }, ticks: { maxTicksLimit: 8 }, }"
        """
        block = self._y_scale_block("Default line/scatter mode")
        assert "reverse" in block, f"scatter y-scale does not set 'reverse': {block!r}"

    def test_every_chart_renderer_orients_its_energy_axis(self) -> None:
        """No y-scale anywhere in this module may leave its direction unstated.

        The two tests above name their branch, so they only see the renderer
        they were written against. That is how a *second* Chart.js renderer sat
        in this module for the whole of the F7 investigation carrying the
        identical un-oriented y-scale: ``_HEATMAP_HTML``, kept for the removed
        ``ts_parameter_heatmap_app``. It was unreachable, so it broke nothing --
        but it was one re-registration away from reintroducing the bug, and no
        anchored test would have noticed.

        This one is not anchored. Every ``y:`` inside every ``scales:`` inside
        every chart-constructing ``<script>`` has to say which way energy goes.

        Observed failure before ``_HEATMAP_HTML`` was deleted::

            AssertionError: y-scale does not state its direction in chart
            script 2/2: "y: { type: 'linear', title: { display: true, text:
            payload.y_label } }"
        """
        scripts = _chart_scripts()
        assert scripts, "no chart-constructing <script> found in apps.py"

        offenders = [
            f"chart script {i}/{len(scripts)}: {block!r}"
            for i, script in enumerate(scripts, start=1)
            for block in _y_scale_blocks(script)
            if "reverse" not in block
        ]
        assert not offenders, "y-scale does not state its direction in " + "; ".join(offenders)

    @staticmethod
    def _y_scale_block(anchor: str) -> str:
        """The ``y: { ... }`` scale object following ``anchor`` in the embedded JS.

        Brace-matched rather than line-matched: the two branches are written
        differently -- the heatmap's y-scale is a single line indented 14, the
        scatter's spans four lines indented 12 -- and an earlier draft that
        assumed one shape failed with ``ValueError: substring not found``,
        which is a broken test rather than a detected defect.
        """
        source = inspect.getsource(ts_apps)
        window = source[source.index(anchor) :]
        return _brace_block(window, window.index("y: {", window.index("scales: {")))


class TestDocumentedBehaviour:
    """W8 and W3 -- behaviour a caller cannot discover from the signature."""

    def test_landscape_documents_the_ground_state_exclusion(self) -> None:
        """Both landscape modes drop every level at or below 1 cm-1.

        That is every d-count's ground state, so the chart shows excited states
        only. Defensible, but a reader counting levels against a term table
        will come up one short per configuration and have no way to find out
        why.

        Observed failure before the fix::

            AssertionError: ts_oxidation_landscape_app does not document that
            the ground manifold is excluded.
        """
        doc = self._docstring_of("def ts_oxidation_landscape_app")
        assert "ground" in doc.lower(), (
            "ts_oxidation_landscape_app does not document that the ground manifold is excluded."
        )

    def test_spin_crossover_documents_dq_max_units(self) -> None:
        """``dq_max`` is Dq, while the chart's own axis is Delta = 10*Dq.

        The docstring opens 'vs Delta' and then takes a bound in Dq. A caller
        converting a published Delta lands an order of magnitude out, and the
        tool answers with a plausible chart rather than an error.

        Observed failure before the fix::

            AssertionError: ts_spin_crossover_app does not relate dq_max to
            Delta = 10*Dq where dq_max is described.
        """
        doc = self._docstring_of("def ts_spin_crossover_app")
        dq_max_at = doc.index("dq_max:")
        described = doc[dq_max_at : dq_max_at + 400]
        assert any(marker in described for marker in ("10·Dq", "10*Dq", "Δ/10", "Delta/10")), (
            "ts_spin_crossover_app does not relate dq_max to Delta = 10*Dq "
            "where dq_max is described."
        )

    @staticmethod
    def _docstring_of(signature: str) -> str:
        source = inspect.getsource(ts_apps)
        start = source.index(signature)
        window = source[start:]
        opening = window.index('"""')
        closing = window.index('"""', opening + 3)
        return window[opening : closing + 3]


class TestFitReportsWhetherCWasConstrained:
    """W1 -- a fitted C that the data never constrained looks like a result.

    ``SpectrumFit`` reports C beside Dq and B with nothing to separate them, so
    two unrelated complexes come back with byte-identical C and a reader has no
    signal that the optimizer never moved it.

    The measured picture is narrower than 'd2 and d8', which is what
    ``fit_spectrum``'s docstring currently claims. Sweeping C over 3000-5200 at
    Dq in {400 .. 2600} and B in {700 .. 1300}: d2, d3 and d8 are C-independent
    everywhere, while d4, d5, d6 and d7 acquire C-dependence only past their
    spin crossover, where the spin-allowed set becomes the *low-spin* manifold.
    So the flag has to be derived per fit, not looked up per d-count -- the
    same lesson that retired the hand-maintained ground-term table.
    """

    @pytest.mark.parametrize("d_count", [2, 3, 8])
    def test_flag_is_set_when_the_bands_cannot_constrain_C(self, d_count: int) -> None:
        """A high-spin fit on a C-independent manifold must say so.

        Observed failure before the fix::

            AttributeError: 'SpectrumFit' object has no attribute 'c_is_default'
        """
        from tanabesugano.mcp._compute import fit_spectrum

        bands = {
            2: [11000.0, 17000.0, 25000.0],
            3: [17400.0, 24500.0, 37800.0],
            8: [8500.0, 13800.0, 25300.0],
        }[d_count]
        fit = fit_spectrum(d_count, bands)
        assert fit.c_is_default is True, (
            f"d{d_count}: the spin-allowed manifold does not depend on C, but the "
            f"fit reports C={fit.C} with no indication it was never constrained."
        )

    def test_flag_is_clear_when_the_caller_pins_C(self) -> None:
        """An explicitly supplied C is the caller's value, not a default.

        Observed failure before the fix::

            AttributeError: 'SpectrumFit' object has no attribute 'c_is_default'
        """
        from tanabesugano.mcp._compute import fit_spectrum

        fit = fit_spectrum(8, [8500.0, 13800.0, 25300.0], C=4200.0)
        assert fit.c_is_default is False, (
            "C was supplied by the caller but the fit reports it as a default."
        )
