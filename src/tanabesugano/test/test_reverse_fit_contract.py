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
