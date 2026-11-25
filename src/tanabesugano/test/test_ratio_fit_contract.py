"""Contract tests for ts_ratio_fit_app: one solver for the answer, the ratio grid as a picture.

The app used to return the node of its own (Dq, B) grid with the best two-ratio
score. That was a second objective in the MCP layer: it paired bands by position
(``allowed[i] / allowed[0]``) and weighted a magnitude term by an arbitrary 0.3, and
its answer could only ever be a grid node -- +3.5 % Dq on d3, where nu1/10 falls
between nodes. The answer now comes from ``fit_spectrum``; the ratio grid's best node
is kept beside it as a labelled diagnostic, with its cell size.

Provenance: oracle truths are inputs to ``_determinant_oracle`` (through the recovery
module's helpers); the equality cases compare against a direct ``fit_spectrum`` call.
"""

from __future__ import annotations

import json

import pytest

from tanabesugano.mcp._compute import fit_spectrum
from tanabesugano.mcp.server import create_server
from tanabesugano.test._loop import run_loop_free
from tanabesugano.test.test_fit_recovery import oracle_bands


NI_BANDS = [8500.0, 13800.0, 25300.0]  # [Ni(H2O)6]2+
CROWDED_D3 = [17000.0, 17800.0, 37552.0]


def call_ratio_fit(**kwargs) -> dict:
    """Call the tool function and return its Chart.js payload."""

    async def go():
        server = create_server()
        tool = await server.get_tool("ts_ratio_fit_app")
        return tool.fn(**kwargs)

    result = run_loop_free(go)
    return json.loads(result.content[0].text)


def bands_kwargs(energies: list[float]) -> dict:
    """Map up to three band energies onto the tool's v1 / v2 / v3."""
    return dict(zip(("v1", "v2", "v3"), energies, strict=False))


def test_ratio_app_d3_has_no_lattice_offset() -> None:
    """Oracle d3 Cr(III)-like bands: Dq within 0.5 %, not the grid node beside nu1/10.

    Observed red (3bff962): ``KeyError: 'Dq'`` -- the payload carried
    only the title, ``Dq=1241.4`` (+3.5 %).
    """
    energies = [e for e, _u in oracle_bands(3, 1200.0, 413.1, 1652.4, spin_allowed_only=True)[:3]]
    payload = call_ratio_fit(d_count=3, **bands_kwargs(energies))
    assert payload["Dq"] == pytest.approx(1200.0, rel=0.005)


@pytest.mark.parametrize(("d_count", "energies"), [(8, NI_BANDS), (3, CROWDED_D3)])
def test_ratio_app_matches_fit_spectrum(d_count: int, energies: list[float]) -> None:
    """App defaults and fit_spectrum defaults give the same Dq and B: one solver.

    Observed red (c09f535): ``KeyError: 'Dq'`` (the answer was a grid node, in the title only).
    """
    direct = fit_spectrum(d_count, energies)
    payload = call_ratio_fit(d_count=d_count, **bands_kwargs(energies))
    assert payload["Dq"] == pytest.approx(direct.Dq, rel=1e-6)
    assert payload["B"] == pytest.approx(direct.B, rel=1e-6)


def test_ratio_app_fits_low_spin_when_told() -> None:
    """d6 low-spin bands with spin_state='low' (C held at the truth, as in the reverse app).

    Observed red (c09f535): ``TypeError: ... unexpected keyword argument 'C'``.
    """
    energies = [e for e, _u in oracle_bands(6, 2500.0, 700.0, 3080.0, spin_allowed_only=True)[:2]]
    payload = call_ratio_fit(d_count=6, C=3080.0, spin_state="low", **bands_kwargs(energies))
    assert payload["Dq"] == pytest.approx(2500.0, rel=0.02)
    assert payload["spin_state"] == "low"


def test_ratio_app_reports_its_grid_as_diagnostic() -> None:
    """The ratio grid's best node survives as a diagnostic with a positive cell size.

    Observed red (c09f535): ``KeyError: 'ratio_grid_best'``.
    """
    payload = call_ratio_fit(d_count=8, **bands_kwargs(NI_BANDS))
    node = payload["ratio_grid_best"]
    assert node["cell"]["Dq"] > 0
    assert node["cell"]["B"] > 0
    assert payload["C_source"] == "default"
    assert isinstance(payload["warnings"], list)


def test_ratio_app_short_label_list_is_an_error_payload() -> None:
    """Fewer labels than bands comes back as an error payload, not an exception.

    Observed red (62797f6, final review): ``IndexError: list index out of range``.
    """
    payload = call_ratio_fit(d_count=8, band_labels=["3_T_2"], **bands_kwargs(NI_BANDS))
    assert "one label per band" in payload["error"]


def test_ratio_grid_marker_sits_at_the_node() -> None:
    """The dashed diagnostic marker is drawn at the node's own 10Dq/B.

    Observed red (62797f6, final review): labelled 9.286 (node Dq over the fit's B),
    the node (879.3, 962.1) sits at 9.139.
    """
    payload = call_ratio_fit(d_count=8, **bands_kwargs(NI_BANDS))
    node = payload["ratio_grid_best"]
    marker = next(s for s in payload["series"] if "diagnostic" in s["label"])
    assert marker["data"][0]["x"] == pytest.approx(10.0 * node["Dq"] / node["B"], abs=2e-3)


def test_ratio_grid_is_withheld_for_spin_forbidden_fits() -> None:
    """The ratio grid scores spin-allowed lines only: withheld when the fit uses forbidden ones.

    d3 with the spin-forbidden ²E line as v1: the ratio grid would read ²E as nu1.
    High-spin d5 cannot show this -- it has no spin-allowed line, so its grid is empty.
    Observed red (62797f6, final review): a ``ratio_grid_best`` node was returned.
    """
    bands = [
        (e, u)
        for e, u in oracle_bands(3, 1700.0, 700.0, 2800.0, spin_allowed_only=False)
        if u in {"2_E#0", "4_T_2#0", "4_T_1#0"}
    ]
    payload = call_ratio_fit(
        d_count=3,
        C=2800.0,
        include_spin_forbidden=True,
        band_labels=[u.split("#")[0] for _e, u in bands],
        **bands_kwargs([e for e, _u in bands]),
    )
    assert "error" not in payload, payload.get("error")
    assert payload["ratio_grid_best"] is None


def test_ratio_app_names_energy_unit_for_ev_peaks() -> None:
    """Peaks v1-v3 in eV at the default energy_unit name energy_unit (plan E R4).

    Observed red (0aef909): the error was ``fit never escaped the penalty region``.
    """
    payload = call_ratio_fit(d_count=8, v1=1.05, v2=1.71, v3=3.14)
    assert "energy_unit" in payload["error"]
    assert "eV" in payload["error"]


def test_ratio_app_refuses_kk_peaks_declared_as_ev() -> None:
    """Values v1-v3 in kK sent with energy_unit='eV' are refused, not fitted (final review I1).

    Observed red (562491b): no ``error`` key -- the payload carried a fitted Dq.
    """
    payload = call_ratio_fit(d_count=8, v1=8.5, v2=13.8, v3=25.3, energy_unit="eV")
    assert "kK" in payload.get("error", "")
