"""Contract tests for vector export from ``ts_plot_png``.

The tool hardcoded ``format="png"`` in ``fig.savefig``, so a publication-bound
user could get a raster image and nothing else. These pin the three formats and
their MIME types.

Why MIME types are asserted here rather than left to a helper: FastMCP's
``File(data=..., format=...)`` maps a bare extension to ``application/<ext>``,
so ``format="svg"`` yields ``application/svg`` and ``format="png"`` yields
``application/png``. Both are wrong -- the registered types are
``image/svg+xml`` and ``image/png`` -- and no client renders them. The
assertions below exist so a future switch to that helper cannot pass silently.

Provenance of the expected values: file-format magic numbers (``%PDF-`` from
the PDF 1.7 spec / ISO 32000-1 §7.5.2, ``<svg`` from the SVG 1.1 DTD, and the
8-byte PNG signature from RFC 2083 §3.1) and the IANA media type registry.
None of these are produced by, or knowable from, the code under test.
"""

from __future__ import annotations

import base64

import pytest

from tanabesugano.mcp.server import create_server
from tanabesugano.test._loop import run_loop_free


PNG_MAGIC = b"\x89PNG\r\n\x1a\n"  # RFC 2083 section 3.1


def call_plot(**kwargs):
    async def go():
        server = create_server()
        tool = await server.get_tool("ts_plot_png")
        return tool.fn(**kwargs)

    return run_loop_free(go)


def payload_bytes(result) -> bytes:
    """Decode the single binary block a render returns, whatever its wrapper."""
    block = result.content[0]
    if hasattr(block, "data"):  # ImageContent
        return base64.b64decode(block.data)
    return base64.b64decode(block.resource.blob)  # EmbeddedResource


def mime_of(result) -> str:
    block = result.content[0]
    return block.mimeType if hasattr(block, "mimeType") else block.resource.mimeType


ARGS = {"d_count": 8, "steps": 6}


def test_png_remains_the_default_and_is_a_real_png() -> None:
    """The default path must not change: PNG, inline, as an image block."""
    result = call_plot(**ARGS)
    assert payload_bytes(result).startswith(PNG_MAGIC)
    assert mime_of(result) == "image/png"


def test_pdf_export_returns_a_real_pdf() -> None:
    """Observed failure before the fix, verbatim::

    TypeError: ts_plot_png() got an unexpected keyword argument 'format'
    """
    result = call_plot(**ARGS, format="pdf")
    assert payload_bytes(result).startswith(b"%PDF-")
    assert mime_of(result) == "application/pdf"


def test_svg_export_returns_real_svg_markup() -> None:
    """Observed failure before the fix, verbatim::

    TypeError: ts_plot_png() got an unexpected keyword argument 'format'
    """
    result = call_plot(**ARGS, format="svg")
    body = payload_bytes(result)
    assert b"<svg" in body[:1024]
    assert mime_of(result) == "image/svg+xml"


def test_svg_is_vector_not_a_wrapped_raster() -> None:
    """An SVG holding one giant base64 <image> would satisfy the magic-number
    check while being useless for publication. Assert real vector primitives.

    Provenance: matplotlib's SVG backend emits glyph and line geometry as
    ``<path>`` elements; a rasterised figure emits a single ``<image>`` element
    with an embedded PNG. The two are mutually exclusive for this figure.
    """
    body = payload_bytes(call_plot(**ARGS, format="svg"))
    assert body.count(b"<path") > 10, "expected vector path data, got a raster wrapper"
    assert b"<image" not in body


def test_unknown_format_returns_a_structured_error_not_a_raise() -> None:
    """CLAUDE.md, MCP design notes: 'Avoid raising -- return the error model so
    agents can recover.' The tool's sibling validation paths (B <= 0, steps < 2)
    already return a TextContent explanation rather than raising.
    """
    result = call_plot(**ARGS, format="jpeg")
    text = result.content[0].text
    assert "jpeg" in text
    for supported in ("png", "pdf", "svg"):
        assert supported in text, f"error text must name {supported} as a valid choice"


@pytest.mark.parametrize("fmt", ["png", "pdf", "svg"])
def test_every_format_renders_the_same_diagram(fmt: str) -> None:
    """Format must change only the container, never whether the render works."""
    result = call_plot(**ARGS, format=fmt)
    assert len(payload_bytes(result)) > 1000, f"{fmt} payload is implausibly small"


class TestGroundTermAnnotation:
    """The emphasised curve must be the ground term where the label is drawn.

    render_diagram picked it as "lowest eigenvalue at the FIRST Dq point", then
    drew the annotation at the LAST one. Two separate problems:

    * at Dq = 0 the ligand field vanishes, so every crystal-field component of
      the free-ion ground term is exactly degenerate and `min()` over the term
      dict breaks the tie by insertion order -- d6 yields `5_E`, not the
      weak-field `5_T_2`;
    * d4-d7 cross over, so even a correct weak-field answer is the wrong term
      at strong field, which is where the label sits.

    Provenance: the expected values are literature-invariant ground terms, not
    values read off this renderer. d3 and d8 have no spin crossover and are
    invariantly 4A_2g and 3A_2g. d6 above its crossover is low-spin 1A_1g --
    the textbook Dq/B ~ 2 case, and the crossing for these Racah parameters is
    independently located by `crossover_dq`.
    """

    @staticmethod
    def _ground_of(d_count: int, dq_max: float, B: float, C: float) -> str:
        from tanabesugano.mcp.plotting import _diagram_ground_term

        return str(_diagram_ground_term(d_count, dq_max, B, C, steps=40))

    @pytest.mark.parametrize(("d_count", "expected"), [(3, "4_A_2"), (8, "3_A_2")])
    def test_configurations_without_a_crossover_name_their_invariant_ground(
        self,
        d_count: int,
        expected: str,
    ) -> None:
        assert self._ground_of(d_count, 2500.0, 900.0, 4000.0) == expected

    def test_d6_above_its_crossover_is_low_spin(self) -> None:
        """Observed failure before the fix: `5_E`.

        Wrong twice over -- 5_E is not even the weak-field ground term (5_T_2
        is; they are degenerate at Dq=0 and the tie-break chose wrongly), and
        at this field d6 is low-spin anyway.
        """
        assert self._ground_of(6, 2506.5, 1080.0, 4773.0) == "1_A_1"

    @pytest.mark.parametrize("d_count", [2, 3, 4, 5, 6, 7, 8])
    def test_it_matches_an_independent_argmin_at_the_annotated_edge(
        self,
        d_count: int,
    ) -> None:
        """The label is drawn at x_max, so the term named must be lowest there.

        Independent oracle: compute_point at exactly dq_max and take the argmin
        over raw eigenvalues, sharing no code with the renderer's selection.
        """
        from tanabesugano.mcp._compute import compute_point

        dq_max, B, C = 2200.0, 950.0, 4200.0
        point = compute_point(d_count, dq_max, B, C)
        expected = min(point, key=lambda t: min(point[t]) if point[t] else float("inf"))
        assert self._ground_of(d_count, dq_max, B, C) == str(expected)
