"""Tabular ts_* tools: sorted term-energy data at a chosen Dq."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel
from pydantic import Field

from tanabesugano import __version__
from tanabesugano.mcp._compute import compute_point
from tanabesugano.mcp._inputs import D_COUNT_LITERAL
from tanabesugano.mcp.models import ComputeError
from tanabesugano.mcp.tools._shared import READONLY
from tanabesugano.mcp.tools._shared import TS_META
from tanabesugano.mcp.tools._shared import resolve_bc


if TYPE_CHECKING:
    from fastmcp import FastMCP


class TermEnergyRow(BaseModel):
    """One eigenvalue row in the sorted terms table."""

    term: str = Field(description="Term-symbol key (e.g. '4_T_1').")
    multiplicity: int = Field(description="Spin multiplicity (2S+1).")
    level: int = Field(description="Level index within the term (0 = lowest).")
    energy_cm: float = Field(description="Eigenvalue in wavenumbers (cm^-1).")
    energy_over_B: float = Field(description="Eigenvalue normalised by Racah B.")
    is_ground: bool = Field(description="True if this is the lowest eigenvalue overall.")


class TermsTable(BaseModel):
    """Sorted terms table for one (d_count, Dq, B, C) point."""

    d_count: int
    Dq: float
    B: float
    C: float
    rows: list[TermEnergyRow]


def register(mcp: FastMCP) -> None:
    """Register the ts_terms_table_data tool."""

    @mcp.tool(
        name="ts_terms_table_data",
        title="Sorted term-energy table",
        version=__version__,
        tags={"tanabesugano", "table"},
        annotations=READONLY,
        meta=TS_META,
    )
    def ts_terms_table_data(
        d_count: D_COUNT_LITERAL,  # type: ignore[valid-type]
        Dq: float = 900.0,
        B: float | None = None,
        C: float | None = None,
    ) -> TermsTable | ComputeError:
        """Return all eigenvalues at one Dq, sorted ascending with multiplicity.

        Useful for agent workflows that need a flat tabular view ("which term
        is at ~17500 cm^-1 for Cr3+?") rather than a JSON blob keyed by term.
        Drives the DataTable surfaces in `ts_diagram_app` and friends.
        """
        b_val, c_val = resolve_bc(d_count, B, C)
        if b_val <= 0:
            return ComputeError(error=f"Racah B must be positive, got {b_val}")
        try:
            terms = compute_point(d_count, Dq, b_val, c_val)
        except (ValueError, RuntimeError) as exc:
            return ComputeError(error=str(exc))

        rows: list[TermEnergyRow] = []
        for term, energies in terms.items():
            mult = _parse_multiplicity(term)
            for level, e in enumerate(energies):
                rows.append(
                    TermEnergyRow(
                        term=term,
                        multiplicity=mult,
                        level=level,
                        energy_cm=float(e),
                        energy_over_B=float(e / b_val) if b_val else 0.0,
                        is_ground=False,
                    ),
                )
        rows.sort(key=lambda r: r.energy_cm)
        if rows:
            rows[0].is_ground = True
        return TermsTable(d_count=d_count, Dq=Dq, B=b_val, C=c_val, rows=rows)


def _parse_multiplicity(term: str) -> int:
    head = term.split("_", 1)[0]
    try:
        return int(head)
    except ValueError:
        return 0
