"""`CITATION.cff` must agree with the package it claims to describe.

`rrt` rewrites the `version:` line on every bump -- `[[tool.rrt.version_targets]]`
names `CITATION.cff` with a regex for exactly that field -- but its schema has no
concept of a date, so `date-released:` is not maintained by anything. It drifted
silently for two releases: the file still read `2026-08-20`, the 2.0.0-alpha.1
date, after both the alpha.2 and beta.1 bumps had moved `version:` past it.

That is the kind of defect nothing else here can catch. It breaks no import, no
render and no calculation; it only misinforms whoever cites the software, and
only after the artifact has been published under a DOI.
"""

from __future__ import annotations

import re

from pathlib import Path

import pytest

from tanabesugano import __version__


_ROOT = Path(__file__).parents[3]
CITATION = _ROOT / "CITATION.cff"
CHANGELOG = _ROOT / "CHANGELOG.md"


def _cff_field(name: str) -> str:
    """One top-level scalar out of CITATION.cff, without taking a YAML dependency."""
    match = re.search(rf"^{re.escape(name)}:\s*(\S+)\s*$", CITATION.read_text(), re.MULTILINE)
    assert match, f"CITATION.cff has no top-level {name!r} field"
    return match.group(1).strip().strip('"')


def test_citation_version_matches_the_package() -> None:
    """The version rrt rewrites has to be the version that ships."""
    assert _cff_field("version") == __version__


def test_citation_release_date_matches_the_changelog() -> None:
    """`date-released` must be the date the changelog gives this version.

    The changelog is the reference rather than "today" on purpose: a release
    branch can be cut, reviewed and merged across a day boundary, and the date
    a citation should carry is the one the release itself claims, not whenever
    the test happens to run.

    Observed failure before the fix::

        AssertionError: CITATION.cff says date-released: 2026-08-20 but
        CHANGELOG.md dates 2.0.0-beta.1 as 2026-08-23
    """
    heading = re.search(
        rf"^## \[{re.escape(__version__)}\]\s*-\s*(\d{{4}}-\d{{2}}-\d{{2}})\s*$",
        CHANGELOG.read_text(),
        re.MULTILINE,
    )
    if heading is None:
        pytest.fail(
            f"CHANGELOG.md has no dated section for {__version__}. `rrt bump` promotes "
            f"[Unreleased] to the new version in the same commit, so a missing section "
            f"means the bump was incomplete or hand-edited afterwards.",
        )

    released = _cff_field("date-released")
    assert released == heading.group(1), (
        f"CITATION.cff says date-released: {released} but CHANGELOG.md dates "
        f"{__version__} as {heading.group(1)}"
    )
