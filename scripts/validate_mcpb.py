"""Validate a built .mcpb bundle before it is attached to a GitHub Release.

Guards the three defects that shipped silently in v1.7.x, each of which
produced a bundle that Claude Desktop could not start:

1. the launch recipe invoked the ``tanabesugano`` CLI instead of the
   ``tanabesugano-mcp`` server entry point, so the process hung on stdin
   and never answered the JSON-RPC ``initialize`` request;
2. the ``[mcp]`` extra was absent, so ``fastmcp`` was never installed and
   the server exited with its install hint;
3. the runtime reference carried no ``==`` pin, so a bundle labelled
   ``1.7.2`` installed whatever happened to be newest on PyPI.

Usage: ``python scripts/validate_mcpb.py <dist-dir> <expected-version>``
"""

from __future__ import annotations

import json
import sys
import zipfile

from pathlib import Path


EXPECTED_ENTRY_SCRIPT = "tanabesugano-mcp"
EXPECTED_PACKAGE = "tanabesugano[mcp]"
REQUIRED_MEMBERS = ("manifest.json",)


def _fail(message: str) -> None:
    print(f"::error::{message}")
    print(f"FAIL: {message}")


def validate(bundle: Path, expected_version: str) -> list[str]:
    """Return a list of problems found in *bundle*; empty means valid."""
    problems: list[str] = []

    with zipfile.ZipFile(bundle) as archive:
        names = set(archive.namelist())
        for member in REQUIRED_MEMBERS:
            if member not in names:
                problems.append(f"{bundle.name}: missing archive member {member!r}")
        if "manifest.json" not in names:
            return problems
        manifest = json.loads(archive.read("manifest.json"))

    version = manifest.get("version")
    if version != expected_version:
        problems.append(
            f"{bundle.name}: manifest version {version!r} != expected {expected_version!r}"
        )

    args = manifest.get("server", {}).get("mcp_config", {}).get("args", [])
    if not args:
        problems.append(f"{bundle.name}: manifest has no server.mcp_config.args")
        return problems

    # The entry point is the final argv element: `uv tool run --from <spec> <entry>`.
    if args[-1] != EXPECTED_ENTRY_SCRIPT:
        problems.append(
            f"{bundle.name}: launch entry point is {args[-1]!r}, expected "
            f"{EXPECTED_ENTRY_SCRIPT!r} — the bundle would start the CLI, not the MCP server"
        )

    spec = next((a for a in args if a.startswith(EXPECTED_PACKAGE)), None)
    if spec is None:
        problems.append(
            f"{bundle.name}: launch args do not request {EXPECTED_PACKAGE!r} — "
            f"fastmcp would be missing at runtime (args: {args})"
        )
    elif spec != f"{EXPECTED_PACKAGE}=={expected_version}":
        problems.append(
            f"{bundle.name}: launch spec {spec!r} is not pinned to {expected_version} — "
            "the bundle would resolve whatever is newest on PyPI"
        )

    return problems


def main() -> int:
    """Validate every .mcpb in the given directory; return a shell exit code."""
    if len(sys.argv) != 3:  # noqa: PLR2004
        print(__doc__)
        return 2
    dist_dir, expected_version = Path(sys.argv[1]), sys.argv[2]

    bundles = sorted(dist_dir.glob("*.mcpb"))
    if not bundles:
        _fail(f"no .mcpb bundle found in {dist_dir}")
        return 1

    problems: list[str] = []
    for bundle in bundles:
        problems.extend(validate(bundle, expected_version))

    if problems:
        for problem in problems:
            _fail(problem)
        return 1

    for bundle in bundles:
        print(
            f"OK: {bundle.name} launches {EXPECTED_ENTRY_SCRIPT} from "
            f"{EXPECTED_PACKAGE}=={expected_version}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
