"""Contract tests for ts_reverse_fit_app.

The tool must satisfy BOTH halves of its docstring promise -- "best-fit
parameters plus a residuals table":

* a human-visible Prefab card (pinned here so the rendering cannot regress
  silently when the return type changes), and
* a machine-readable payload, so an agent calling the tool gets numbers rather
  than only a widget.

The render assertions exist specifically so the second half could be added
safely; without them a return-type change is unverifiable.
"""

from __future__ import annotations

import json

import pytest

from tanabesugano.mcp.server import create_server
from tanabesugano.test._loop import run_loop_free


BANDS = [8500.0, 13800.0, 25300.0]  # [Ni(H2O)6]2+


def call_reverse_fit(**kwargs):
    async def go():
        server = create_server()
        tool = await server.get_tool("ts_reverse_fit_app")
        return tool.fn(**kwargs)

    return run_loop_free(go)


def rendered_payload(app) -> str:
    """Serialised Prefab card. `.to_json()` carries the content tree."""
    return str(app.to_json() if hasattr(app, "to_json") else app)


class TestPrefabCardRenders:
    """Pin the visible card so a return-type change cannot silently break it."""

    @pytest.fixture
    def card(self) -> str:
        return rendered_payload(
            call_reverse_fit(d_count=8, observed_peaks=BANDS, grid_steps=25),
        )

    @pytest.mark.parametrize(
        "fragment",
        ["Reverse fit: d8", "Best Dq", "Best B", "RMS residual"],
    )
    def test_card_shows_headline_metrics(self, card: str, fragment: str) -> None:
        assert fragment in card

    def test_card_names_the_ground_term(self, card: str) -> None:
        """d8 is invariantly 3A2g; the card must say so rather than leave it implicit."""
        assert "3_A_2" in card

    def test_card_has_a_residuals_table(self, card: str) -> None:
        for column in ("observed_cm", "predicted_cm", "delta_cm"):
            assert column in card, f"residuals table missing column {column}"

    def test_card_has_the_grid_candidate_table(self, card: str) -> None:
        assert "Top 20 grid candidates" in card

    def test_term_table_distinguishes_the_two_triplet_t1_levels(self, card: str) -> None:
        """d8 has exactly two 3T1g levels (3F and 3P parents).

        The term-energies table listed `term` and `level` as separate columns,
        so a rendered cell read "3_T_1" twice and only the neighbouring Level
        column said which was which. The label column names each row outright.
        """
        assert "3_T_1(a)" in card
        assert "3_T_1(b)" in card
        # 3T2g is the only 3T2g in d8 -- it must stay bare, not become "(a)".
        assert "3_T_2(a)" not in card

    def test_card_reports_a_fit_not_a_failure(self, card: str) -> None:
        """Regression guard: this rendered "No fit found" for EVERY d-count.

        The multiplicity parser was handed free-ion notation ("3F"), returned 0,
        and never matched an octahedral key, so the candidate list was always
        empty.
        """
        assert "No fit found" not in card


class TestMachineReadableResult:
    """An agent must get numbers back, not only a rendered widget."""

    def test_returns_structured_fit_data(self) -> None:
        result = call_reverse_fit(d_count=8, observed_peaks=BANDS, grid_steps=25)
        data = extract_fit_data(result)
        assert data is not None, "no machine-readable fit payload in the tool result"
        assert data["Dq"] == pytest.approx(850.0, abs=60.0)
        assert data["B"] == pytest.approx(940.0, abs=120.0)
        assert data["ground_term"] == "3_A_2"
        assert len(data["residuals"]) == len(BANDS)
        for row in data["residuals"]:
            assert {"observed_cm1", "predicted_cm1", "delta_cm1"} <= set(row)


def extract_fit_data(result) -> dict | None:
    """Pull the fit payload out of whatever the tool returns.

    structured_content is checked FIRST: the rendered Prefab card is itself a
    JSON object in a text block, so scanning content first would return the card
    and never reach the fit data.
    """
    structured = getattr(result, "structured_content", None)
    if isinstance(structured, dict) and structured:
        return structured.get("result", structured)
    content = getattr(result, "content", None)
    if content:
        for block in content:
            text = getattr(block, "text", None)
            if text and text.strip().startswith("{"):
                payload = json.loads(text)
                if "Dq" in payload:  # skip the Prefab card envelope
                    return payload
    return None


class TestErrorBranchesStillRender:
    """The early-return branches must render, not silently blank the card.

    Found by `ty`: three tools declare `-> ToolResult` but returned a bare
    `PrefabApp` on their error paths. FastMCP serialises a bare PrefabApp via
    `model_dump()`, which drops the entire child tree built by the `with`
    block -- so the user got an EMPTY widget instead of the message explaining
    what went wrong. Measured before the fix: a 20-character payload with the
    heading gone.

    The happy paths were already correct, which is exactly why this survived:
    every test drove a successful fit.
    """

    def _payload(self, **kwargs) -> str:
        result = call_reverse_fit(**kwargs)
        blocks = getattr(result, "content", None) or []
        return " ".join(getattr(b, "text", "") or "" for b in blocks)

    def test_empty_peak_list_explains_itself(self) -> None:
        assert "No valid peaks provided" in self._payload(
            d_count=8,
            observed_peaks=[],
            grid_steps=10,
        )

    def test_all_non_positive_peaks_explain_themselves(self) -> None:
        """Peaks are filtered by `p > 0`, so this reaches the same branch."""
        assert "No valid peaks provided" in self._payload(
            d_count=8,
            observed_peaks=[0.0, -100.0],
            grid_steps=10,
        )


class TestOneSolverOneAnswer:
    """The app's answer is fit_spectrum's; its grid is a landscape, not an answer.

    Oracle truths come from ``_determinant_oracle`` via the recovery module's helpers;
    the equality cases compare against a direct ``fit_spectrum`` call (pass-through).
    """

    def test_reverse_app_fits_low_spin_when_told(self) -> None:
        """d6 low-spin bands with spin_state='low' come back in that regime.

        C is held at the truth: two bands cannot pin C, and with the default C the
        fit (fit_spectrum's, not the app's) lands at Dq 2620 -- that is plan C's
        default-C limitation, not this test's claim.

        Observed red (3bff962): ``TypeError: ...ts_reverse_fit_app() got an
        unexpected keyword argument 'spin_state'``.
        """
        from tanabesugano.test.test_fit_recovery import oracle_bands

        bands = oracle_bands(6, 2500.0, 700.0, 3080.0, spin_allowed_only=True)[:2]
        data = extract_fit_data(
            call_reverse_fit(
                d_count=6, observed_peaks=[e for e, _u in bands], C=3080.0, spin_state="low"
            )
        )
        assert data is not None
        assert data["Dq"] == pytest.approx(2500.0, rel=0.02)
        assert data["spin_state"] == "low"

    @pytest.mark.parametrize("case", ["d3", "d6-low", "d5-high-sf"])
    def test_reverse_app_matches_fit_spectrum(self, case: str) -> None:
        """App defaults and fit_spectrum defaults give the same Dq and B: one solver.

        Observed red (3bff962): d3 differs (grid node, not the fitted point);
        d6-low / d5-high-sf: unexpected keyword argument ``spin_state`` /
        ``include_spin_forbidden``.
        """
        from tanabesugano.mcp._compute import fit_spectrum
        from tanabesugano.test.test_fit_recovery import D5_HS_POINTS
        from tanabesugano.test.test_fit_recovery import merged_labelled_bands
        from tanabesugano.test.test_fit_recovery import oracle_bands

        kwargs: dict = {}
        if case == "d3":
            d, peaks = (
                3,
                [e for e, _u in oracle_bands(3, 1200.0, 413.1, 1652.4, spin_allowed_only=True)[:3]],
            )
        elif case == "d6-low":
            d = 6
            peaks = [
                e for e, _u in oracle_bands(6, 2500.0, 700.0, 3080.0, spin_allowed_only=True)[:2]
            ]
            kwargs = {"spin_state": "low"}
        else:
            d = 5
            peaks, labels = merged_labelled_bands(5, *D5_HS_POINTS[3], 3)
            kwargs = {"include_spin_forbidden": True, "band_labels": labels}
        direct = fit_spectrum(d, peaks, **kwargs)
        data = extract_fit_data(call_reverse_fit(d_count=d, observed_peaks=peaks, **kwargs))
        assert data is not None
        # The payload rounds to 0.1 cm^-1, so equality is to that resolution.
        assert data["Dq"] == pytest.approx(direct.Dq, abs=0.051)
        assert data["B"] == pytest.approx(direct.B, abs=0.051)

    def test_reverse_app_default_b_range_reaches_low_b(self) -> None:
        """Oracle d2 at B 387: the default B range must contain it.

        Observed red (3bff962): B pinned at the old 400 floor.
        """
        from tanabesugano.test.test_fit_recovery import oracle_bands

        peaks = [e for e, _u in oracle_bands(2, 900.0, 387.0, 1548.0, spin_allowed_only=True)[:3]]
        data = extract_fit_data(call_reverse_fit(d_count=2, observed_peaks=peaks))
        assert data is not None
        assert data["B"] == pytest.approx(387.0, rel=0.02)

    def test_reverse_app_grid_candidates_keep_their_shape(self) -> None:
        """grid_candidates keeps today's rows; minima, warnings and C_source are new keys.

        Observed red (3bff962): ``KeyError: 'minima'``.
        """
        data = extract_fit_data(call_reverse_fit(d_count=8, observed_peaks=BANDS))
        assert data is not None
        rows = data["grid_candidates"]
        assert 0 < len(rows) <= 20
        assert all(set(r) == {"Dq", "B", "RMS"} for r in rows)
        assert [r["RMS"] for r in rows] == sorted(r["RMS"] for r in rows)
        assert data["minima"][0]["Dq"] == pytest.approx(data["Dq"], abs=0.051)
        assert isinstance(data["warnings"], list)
        assert data["C_source"] == "default"


def test_reverse_app_short_label_list_is_an_error_card() -> None:
    """Fewer labels than peaks is reported, not raised.

    Observed red (62797f6, final review): ``IndexError: list index out of range``.
    """
    result = call_reverse_fit(d_count=8, observed_peaks=BANDS, band_labels=["3_T_2", None])
    data = extract_fit_data(result) or result.structured_content
    assert "one label per band" in data["error"]


def test_reverse_app_names_energy_unit_for_ev_peaks() -> None:
    """Peaks given in eV at the default energy_unit point the caller at energy_unit (plan E R4).

    Observed red (0aef909): the error was ``fit never escaped the penalty region``,
    which does not mention energy_unit.
    """
    result = call_reverse_fit(d_count=8, observed_peaks=[1.05, 1.71, 3.14])
    data = extract_fit_data(result) or result.structured_content
    assert "energy_unit" in data["error"]
    assert "eV" in data["error"]


def test_reverse_app_shuffled_labelled_peaks_pair_by_label() -> None:
    """Shuffled labelled oracle bands plus a dropped 0.0 peak: each band keeps its label.

    The 0.0 entry is dropped *with* its label; were it not, every later label would
    shift by one and pair a band with the wrong level. Green on arrival (33dcf7d):
    coverage for the D review's deferred case, not the red of a fix.
    """
    from tanabesugano.test.test_fit_recovery import oracle_bands
    from tanabesugano.test.test_fit_recovery import term_labels

    bands = oracle_bands(8, 850.0, 907.0, 4850.0, spin_allowed_only=True)
    order = [2, 0, 1]
    peaks = [bands[order[0]][0], 0.0, bands[order[1]][0], bands[order[2]][0]]
    labels = term_labels([bands[i] for i in order])
    labels.insert(1, "3_T_2")
    result = call_reverse_fit(d_count=8, observed_peaks=peaks, band_labels=labels)
    data = extract_fit_data(result) or result.structured_content
    assert "error" not in data, data.get("error")
    kept = [p for p in peaks if p > 0]
    assert [r["observed_cm1"] for r in data["residuals"]] == pytest.approx(kept, abs=0.1)
    assert all(abs(r["delta_cm1"]) < 1.0 for r in data["residuals"]), data["residuals"]
