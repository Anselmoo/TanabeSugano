"""Contract tests for the five fit-returning tools (plan G, Task 5).

``ts_fit_spectrum`` is the numeric fit; ``ts_reverse_fit_app``, ``ts_ratio_fit_app``,
``ts_fit_plot_app`` and ``ts_fit_script`` display that same fit. Each must carry the
fit's provenance (``Dq_source`` / ``B_source`` / ``C_source``) and its ``assumptions``,
so no surface can show an undetermined Dq as a bare number.

The undetermined case is observed [Mn(H2O)6]2+, unlabelled, at the default C. Its range
must contain 805.981, the exact C-free point the determinant oracle gives for these bands
(``test_fit_recovery.MN_REF_C_FREE``), a value no fit code produced.
"""

from __future__ import annotations

import json
import re

from pathlib import Path

import pytest

from fastmcp.tools import ToolResult
from mcp.types import TextContent

from tanabesugano.mcp.models import FitResult
from tanabesugano.mcp.server import create_server
from tanabesugano.test._determinant_oracle import relative_term_levels
from tanabesugano.test._loop import run_loop_free
from tanabesugano.test.test_fit_recovery import MN_OBSERVED_BANDS
from tanabesugano.test.test_fit_recovery import MN_REF_C_FREE


FIT_TOOLS = ("ts_fit_spectrum", "ts_reverse_fit_app", "ts_ratio_fit_app", "ts_fit_plot_app")
"""The fit tools whose result is structured data; ts_fit_script returns source text."""
SPIN_STATE_TOOLS = ("ts_reverse_fit_app", "ts_ratio_fit_app", "ts_fit_plot_app", "ts_fit_script")
"""The four tools whose spin_state offered 'auto', which always fails without a Dq."""
PROVENANCE_KEYS = ("Dq_source", "B_source", "C_source", "assumptions")


def _tool(name: str):
    async def go():
        return await create_server().get_tool(name)

    return run_loop_free(go)


def _mn_args(name: str) -> dict:
    """Unlabelled observed Mn, default C, spin-forbidden bands: Dq and B undetermined."""
    if name == "ts_ratio_fit_app":
        v1, v2, v3 = MN_OBSERVED_BANDS
        return {"d_count": 5, "v1": v1, "v2": v2, "v3": v3, "include_spin_forbidden": True}
    key = "observed_peaks_cm1" if name == "ts_fit_spectrum" else "observed_peaks"
    return {"d_count": 5, key: list(MN_OBSERVED_BANDS), "include_spin_forbidden": True}


def _text(result: ToolResult) -> str:
    block = result.content[0]
    assert isinstance(block, TextContent)
    return block.text


def _payload(result: object) -> dict:
    """The machine-readable half of a fit tool's result."""
    if isinstance(result, FitResult):
        return result.model_dump()
    assert isinstance(result, ToolResult)
    if result.structured_content is not None:
        return result.structured_content
    return json.loads(_text(result))


def _shown(name: str, result: object) -> str:
    """The human-visible text: the script, the reverse-fit card, or the chart title."""
    assert isinstance(result, ToolResult)
    if name == "ts_fit_script":
        return _text(result)
    if name == "ts_reverse_fit_app":
        return json.dumps(json.loads(_text(result)), ensure_ascii=False)
    return _payload(result)["title"]


@pytest.mark.parametrize("name", FIT_TOOLS)
def test_every_fit_tool_exposes_provenance(name: str) -> None:
    """Each fit tool carries Dq_source, B_source, C_source and assumptions.

    Observed red: ``AssertionError: Dq_source`` on ts_reverse_fit_app (it carried
    C_source only), ts_ratio_fit_app and ts_fit_plot_app.
    """
    data = _payload(_tool(name).fn(**_mn_args(name)))
    for key in PROVENANCE_KEYS:
        assert key in data, key
    assert data["Dq_source"] == "undetermined"


def test_fit_script_header_carries_provenance() -> None:
    """The script's header names each source and the assumptions.

    Observed red: ``AssertionError: assert None`` -- no ``Dq_source`` line; the header
    listed Dq, B and C as bare numbers.
    """
    source = _text(_tool("ts_fit_script").fn(**_mn_args("ts_fit_script")))
    header = source.split('"""', 2)[1]
    assert re.search(r"Dq_source\s+undetermined", header)
    for key in ("B_source", "C_source", "assumptions"):
        assert key in header


@pytest.mark.parametrize("name", [*FIT_TOOLS[1:], "ts_fit_script"])
def test_fit_apps_show_a_range_when_undetermined(name: str) -> None:
    """An undetermined fit is shown as a range over minima, never as one Dq.

    Observed red: ``assert 'Best Dq' not in`` the reverse-fit card; titles
    ``Custom TS d5: Dq=715.5, B=400.4 cm⁻¹`` and ``d5 fit — Dq = 715, B = 400 cm⁻¹,
    RMSE = 95 cm⁻¹ (6_A_1 ground)``; ``Dq = 715.5`` in the script heading.
    """
    shown = _shown(name, _tool(name).fn(**_mn_args(name)))
    # Warnings name the alternative minima ("a fitted C = 3078 gives Dq = 806"): that
    # is the pointer the rule wants, not a result, so they are not inspected here.
    shown = re.sub(r"#   ! .*", "", re.sub(r"⚠[^\"]*", "", shown))
    assert "Best Dq" not in shown
    assert not re.search(r"Dq ?= ?[\d,]+", shown), shown[:300]
    match = re.search(r"Dq ([\d,.]+)\s*[–-]\s*([\d,.]+)", shown)
    assert match, shown[:300]
    lo, hi = (float(x.replace(",", "")) for x in match.groups())
    assert lo <= MN_REF_C_FREE[0] <= hi


def test_reverse_minima_carry_lowest_rmse_and_source() -> None:
    """The reverse app's minima carry source, lowest_rmse and ambiguous, as FitMinimum does.

    Observed red: ``KeyError: 'source'``.
    """
    data = _payload(_tool("ts_reverse_fit_app").fn(**_mn_args("x")))
    assert {m["source"] for m in data["minima"]} == {"held", "free_c"}
    assert sum(m["lowest_rmse"] for m in data["minima"]) == 1
    assert all("ambiguous" in m for m in data["minima"])


def test_spectrum_app_draws_no_delta_s_two_lines() -> None:
    """High-spin d5: the simulated spectrum ends where the quartets end, not the doublets.

    The upper edge of the energy axis is the highest stick + 3 x broadening. The quartet
    and doublet energies come from the determinant oracle, independent of the app.
    Observed red: ``assert 97192.3072 == 50980.74508380748 ± 1`` -- the axis ran to
    the top doublet.
    """
    dq, broadening = 800.0, 500.0
    levels = relative_term_levels(5, dq, 860.0, 3850.0)
    top_quartet = max(e for key, es in levels.items() if key.startswith("4_") for e in es)
    top_doublet = max(e for key, es in levels.items() if key.startswith("2_") for e in es)
    assert top_doublet > top_quartet + 1.0
    result = _tool("ts_spectrum_app").fn(d_count=5, Dq=dq, B=860.0, C=3850.0, n_points=50)
    x_max = max(p["x"] for p in json.loads(_text(result))["series"][0]["data"])
    assert x_max == pytest.approx(top_quartet + 3 * broadening, abs=1.0)


def test_peak_assignments_follow_the_spin_rule() -> None:
    """ts_fit_spectrum lists no Delta S = 2 transition in peak_assignments.

    Observed red: ``assert ['2_T_2(a)', ..._A_1(a)', ...] == []`` -- doublet targets
    listed at intensity 0.05.
    """
    data = _payload(
        _tool("ts_fit_spectrum").fn(
            **_mn_args("ts_fit_spectrum"),
            C=3243.0,
            band_labels=["4_T_1", "4_T_2", ["4_E", "4_A_1"]],
        ),
    )
    targets = [p["assignment"].split("→", 1)[1] for p in data["peak_assignments"]]
    assert targets
    assert [t for t in targets if t.startswith("2_")] == []


@pytest.mark.parametrize("name", SPIN_STATE_TOOLS)
def test_spin_state_auto_is_not_offered(name: str) -> None:
    """spin_state is 'high' or 'low': 'auto' needs a Dq these tools do not take.

    Observed red: ``'enum': ['high', 'low', 'auto']`` on all four.
    """
    schema = _tool(name).parameters["properties"]["spin_state"]
    assert schema.get("enum") == ["high", "low"], schema


def test_nephelauxetic_names_the_default_ion() -> None:
    """Without ion, the result says which free ion beta is relative to.

    Observed red: ``assert 'not given' in 'beta = 0.855: the d-electron cloud of Ni2+
    ...'`` -- nothing said Ni2+ was a default.
    """
    result = _tool("ts_nephelauxetic").fn(d_count=8, fitted_B=890.0)
    assert result.ion in result.interpretation
    assert "not given" in result.interpretation


# -- Agent-facing text (plan G, Task 5). Each string an agent reads must say what the
# -- code does; a physical claim in it is checked against the determinant oracle.

ALL_FIT_TOOLS = (*FIT_TOOLS, "ts_fit_script")
ROUTING = "ts_fit_spectrum is the numeric fit"
DELTA_S = "ΔS = 0, ±1"
OH_ONLY = "Oh only; a geometry='Td' fit cannot be reproduced here"
REPO = Path(__file__).resolve().parents[3]


def _param(name: str, param: str) -> str:
    return _tool(name).parameters["properties"][param].get("description", "")


@pytest.mark.parametrize("name", ALL_FIT_TOOLS)
def test_fit_tool_routes_to_the_numeric_fit(name: str) -> None:
    """Every fit tool says ts_fit_spectrum is the fit to call first.

    Observed red: ``assert 'ts_fit_spectrum is the numeric fit' in ...`` on all five.
    """
    assert ROUTING in (_tool(name).description or "")


@pytest.mark.parametrize("name", ALL_FIT_TOOLS)
@pytest.mark.parametrize("param", ["include_spin_forbidden", "band_labels"])
def test_fit_tool_states_the_spin_rule(name: str, param: str) -> None:
    """include_spin_forbidden and band_labels say only ΔS = 0, ±1 levels are fitted.

    Observed red: ``assert 'ΔS = 0, ±1' in ...`` on every pair.
    """
    assert DELTA_S in _param(name, param)


@pytest.mark.parametrize("name", ["ts_fit_plot_app", "ts_reverse_fit_app"])
def test_fit_c_is_described_as_fit_c(name: str) -> None:
    """fit_c no longer repeats band_labels' text (a copy-paste).

    Observed red: ``'each band is drawn against the level the fit assigned it'`` /
    ``'one label per peak'`` in fit_c.
    """
    text = _param(name, "fit_c")
    assert "Racah C" in text
    assert "one label per peak" not in text
    assert "drawn" not in text


def test_ratio_fit_app_title() -> None:
    """Observed red: title ``'Custom TS diagram from band positions'``."""
    assert _tool("ts_ratio_fit_app").title == (
        "TS diagram at the fitted (Dq, B), with ratio-method diagnostic"
    )


@pytest.mark.parametrize("name", ["ts_fit_plot_app", "ts_fit_script"])
def test_fit_displays_say_oh_only(name: str) -> None:
    """Observed red: ``assert "Oh only; ..." in ...`` -- they take no geometry."""
    assert OH_ONLY in (_tool(name).description or "")
    assert "geometry" not in _tool(name).parameters["properties"]


def test_fit_spectrum_returns_names_what_to_read() -> None:
    """The description an agent receives names the fields to read before reporting.

    FastMCP drops a docstring's ``Args:`` / ``Returns:`` / ``Example:`` sections from
    the tool description (the Args become parameter descriptions; the rest is lost),
    so this guidance must sit in the prose body. Observed red: ``IndexError`` on
    ``split("Returns:")`` -- the description an agent got ends after its first
    paragraph, with no Returns text at all.
    """
    text = _tool("ts_fit_spectrum").description or ""
    for word in ("Dq_source", "minima", "band_assignments", "assumptions", "warnings"):
        assert word in text, word


def test_fit_spectrum_example_is_labelled_and_runs() -> None:
    """The docstring example passes band_labels whose uids exist, and fits.

    The call is parsed out of the description an agent receives and run, so a renamed
    uid fails here. Observed red: ``IndexError`` -- the example, unlabelled, sat in an
    ``Example:`` section that FastMCP drops from the description; then
    ``assert 'C stays the d8 default' in ...`` -- the sentence called all three
    sources fitted or given while the run returned C_source 'default'.
    """
    import ast

    text = _tool("ts_fit_spectrum").description or ""
    call = re.findall(r"ts_fit_spectrum\((d_count=[^\n]*band_labels=[^\n]*)\)", text)[0]
    kwargs = {
        kw.arg: ast.literal_eval(kw.value)
        for kw in ast.parse(f"f({call})", mode="eval").body.keywords  # ty: ignore[unresolved-attribute]
    }
    result = _tool("ts_fit_spectrum").fn(**kwargs)
    assert isinstance(result, FitResult), result
    assert result.Dq_source == "fitted"
    assert result.B_source == "fitted"
    # d8's spin-allowed bands do not fix C, so it stays the default; the sentence
    # introducing the example must say so rather than call all three determined.
    assert result.C_source == "default"
    assert "C stays the d8 default" in " ".join(text.split())


def test_fit_result_descriptions() -> None:
    """models.py says which fields are results only together with their source.

    Observed red: ``assert 'Dq_source' in 'Optimized ligand field parameter (cm^-1).'``.
    """
    fields = FitResult.model_fields
    assert "Dq_source" in (fields["fitted_Dq"].description or "")
    assert "B_source" in (fields["fitted_B"].description or "")
    for name in ("Dq_source", "B_source"):
        assert "default C" in (fields[name].description or ""), name
    for name in ("minima",):
        assert "undetermined" in (fields[name].description or ""), name
    from tanabesugano.mcp.models import FitMinimum

    assert "undetermined" in (FitMinimum.model_fields["lowest_rmse"].description or "")
    assert "band_assignments" in (fields["peak_assignments"].description or "")
    assert DELTA_S in (fields["predicted_peaks_cm1"].description or "")


def test_correlation_app_default_is_not_called_strong_field() -> None:
    """d4-d7 at Dq = 2000 and default B/C are still high-spin, by the oracle.

    The strong_field_Dq text must not call 2000 the strong-field limit. Observed red:
    ``'well into the strong-field limit for any first-row transition metal'``.
    """
    from tanabesugano.mcp.tools._shared import resolve_bc

    for d in (4, 5, 6, 7):
        levels = relative_term_levels(d, 2000.0, *resolve_bc(d, None, None))
        ground = min(levels, key=lambda key: min(levels[key]))
        assert int(ground[0]) == max(int(key[0]) for key in levels), (d, ground)
    text = _param("ts_correlation_diagram_app", "strong_field_Dq")
    assert "well into the strong-field" not in text
    assert "high-spin" in text


@pytest.mark.parametrize("name", ["ts_compare_app", "ts_overlay_app"])
def test_hole_pairs_are_related_by_negative_dq(name: str) -> None:
    """Observed red: the text called d2/d8 etc. "directly comparable" at equal Dq."""
    assert "Dq → −Dq" in (_tool(name).description or "")


def test_spectrum_app_text_states_the_spin_rule() -> None:
    """Observed red: the text said every spin-forbidden line is drawn at 5%."""
    assert DELTA_S in (_tool("ts_spectrum_app").description or "")


def test_server_instructions_read_a_fit() -> None:
    """A rule for reading a fit, and ts_reverse_fit_app in the Prefab group.

    Observed red: ``assert 'Reading a fit' in ...``.
    """

    async def go():
        return create_server().instructions or ""

    text = run_loop_free(go)
    assert "Reading a fit" in text
    assert "Dq_source" in text
    prefab = text.split("render as in-chat Chart.js", 1)[1]
    assert "ts_reverse_fit_app" in prefab.split("Prefab", 1)[0]
    assert "ts_reverse_fit_app" not in text.split("render as in-chat Chart.js", 1)[0]


def test_explain_prompt_fits_with_labels_and_reads_provenance() -> None:
    """Observed red: the prompt asked for observed_peaks_cm1 only."""

    async def go():
        return await create_server().get_prompt("tanabesugano_explain_complex")

    text = run_loop_free(go).fn(d_count=8, absorption_peaks_cm1="8500, 13800, 25300")
    for word in ("band_labels", "Dq_source", "assumptions"):
        assert word in text, word


def _repo_text(relative: str) -> str:
    path = REPO / relative
    if not path.exists():
        pytest.skip(f"{relative} is not shipped with the package")
    return " ".join(path.read_text(encoding="utf-8").split())  # markdown wraps lines


@pytest.mark.parametrize(
    "relative",
    [".claude/skills/tanabesugano-compute/SKILL.md", ".claude/agents/ts-diagram-curator.agent.md"],
)
def test_skill_and_agent_text(relative: str) -> None:
    """Td exists, defaults are assumptions, and the eyeballing fallback is labelled.

    Observed red: ``assert "geometry='Td'" in ...``; both said octahedral-only.
    """
    text = _repo_text(relative)
    assert "geometry='Td'" in text
    assert "octahedral-only" not in text
    assert "(tetrahedral, square-planar) — not modeled" not in text
    assert "assumption" in text
    assert "eyeballed estimate, not a fit" in text


def test_why_text_does_not_overclaim() -> None:
    """Observed red: ``'nails both paired and unpaired'``, ``'without numerical optimisation'``."""
    from tanabesugano.mcp._defaults import WHY_TANABE_SUGANO

    assert "nails" not in WHY_TANABE_SUGANO
    assert "without numerical optimisation" not in WHY_TANABE_SUGANO


def test_d5_note_states_the_dq_independent_quartets() -> None:
    """4A1 and 4E(G) sit at 10B + 5C at every Dq (oracle at two Dq), and the note says so.

    Observed red: ``assert '10B+5C' in 'd5 (e.g. Mn2+, Fe3+): high-spin 6A1g; ...'``.
    """
    from tanabesugano.mcp._defaults import GROUND_STATE_NOTES

    b, c = 860.0, 3850.0
    for dq in (800.0, 1500.0):
        levels = relative_term_levels(5, dq, b, c)
        assert min(levels["4_A_1"]) == pytest.approx(10 * b + 5 * c, abs=1e-6)
        assert min(levels["4_E"]) == pytest.approx(10 * b + 5 * c, abs=1e-6)
    assert "10B+5C" in GROUND_STATE_NOTES[5]
    assert "Dq-independent" in GROUND_STATE_NOTES[5]


def test_spectrum_app_spin_rule_is_relative_to_the_ground_at_this_dq() -> None:
    """Low-spin d6 (1A1 ground at Dq = 3000): the singlets' ΔS = 0, ±1 lines are drawn.

    With the ground taken at the default B/C instead (5T2, high-spin), the rule drops
    the singlets and keeps the septets' neighbours. Levels from the determinant oracle.
    Observed red (ground from reference_ground_term at the default B/C):
    ``assert 115531.562 == 169693.06753065932 ± 1``.
    """
    from tanabesugano.mcp.tools._shared import resolve_bc

    dq, broadening = 3000.0, 500.0
    b, c = resolve_bc(6, None, None)
    levels = relative_term_levels(6, dq, b, c)
    ground = min(levels, key=lambda key: min(levels[key]))
    assert ground == "1_A_1"
    top = max(e for key, es in levels.items() if abs(int(key[0]) - 1) <= 2 for e in es)
    result = _tool("ts_spectrum_app").fn(d_count=6, Dq=dq, n_points=50)
    x_max = max(p["x"] for p in json.loads(_text(result))["series"][0]["data"])
    assert x_max == pytest.approx(top + 3 * broadening, abs=1.0)


@pytest.mark.parametrize("name", ["ts_reverse_fit_app", "ts_ratio_fit_app"])
def test_undetermined_point_is_not_called_fitted_or_best(name: str) -> None:
    """Headings and markers do not call an undetermined point the fitted / best one.

    Observed red: ``'best fit'`` in the reverse card's headings ("Residuals at best fit",
    "Term energies at best-fit Dq"); ``'Fitted 10Dq/B = 16.6'`` as the ratio marker.
    """
    result = _tool(name).fn(**_mn_args(name))
    if name == "ts_reverse_fit_app":
        shown = re.sub(r"⚠[^\"]*", "", _shown(name, result)).lower()
        assert "best fit" not in shown
        assert "best-fit" not in shown
    else:
        labels = [s["label"] for s in _payload(result)["series"]]
        assert not [label for label in labels if label.startswith("Fitted")], labels


AL2O3_CR_ALL_BANDS = [18149.0, 24570.0, 14405.0]
"""Al2O3:Cr3+, the three observed bands of ``audit/jce2023/primary_sources.csv`` (4T2,
4T1, 2E), passed unlabelled with spin-forbidden fitting on: Dq and B undetermined, and
the spin-allowed fit (1814.9) lies outside the tied minima's spread (Task 9, C6)."""

RANGE_NOT_BOUNDS = "the spread spans the tied minima found, not bounds on the answer"
OUTSIDE = "the true value can lie outside it"
SF_UNLABELLED = (
    "unlabelled spin-forbidden fit: labelling the bands, or fitting the spin-allowed "
    "bands only, may give a different answer"
)


def test_undetermined_warning_says_the_range_is_not_a_bound() -> None:
    """The spread of tied minima is named as such, not as bounds on Dq.

    Observed red (b219f71): no warning contains the phrase; the undetermined warning
    ended "...the reported value is one of them, for display".
    """
    fit = _tool("ts_fit_spectrum").fn(
        d_count=3, observed_peaks_cm1=AL2O3_CR_ALL_BANDS, include_spin_forbidden=True
    )
    assert fit.Dq_source == "undetermined"
    joined = " | ".join(fit.warnings)
    assert RANGE_NOT_BOUNDS in joined
    assert OUTSIDE in joined
    assert SF_UNLABELLED in joined


def test_provenance_descriptions_say_the_range_is_not_a_bound() -> None:
    """Dq_source and B_source descriptions carry the same caution as the warning.

    Observed red (b219f71): ``AssertionError: Dq_source`` / ``assert 'not a bound' in
    "Where fitted_Dq comes from: 'fitted', or 'undetermined' when tied minima disagree
    on it -- ..."``.
    """
    for name in ("Dq_source", "B_source"):
        description = FitResult.model_fields[name].description or ""
        assert "not a bound" in description, name
        assert "can lie outside" in description, name


def test_spin_allowed_fit_gets_no_spin_forbidden_caution() -> None:
    """The unlabelled spin-forbidden caution does not fire on a spin-allowed fit."""
    fit = _tool("ts_fit_spectrum").fn(d_count=3, observed_peaks_cm1=AL2O3_CR_ALL_BANDS[:2])
    assert all(SF_UNLABELLED not in w for w in fit.warnings)
