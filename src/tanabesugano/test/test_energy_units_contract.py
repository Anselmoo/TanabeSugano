"""Contract tests: every energy a tool reads or draws states its unit.

Inputs are cm^-1 (plan E, option A); the two fit apps also take an ``energy_unit``
for their peaks, and axis limits are in the plotted unit. The set of numeric
parameters is pinned and built by schema *type*, not by name, so a renamed or
added energy parameter cannot fall outside the check (Fable objection 5: three
tools call their peaks ``observed_peaks``, not ``observed_peaks_cm1``).

Provenance: the expectations are the unit rule itself; no number here comes from
the code under test.
"""

from __future__ import annotations

import re

from pathlib import Path

from tanabesugano.mcp.server import create_server
from tanabesugano.test._loop import run_loop_free


MCP_DIR = Path(__file__).resolve().parents[1] / "mcp"
UNIT_TEXT = re.compile(r"cm⁻¹|cm\^-1|cm-1|energy_unit")


def _is_number(schema: dict) -> bool:
    """True for a number or integer, an array or fixed tuple of them, or an optional one."""
    if schema.get("type") in {"number", "integer"}:
        return True
    if schema.get("type") == "array":
        items = schema.get("items")
        if isinstance(items, dict) and _is_number(items):
            return True
        prefix = schema.get("prefixItems") or []
        if prefix and all(_is_number(p) for p in prefix):
            return True
    return any(_is_number(s) for s in schema.get("anyOf", []))


def _numeric_params() -> dict[tuple[str, str], str]:
    """Every (tool, parameter) whose schema is numeric, mapped to its description."""

    async def go():
        server = create_server()
        return await server.list_tools()

    tools = run_loop_free(go)
    return {
        (tool.name, name): description
        for tool in tools
        for name, description in _numeric_fields(tool.parameters).items()
        if name not in COUNTERS
    }


def _numeric_fields(parameters: dict, node: dict | None = None, prefix: str = "") -> dict[str, str]:
    """Every numeric field of one tool's parameter schema, mapped to its description.

    Follows ``$ref`` into ``$defs`` (also inside ``anyOf``) and names a model's
    fields ``param.field``, so a model parameter cannot hide an energy.
    """
    defs = parameters.get("$defs", {})

    def resolve(schema: dict) -> dict:
        ref = schema.get("$ref", "")
        return defs.get(ref.rsplit("/", 1)[-1], schema) if ref.startswith("#/$defs/") else schema

    found: dict[str, str] = {}
    for name, raw in (node or parameters).get("properties", {}).items():
        if _is_number(raw):
            found[prefix + name] = raw.get("description", "")
            continue
        for option in [raw, *raw.get("anyOf", [])]:
            target = resolve(option)
            if target.get("properties"):
                found |= _numeric_fields(parameters, target, f"{prefix}{name}.")
    return found


COUNTERS = frozenset(
    {"d_count", "d_counts", "dpi", "grid_steps", "n_energy_points", "n_points", "steps"}
)
"""Integer parameters that count or select, never an energy; excluded by name."""


ENERGY_PARAMS: frozenset[tuple[str, str]] = frozenset(
    {
        ("ts_compare_app", "dq_max"),
        ("ts_compare_app", "dq_min"),
        ("ts_compute_app", "B"),
        ("ts_compute_app", "C"),
        ("ts_compute_app", "Dq"),
        ("ts_compute_app", "max_energy_cm"),
        ("ts_correlation_diagram_app", "B"),
        ("ts_correlation_diagram_app", "C"),
        ("ts_correlation_diagram_app", "strong_field_Dq"),
        ("ts_diagram_app", "B"),
        ("ts_diagram_app", "C"),
        ("ts_diagram_app", "dq_max"),
        ("ts_diagram_app", "dq_min"),
        ("ts_diagram_app", "x_max"),
        ("ts_diagram_app", "x_min"),
        ("ts_diagram_app", "y_max"),
        ("ts_diagram_app", "y_min"),
        ("ts_fit_plot_app", "C"),
        ("ts_fit_plot_app", "observed_peaks"),
        ("ts_fit_script", "C"),
        ("ts_fit_script", "observed_peaks"),
        ("ts_fit_spectrum", "C"),
        ("ts_fit_spectrum", "dq_bounds"),
        ("ts_fit_spectrum", "observed_peaks_cm1"),
        ("ts_nephelauxetic", "fitted_B"),
        ("ts_orgel_diagram_app", "B"),
        ("ts_orgel_diagram_app", "C"),
        ("ts_orgel_diagram_app", "dq_max"),
        ("ts_orgel_diagram_app", "dq_min"),
        ("ts_overlay_app", "dq_max"),
        ("ts_overlay_app", "dq_min"),
        ("ts_oxidation_landscape_app", "B"),
        ("ts_oxidation_landscape_app", "C"),
        ("ts_oxidation_landscape_app", "Dq"),
        ("ts_oxidation_landscape_app", "broadening_cm"),
        ("ts_oxidation_landscape_app", "max_energy_cm"),
        ("ts_plot_png", "B"),
        ("ts_plot_png", "C"),
        ("ts_plot_png", "dq_max"),
        ("ts_plot_png", "dq_min"),
        ("ts_plot_png", "x_max"),
        ("ts_plot_png", "x_min"),
        ("ts_plot_png", "y_max"),
        ("ts_plot_png", "y_min"),
        ("ts_plot_view", "B"),
        ("ts_plot_view", "C"),
        ("ts_plot_view", "dq_max"),
        ("ts_plot_view", "dq_min"),
        ("ts_ratio_fit_app", "C"),
        ("ts_ratio_fit_app", "b_max"),
        ("ts_ratio_fit_app", "b_min"),
        ("ts_ratio_fit_app", "v1"),
        ("ts_ratio_fit_app", "v2"),
        ("ts_ratio_fit_app", "v3"),
        ("ts_reverse_fit_app", "C"),
        ("ts_reverse_fit_app", "b_max"),
        ("ts_reverse_fit_app", "b_min"),
        ("ts_reverse_fit_app", "dq_max_search"),
        ("ts_reverse_fit_app", "observed_peaks"),
        ("ts_spectrum_app", "B"),
        ("ts_spectrum_app", "C"),
        ("ts_spectrum_app", "Dq"),
        ("ts_spectrum_app", "broadening"),
        ("ts_spin_crossover_app", "B"),
        ("ts_spin_crossover_app", "C"),
        ("ts_spin_crossover_app", "dq_max"),
        ("ts_terms_table_data", "B"),
        ("ts_terms_table_data", "C"),
        ("ts_terms_table_data", "Dq"),
    }
)
"""Every numeric tool parameter at 1cb2ea7, listed from the live schema: all are energies
(cm^-1, or the plotted unit for axis limits and the apps' energy_unit peaks)."""


def test_no_second_ev_constant() -> None:
    """cm^-1 -> eV is defined once, in ``constants``; no MCP module carries its own literal."""
    offenders = [p.name for p in MCP_DIR.rglob("*.py") if "8065" in p.read_text()]
    assert offenders == []


def test_energy_param_set_is_pinned() -> None:
    """The live numeric parameters are exactly the pinned set, and it is not trivially small."""
    assert len(ENERGY_PARAMS) >= 10
    assert set(_numeric_params()) == ENERGY_PARAMS


def test_every_energy_param_names_its_unit() -> None:
    """Each pinned parameter's description says cm^-1, or names energy_unit."""
    missing = sorted(k for k, d in _numeric_params().items() if not UNIT_TEXT.search(d))
    assert missing == []


def test_ev_axis_keeps_cm1_parameters_labelled() -> None:
    """On an eV axis the title's parameters still say cm^-1 -- the Dq range included (E5.4).

    Observed red (1cb2ea7): title ``d3 (4F) — B=918, C=4133 cm⁻¹  [Dq 0–1500, 60 pts]``
    beside ``y_label='E (eV)'``: the Dq range carried no unit on a chart drawn in eV.
    """
    import json

    async def go():
        server = create_server()
        tool = await server.get_tool("ts_diagram_app")
        return tool.fn(d_count=3, energy_unit="eV", normalize=False)

    payload = json.loads(run_loop_free(go).content[0].text)
    assert "eV" in payload["y_label"]
    assert re.search(r"C=\d+ cm⁻¹", payload["title"]), payload["title"]
    assert re.search(r"Dq [\d.]+–[\d.]+ cm⁻¹", payload["title"]), payload["title"]


def test_walker_sees_integer_and_model_fields() -> None:
    """An int parameter and a field inside a model parameter are both seen (final review I2).

    Without this a future ``max_energy_cm: int`` or ``params: TSInput`` would fall
    outside the pinned set and both tests above would stay green.
    Observed red (562491b): ``assert {'dq'} == {'cutoff', 'dq', 'params.B'}``.
    """
    schema = {
        "properties": {
            "dq": {"type": "number"},
            "cutoff": {"type": "integer", "description": "cm^-1"},
            "params": {"$ref": "#/$defs/Model"},
            "label": {"type": "string"},
        },
        "$defs": {"Model": {"type": "object", "properties": {"B": {"type": "number"}}}},
    }
    assert set(_numeric_fields(schema)) == {"dq", "cutoff", "params.B"}


def test_counters_are_live() -> None:
    """Every excluded counter still exists, so the exclusion list cannot go stale.

    Green on arrival: pins the exclusion added with the walker fix (final review I2).
    """

    async def go():
        return await create_server().list_tools()

    live = {name for tool in run_loop_free(go) for name in tool.parameters.get("properties", {})}
    assert live >= COUNTERS
