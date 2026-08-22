"""The HTML drift gate must be able to fail.

`scripts/regenerate_ts_diagrams.py` compares committed Plotly diagrams against
freshly generated ones. It cannot compare bytes -- plotly stamps a fresh UUID
per write, and full-precision floats differ in the last ulp across BLAS
implementations -- so it compares the set of level identifiers each file names.

That design has one lethal failure mode: if the extractor finds nothing, an
empty set equals an empty set and every diagram is reported as current, forever.
This is not hypothetical. Typesetting the legends removed the raw solver keys
the previous extractor grepped for, which would have turned the gate into a
permanent pass on the very commit that changed the diagrams.

Observed red before the guard existed (`uv run python` against the real
regenerated d6 diagram, with `"uid"` renamed to `"xid"` to simulate a diagram
from before uid stamping):

    no_uid.html    -> 0 uids, compares equal to any other empty set
    bad_vocab.html -> 0 uids, compares equal to no_uid.html

and after:

    no_uid.html    -> VacuousGateError: no_uid.html carries no trace uid
                      metadata, so there is nothing to compare -- an empty set
                      would match any other empty set and the drift gate would
                      pass vacuously.
    bad_vocab.html -> drift visible: +['1_T_3#0'] -['1_T_2#0']

`1_T_3` is the real historical defect: an irrep that does not exist in Oh, which
survived for the life of the project because nothing could tell a valid key from
a typo. It is used here as the canary precisely because the extractor must NOT
filter to legal keys -- a pattern that only matches valid vocabulary is blind to
exactly the thing it is guarding against.
"""

from __future__ import annotations

import importlib.util
import sys

from pathlib import Path

import pytest


_SCRIPT = Path(__file__).parents[3] / "scripts" / "regenerate_ts_diagrams.py"


def _load_gate():
    """Import the build script by path; scripts/ is not an installed package."""
    spec = importlib.util.spec_from_file_location("_regen_ts_diagrams", _SCRIPT)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        pytest.skip(f"cannot load {_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


pytest.importorskip("plotly", reason="install with `pip install tanabesugano[plotly]`")

gate = _load_gate()


@pytest.fixture(scope="module")
def diagram(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A real regenerated d6 Tanabe-Sugano diagram.

    Generated rather than fixtured: a checked-in HTML sample would drift from
    what `interactive_plot` actually writes, and this gate exists to catch
    precisely that kind of drift.
    """
    from tanabesugano.cmd import CMDmain

    out = tmp_path_factory.mktemp("diagrams")
    cwd = Path.cwd()
    import os

    os.chdir(out)
    try:
        cmd = CMDmain(Dq=2506.5, B=1080.0, C=4773.0, nroots=20, d_count=6)
        cmd.calculation()
        cmd.interactive_plot()
    finally:
        os.chdir(cwd)
    written = sorted(out.glob("TS-diagram_*.html"))
    assert written, "interactive_plot wrote no Tanabe-Sugano diagram"
    return written[0]


def test_a_current_diagram_names_every_level(diagram: Path) -> None:
    """d6 holds 43 levels, and each must be individually identifiable."""
    from tanabesugano.levels import LevelSet

    expected = {lv.uid for lv in LevelSet.solve(6, 2506.5, 1080.0, 4773.0).levels}
    assert gate._html_level_uids(diagram) == expected


def test_a_diagram_without_uids_raises_instead_of_comparing_empty(
    diagram: Path,
    tmp_path: Path,
) -> None:
    """The guard that stops the gate degrading into a permanent pass."""
    stripped = tmp_path / "no_uid.html"
    stripped.write_text(
        diagram.read_text(encoding="utf-8").replace('"uid"', '"xid"'),
        encoding="utf-8",
    )
    with pytest.raises(gate.VacuousGateError, match="pass vacuously"):
        gate._html_level_uids(stripped)


def test_a_stale_vocabulary_is_visible_as_drift(diagram: Path, tmp_path: Path) -> None:
    """`1_T_3` is not a legal Oh irrep, and the gate must still see it."""
    corrupted = tmp_path / "bad_vocab.html"
    corrupted.write_text(
        diagram.read_text(encoding="utf-8").replace('"uid":"1_T_2#0"', '"uid":"1_T_3#0"'),
        encoding="utf-8",
    )
    current = gate._html_level_uids(diagram)
    stale = gate._html_level_uids(corrupted)
    assert stale != current
    assert stale - current == {"1_T_3#0"}
    assert current - stale == {"1_T_2#0"}


def test_docs_site_is_no_longer_a_target() -> None:
    """The 80 MB tree nothing built. Removed here and from the repo together."""
    assert not any("docs-site" in str(path) for path in gate.TARGET_DIRS)
