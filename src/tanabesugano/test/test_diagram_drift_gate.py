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
import re
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


def test_a_plotly_native_uid_cannot_stand_in_for_a_level_uid(
    diagram: Path,
    tmp_path: Path,
) -> None:
    """Plotly traces carry a `uid` of their own, and it must not be counted.

    Raised in review on #199. Plotly's own trace `uid` serialises to the same
    JSON key the moment anything sets it, so a pattern matching every `"uid"`
    would let those values stand in for ours -- a diagram with no `meta.uid`
    would look populated and never raise, and plotly's uids are not stable
    across writes, so the gate would report drift forever.

    Verified against plotly 6.9.0 that our output currently carries no native
    trace uid, which is precisely the state in which such a trap goes
    unnoticed. Requiring the `<term>#<index>` shape is what excludes them.
    """
    # Plotly's own trace uids are short hex strings, NOT uuids. An earlier
    # version of this test used a 36-character uuid, which the pattern it was
    # meant to condemn rejected on length alone -- so it passed against the
    # broken code. The value below is the shape plotly actually emits.
    plotly_only = tmp_path / "plotly_only.html"
    plotly_only.write_text(
        re.sub(
            r'"uid":"[^"]*"',
            '"uid":"f3a91c4e"',
            diagram.read_text(encoding="utf-8"),
        ),
        encoding="utf-8",
    )
    with pytest.raises(gate.VacuousGateError, match="pass vacuously"):
        gate._html_level_uids(plotly_only)


def test_the_extractor_still_sees_an_illegal_irrep(diagram: Path, tmp_path: Path) -> None:
    """Tightening the SHAPE must not narrow the VOCABULARY.

    `1_T_3` is not a legal Oh irrep. A pattern that only accepted valid term
    keys would be blind to exactly what the gate guards against, so the shape
    requirement has to admit a well-formed key with a nonsense irrep.
    """
    corrupted = tmp_path / "illegal_irrep.html"
    corrupted.write_text(
        diagram.read_text(encoding="utf-8").replace('"uid":"1_T_2#0"', '"uid":"1_T_9#0"'),
        encoding="utf-8",
    )
    assert "1_T_9#0" in gate._html_level_uids(corrupted)


def test_docs_site_is_no_longer_a_target() -> None:
    """The 80 MB tree nothing built. Removed here and from the repo together."""
    assert not any("docs-site" in str(path) for path in gate.TARGET_DIRS)
