"""Resolve and cross-check the version a release tag refers to.

Version strings are not interchangeable in this project. `rrt bump alpha`
writes a SemVer-style pre-release (``1.8.0-alpha.1``) into ``pyproject.toml``
and the git tag, but the wheel that uv builds — and therefore the version on
PyPI, and the version a ``.mcpb`` bundle must pin — is the PEP 440
normalisation of it (``1.8.0a1``). Comparing or pattern-matching the raw
strings silently gets this wrong: a naive ``*(a|b|rc)[0-9]*$`` test reads
``1.8.0-alpha.1`` as a stable release and publishes it as one.

So parse, don't pattern-match. This emits the normalised version (the only
form that should ever reach PyPI or a bundle pin), the raw tag form, and a
correct pre-release flag, and refuses to continue when a tag disagrees with
the artifact that was actually built.

Usage::

    python scripts/release_version.py --dist dist [--ref-name v1.8.0-alpha.1]
"""

from __future__ import annotations

import argparse
import os
import re
import sys

from pathlib import Path

from packaging.utils import canonicalize_name
from packaging.version import InvalidVersion
from packaging.version import Version


PACKAGE = "tanabesugano"
WHEEL_RE = re.compile(r"^(?P<name>[^-]+)-(?P<version>[^-]+)-.*\.whl$")


def version_from_dist(dist_dir: Path) -> Version:
    """Read the version from the wheel filename in *dist_dir*."""
    wheels = sorted(dist_dir.glob("*.whl"))
    if not wheels:
        msg = f"no wheel found in {dist_dir}"
        raise SystemExit(f"::error::{msg}")
    for wheel in wheels:
        match = WHEEL_RE.match(wheel.name)
        if match and canonicalize_name(match["name"]) == canonicalize_name(PACKAGE):
            return Version(match["version"])
    msg = f"no {PACKAGE} wheel among {[w.name for w in wheels]}"
    raise SystemExit(f"::error::{msg}")


def version_from_ref(ref_name: str) -> Version | None:
    """Parse a ``v``-prefixed tag ref into a version, or None if not a tag."""
    if not ref_name.startswith("v"):
        return None
    try:
        return Version(ref_name[1:])
    except InvalidVersion:
        raise SystemExit(f"::error::tag {ref_name!r} is not a valid PEP 440 version") from None


def emit(**outputs: str) -> None:
    """Write key=value pairs to GITHUB_OUTPUT when set, and always to stdout."""
    lines = [f"{key}={value}" for key, value in outputs.items()]
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with Path(github_output).open("a", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")
    for line in lines:
        print(line)


def main() -> int:
    """Resolve the release version and cross-check it against the tag."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist", type=Path, help="directory holding the built wheel")
    parser.add_argument("--ref-name", default=os.environ.get("GITHUB_REF_NAME", ""))
    args = parser.parse_args()

    tag_version = version_from_ref(args.ref_name)
    dist_version = version_from_dist(args.dist) if args.dist else None

    # A tag that disagrees with the artifact means the bump never landed, or the
    # wrong commit was tagged. Either way the release would be mislabelled.
    if tag_version is not None and dist_version is not None and tag_version != dist_version:
        print(
            f"::error::tag {args.ref_name} resolves to {tag_version} but the built "
            f"artifact is {dist_version} — the version bump is missing from this commit",
        )
        return 1

    version = tag_version or dist_version
    if version is None:
        print("::error::need --dist or a v-prefixed --ref-name")
        return 1

    emit(
        version=str(version),
        raw_version=args.ref_name[1:] if tag_version is not None else str(version),
        prerelease="true" if version.is_prerelease else "false",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
