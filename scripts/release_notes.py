"""Produce the GitHub Release body for a tag, without ever failing the release.

This is the step that broke v1.7.0, v1.7.1 and v1.7.2. The workflow called
``rrt release notes`` with no target, so it read ``[Unreleased]`` — which
``changelog_workflow = "incremental"`` empties when the bump PR promotes it to
a versioned heading. It exited 1 on every tag, *after* PyPI had already
published, and the job that attached the release assets was skipped.

Two lessons are encoded here. First, target the tag's own section rather than
``[Unreleased]``, trying the raw tag spelling (``1.8.0-alpha.1``, which is what
``rrt`` writes into the changelog) before the PEP 440 normalisation
(``1.8.0a1``). Second, degrade instead of aborting: by the time this runs the
artifacts are already public, so a missing changelog section must produce a
thinner release body, never a failed release.

Usage::

    python scripts/release_notes.py --version 1.8.0a1 \\
        --raw-version 1.8.0-alpha.1 --output RELEASE_CHANGELOG.md
"""

from __future__ import annotations

import argparse
import subprocess
import sys

from pathlib import Path


def _warn(message: str) -> None:
    print(f"::warning::{message}", file=sys.stderr)


def _run_rrt(rrt: list[str], args: list[str], output: Path) -> bool:
    """Run one `rrt release notes` invocation; True if it wrote a non-empty body."""
    try:
        result = subprocess.run(  # noqa: S603
            [*rrt, "release", "notes", *args, "--format", "md", "--output", str(output)],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        _warn(f"could not execute {rrt[0]}: {exc}")
        return False
    if result.returncode != 0:
        _warn(f"rrt release notes {' '.join(args)} failed: {result.stderr.strip()}")
        return False
    return output.exists() and bool(output.read_text(encoding="utf-8").strip())


def build_body(version: str, raw_version: str, output: Path, rrt: list[str]) -> str:
    """Write the release body to *output* and return which strategy produced it."""
    # rrt writes the changelog heading using the raw (SemVer-ish) spelling, so try
    # that first; the normalised form covers changelogs written by other means.
    for candidate in dict.fromkeys([raw_version, version]):
        if _run_rrt(rrt, ["--version", candidate], output):
            return f"section [{candidate}]"

    _warn(f"no [{raw_version}] changelog section; falling back to --latest-released")
    if _run_rrt(rrt, ["--latest-released"], output):
        return "latest released section"

    _warn("no released changelog section found; emitting a minimal body")
    output.write_text(
        f"## {version}\n\nSee [CHANGELOG.md](CHANGELOG.md) for details.\n",
        encoding="utf-8",
    )
    return "minimal fallback body"


def main() -> int:
    """Always returns 0: a release whose artifacts are public must not fail here."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True, help="PEP 440 normalised version")
    parser.add_argument("--raw-version", help="tag spelling; defaults to --version")
    parser.add_argument("--output", type=Path, default=Path("RELEASE_CHANGELOG.md"))
    parser.add_argument(
        "--rrt",
        default="rrt",
        help="repo-release-tools executable (space-separated if it needs a prefix)",
    )
    args = parser.parse_args()

    strategy = build_body(
        version=args.version,
        raw_version=args.raw_version or args.version,
        output=args.output,
        rrt=args.rrt.split(),
    )
    print(f"Release body written to {args.output} from {strategy}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
