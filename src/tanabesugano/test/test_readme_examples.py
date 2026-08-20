"""Execute the Python examples in README.md.

The README documented `from tanabesugano import TanabeSugano` for years. That
class has never existed -- it raised ImportError on every released version --
because nothing ever ran the README. Prose drifts silently; code does not, once
something executes it.

Each ```python block in README.md is compiled and run in a fresh namespace. A
block that needs a scratch directory gets one via chdir, so an example may
write files without polluting the repo.
"""

from __future__ import annotations

import re

from pathlib import Path

import pytest


README = Path(__file__).resolve().parents[3] / "README.md"
_BLOCK_RE = re.compile(r"^```python\n(.*?)^```", re.MULTILINE | re.DOTALL)


def python_blocks() -> list[str]:
    """Every fenced ```python block in the README, in document order."""
    if not README.is_file():  # pragma: no cover - packaging layouts without the README
        pytest.skip(f"README.md not found at {README}")
    return _BLOCK_RE.findall(README.read_text(encoding="utf-8"))


def test_the_readme_actually_contains_python_examples() -> None:
    """Guards the guard: a regex that silently matches nothing proves nothing.

    If the fence style ever changes, every other test here would vacuously pass
    on an empty list. This is the same class of mistake as a registered table
    no test parametrizes over.
    """
    assert len(python_blocks()) >= 2


@pytest.mark.parametrize("index", range(len(python_blocks())))
def test_readme_python_block_runs(index: int, tmp_path: Path, monkeypatch) -> None:
    """Observed failure before the fix::

    ImportError: cannot import name 'TanabeSugano' from 'tanabesugano'
    """
    import matplotlib

    matplotlib.use("Agg")
    source = python_blocks()[index]
    monkeypatch.chdir(tmp_path)
    exec(compile(source, f"<README block {index}>", "exec"), {"__name__": "__main__"})
