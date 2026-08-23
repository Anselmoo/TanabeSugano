"""Contract tests for ts_fit_plot_app.

Same shape of promise as ts_reverse_fit_app, and pinned for the same reason:
the tool must satisfy BOTH halves of its docstring -- a chart a human can read,
and numbers an agent can use. Without assertions on the render half, a
return-type change is unverifiable, which is exactly how
``ToolResult(content=app)`` once serialised a PrefabApp through ``model_dump()``
and emitted an empty card that looked fine from the outside.

The residual axis is the point of this chart. On a wavenumber axis spanning
8,500-25,300 cm^-1 a 165 cm^-1 misfit is narrower than a plot marker, so a
chart of raw band positions would show two coincident dots and tell the reader
nothing. Plotting computed - observed puts the disagreement on its own scale.
"""

from __future__ import annotations

import json

import pytest

from tanabesugano.mcp.server import create_server
from tanabesugano.test._loop import run_loop_free


BANDS = [8500.0, 13800.0, 25300.0]  # [Ni(H2O)6]2+


def call_fit_plot(**kwargs):
    async def go():
        server = create_server()
        tool = await server.get_tool("ts_fit_plot_app")
        return tool.fn(**kwargs)

    return run_loop_free(go)


@pytest.fixture(scope="module")
def payload() -> dict:
    result = call_fit_plot(d_count=8, observed_peaks=BANDS)
    assert not result.is_error, result.content[0].text
    return json.loads(result.content[0].text)


class TestTheChartRenders:
    """Pin the visible half so a return-type change cannot break it silently."""

    def test_payload_carries_axis_labels_and_series(self, payload: dict) -> None:
        assert payload["x_label"]
        assert payload["y_label"]
        assert payload["series"], "no series to draw"

    def test_every_series_has_plottable_points(self, payload: dict) -> None:
        """A series present but empty is the empty-card failure mode."""
        for series in payload["series"]:
            assert series["data"], f"series {series['label']!r} has no points"
            for point in series["data"]:
                assert isinstance(point["x"], (int, float))
                assert isinstance(point["y"], (int, float))

    def test_a_zero_reference_line_spans_the_data(self, payload: dict) -> None:
        """Residuals are meaningless without the line they are measured from."""
        zero = next(s for s in payload["series"] if "zero" in s["label"].lower())
        assert all(point["y"] == 0 for point in zero["data"])
        residuals = next(s for s in payload["series"] if "residual" in s["label"].lower())
        xs = [p["x"] for p in residuals["data"]]
        zero_xs = [p["x"] for p in zero["data"]]
        assert min(zero_xs) <= min(xs) and max(zero_xs) >= max(xs)


class TestTheNumbersAreAlsoReturned:
    """Pin the machine-readable half: an agent must get data, not only a widget."""

    @pytest.mark.parametrize(
        "field",
        ["Dq_cm1", "B_cm1", "C_cm1", "rmse_cm1", "ground_term", "spin_state", "bands"],
    )
    def test_headline_fields_are_present(self, payload: dict, field: str) -> None:
        assert field in payload

    def test_each_band_carries_its_full_record(self, payload: dict) -> None:
        for band in payload["bands"]:
            assert {"observed_cm1", "computed_cm1", "residual_cm1", "assignment"} <= set(band)

    def test_residuals_are_computed_minus_observed(self, payload: dict) -> None:
        """Sign convention stated once and asserted, so a reader of the chart
        knows which way a positive bar points.
        """
        for band in payload["bands"]:
            assert band["residual_cm1"] == pytest.approx(
                band["computed_cm1"] - band["observed_cm1"],
                abs=1e-6,
            )

    def test_the_numbers_match_the_fitter_exactly(self, payload: dict) -> None:
        """No re-derivation: the app must report the fit, not recompute it."""
        from tanabesugano.mcp._compute import fit_spectrum

        fit = fit_spectrum(8, BANDS)
        assert payload["Dq_cm1"] == pytest.approx(fit.Dq, abs=1e-9)
        assert payload["B_cm1"] == pytest.approx(fit.B, abs=1e-9)
        assert payload["rmse_cm1"] == pytest.approx(fit.rmse_cm1, abs=1e-9)
        assert payload["ground_term"] == fit.ground_term


class TestAssignmentsUseLiteratureNotation:
    def test_d8_bands_are_labelled_by_free_ion_parentage(self, payload: dict) -> None:
        """3T_1g(F)/(P), so a chart and a caption agree. See test_free_ion.py."""
        assignments = " ".join(band["assignment"] for band in payload["bands"])
        assert "(F)" in assignments
        assert "(P)" in assignments
        assert "(a)" not in assignments
        assert "(b)" not in assignments


class TestErrorsAreStructured:
    def test_unfittable_configuration_returns_an_error_payload(self) -> None:
        """High-spin d5 has no spin-allowed d-d bands; say so, do not raise."""
        result = call_fit_plot(d_count=5, observed_peaks=[12000.0, 18000.0, 25000.0])
        assert result.is_error
        assert "spin" in result.content[0].text.lower()


class TestChartLabelsAreRenderable:
    """Chart.js renders no mathtext, so the chart must not be handed LaTeX."""

    def test_band_records_carry_a_unicode_spelling(self, payload: dict) -> None:
        for band in payload["bands"]:
            assert "assignment_unicode" in band

    def test_the_unicode_spelling_is_not_latex(self, payload: dict) -> None:
        """Observed failure before the fix: point labels read
        ``$^{3}A_{2g} \\rightarrow {}^{3}T_{2g}$`` verbatim in the chart.
        """
        for band in payload["bands"]:
            label = band["assignment_unicode"]
            assert "$" not in label
            assert "\\" not in label
            assert "→" in label, "expected a real arrow character"

    def test_plotted_points_carry_the_unicode_label(self, payload: dict) -> None:
        residuals = next(s for s in payload["series"] if "residual" in s["label"].lower())
        for point in residuals["data"]:
            assert "$" not in point.get("label", "")
            assert "→" in point.get("label", "")

    def test_unicode_labels_use_free_ion_parentage(self, payload: dict) -> None:
        joined = " ".join(band["assignment_unicode"] for band in payload["bands"])
        assert "(F)" in joined
        assert "(P)" in joined
