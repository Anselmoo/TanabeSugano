"""Contract tests for the generated matplotlib source.

Why this exists at all: there was no observed-vs-computed renderer, so every
such figure was bespoke matplotlib written by hand or by an LLM -- untested,
non-reproducible, and re-deriving assignment logic that the fitter already
returns structurally. That is the "second implementation with no oracle"
pattern. A generator that emits source removes the second implementation: the
script carries the fit's own numbers as literals rather than recomputing them.

The load-bearing test here is TestTheScriptActuallyRuns. Inspecting generated
source proves nothing about whether it executes -- this project has already
been bitten once by output that looked right and rendered empty
(ToolResult(content=app) serialising a PrefabApp via model_dump()).
"""

from __future__ import annotations

import re

import pytest

from tanabesugano.mcp._compute import fit_spectrum
from tanabesugano.script_export import fit_figure_script


BANDS = [8500.0, 13800.0, 25300.0]  # [Ni(H2O)6]2+


@pytest.fixture(scope="module")
def script() -> str:
    return fit_figure_script(8, BANDS)


@pytest.fixture(scope="module")
def fit():
    return fit_spectrum(8, BANDS)


class TestTheScriptActuallyRuns:
    """Execute it. Everything else is secondary to this."""

    def test_source_compiles(self, script: str) -> None:
        compile(script, "<generated>", "exec")

    def test_executing_it_produces_a_non_empty_figure(self, script: str, tmp_path) -> None:
        """Runs the generated source in a fresh namespace and checks the file
        it writes is a real PNG of plausible size.

        Provenance: the PNG signature is RFC 2083 section 3.1. The size floor
        rules out the failure this project has actually seen -- a technically
        valid but empty render.
        """
        import matplotlib

        matplotlib.use("Agg")
        out = tmp_path / "figure.png"
        source = script.replace('OUTPUT = "tanabesugano_fit.png"', f"OUTPUT = {str(out)!r}")
        assert source != script, "the generated script must expose an OUTPUT constant"

        exec(compile(source, "<generated>", "exec"), {"__name__": "__main__"})

        assert out.exists(), "running the generated script produced no file"
        blob = out.read_bytes()
        assert blob.startswith(b"\x89PNG\r\n\x1a\n")
        assert len(blob) > 10_000, f"figure is implausibly small ({len(blob)} bytes)"


class TestItInheritsTheFitRatherThanRederivingIt:
    """Every number in the source must be the fitter's, verbatim."""

    def test_fitted_parameters_appear_as_literals(self, script: str, fit) -> None:
        assert f"{fit.Dq:.4f}" in script or f"{fit.Dq!r}" in script
        assert f"{fit.B:.4f}" in script or f"{fit.B!r}" in script

    def test_observed_peaks_are_carried_through_unchanged(self, script: str) -> None:
        for peak in BANDS:
            assert f"{peak:.4f}" in script or str(peak) in script

    def test_computed_energies_match_the_fit_to_full_precision(self, script: str, fit) -> None:
        """A re-derivation inside the generator would drift in the last digits."""
        allowed = [energy for energy, _, is_allowed in fit.transitions if is_allowed]
        for energy in allowed[: len(BANDS)]:
            assert f"{energy:.4f}" in script, f"computed energy {energy} is not in the source"


class TestGeneratedLabelsMatchTheLiterature:
    """Labels come from Level.parent_latex, not hand-authored strings."""

    def test_d8_bands_are_labelled_by_free_ion_parentage(self, script: str) -> None:
        """3T_1g(F) and 3T_1g(P) -- what a caption and a textbook both print.

        Provenance: at zero field 3P sits exactly 15B above 3F, and P reduces to
        T_1 alone while F reduces to A_2 + T_1 + T_2. Both facts are asserted
        independently in test_matrices_invariants.py and test_free_ion.py.
        """
        assert r"^{3}T_{1g}(F)" in script
        assert r"^{3}T_{1g}(P)" in script
        assert r"^{3}A_{2g}" in script

    def test_no_positional_ordinals_leak_into_labels(self, script: str) -> None:
        """(a)/(b) is this package's internal spelling and must not reach a figure."""
        assert not re.search(r"T_\{1g\}\((a|b)\)", script)


class TestItIsSelfContained:
    """A reviewer must be able to run it with matplotlib alone."""

    def test_it_does_not_import_tanabesugano(self, script: str) -> None:
        """The whole point of baking literals: reproducibility must not depend on
        having this package, or this version of it, installed.
        """
        assert "import tanabesugano" not in script
        assert "from tanabesugano" not in script

    def test_it_records_where_the_numbers_came_from(self, script: str) -> None:
        """Provenance in the artefact itself, so a diff of two scripts shows what
        changed in the inputs rather than only in the picture.
        """
        from tanabesugano import __version__

        assert __version__ in script
        assert "Dq" in script
        assert "high" in script  # the spin regime the fit was pinned to


class TestErrorsAreStructuredNotSilent:
    def test_an_unfittable_configuration_raises_with_an_explanation(self) -> None:
        """High-spin d5 has zero spin-allowed d-d transitions, so there is no
        observed-vs-computed figure to draw. The generator must surface the
        fitter's own explanation rather than emit a script that plots nothing.
        """
        with pytest.raises(ValueError, match="spin-allowed|spin-forbidden"):
            fit_figure_script(5, [12000.0, 18000.0, 25000.0])


class TestTheMcpTool:
    """ts_fit_script must return the source as text, not as a blob.

    Text is the point: the sandbox strips allow-downloads from every UI iframe,
    so a script that arrives as an attachment the client cannot save is no use.
    Arriving as conversation text, it can be read, edited and pasted.
    """

    @staticmethod
    def _call(**kwargs):
        import asyncio

        from tanabesugano.mcp.server import create_server

        async def go():
            server = create_server()
            tool = await server.get_tool("ts_fit_script")
            return tool.fn(**kwargs)

        return asyncio.run(go())

    def test_it_returns_runnable_source_as_text(self) -> None:
        result = self._call(d_count=8, observed_peaks=BANDS)
        block = result.content[0]
        assert block.type == "text", f"expected text, got {block.type}"
        compile(block.text, "<generated>", "exec")

    def test_an_illposed_fit_returns_a_structured_error_not_a_raise(self) -> None:
        """CLAUDE.md, MCP design notes: return the error model so agents recover.

        High-spin d5 has no spin-allowed d-d bands at all, so this is the
        configuration that exercises the path.
        """
        result = self._call(d_count=5, observed_peaks=[12000.0, 18000.0, 25000.0])
        assert result.is_error
        assert "spin" in result.content[0].text.lower()
