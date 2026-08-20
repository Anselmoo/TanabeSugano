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

What "correct" means is read from ``pyproject.toml`` rather than hardcoded
here: the package name, the console script whose target lives in the ``mcp``
package, and the extra that provides the server dependencies. The workflow
still passes those values to the bundle builder explicitly, so this stays a
genuine two-source cross-check — if the console script is renamed in
``pyproject.toml`` and the workflow is not updated (or vice versa), the two
disagree and validation fails.

Usage::

    python scripts/validate_mcpb.py <dist-dir> <expected-version>
"""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
import zipfile

from pathlib import Path


REQUIRED_MEMBERS = ("manifest.json",)
SERVER_MODULE_MARKER = ".mcp."


class ExpectationError(RuntimeError):
    """Raised when pyproject.toml does not describe an MCP server surface."""


def read_expectations(pyproject: Path) -> tuple[str, str]:
    """Return (package_spec_with_extra, entry_script) derived from pyproject.toml.

    The entry script is the console script whose target module lives inside the
    ``mcp`` subpackage — the only script that speaks the MCP protocol.
    """
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    project = data["project"]
    name = project["name"]

    scripts = project.get("scripts", {})
    candidates = [script for script, target in scripts.items() if SERVER_MODULE_MARKER in target]
    if len(candidates) != 1:
        msg = (
            f"expected exactly one console script targeting the mcp package in "
            f"{pyproject}; found {candidates or 'none'} among {sorted(scripts)}"
        )
        raise ExpectationError(msg)

    extras = project.get("optional-dependencies", {})
    if "mcp" not in extras:
        msg = f"{pyproject} declares no 'mcp' extra; extras are {sorted(extras)}"
        raise ExpectationError(msg)

    return f"{name}[mcp]", candidates[0]


def _fail(message: str) -> None:
    print(f"::error::{message}")
    print(f"FAIL: {message}")


def validate(
    bundle: Path,
    expected_version: str,
    package_spec: str,
    entry_script: str,
) -> list[str]:
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
            f"{bundle.name}: manifest version {version!r} != expected {expected_version!r}",
        )

    args = manifest.get("server", {}).get("mcp_config", {}).get("args", [])
    if not args:
        problems.append(f"{bundle.name}: manifest has no server.mcp_config.args")
        return problems

    # The entry point is the final argv element: `uv tool run --from <spec> <entry>`.
    if args[-1] != entry_script:
        problems.append(
            f"{bundle.name}: launch entry point is {args[-1]!r}, expected "
            f"{entry_script!r} — the bundle would start the CLI, not the MCP server",
        )

    spec = next((a for a in args if a.startswith(package_spec)), None)
    if spec is None:
        problems.append(
            f"{bundle.name}: launch args do not request {package_spec!r} — "
            f"fastmcp would be missing at runtime (args: {args})",
        )
    elif spec != f"{package_spec}=={expected_version}":
        problems.append(
            f"{bundle.name}: launch spec {spec!r} is not pinned to {expected_version} — "
            "the bundle would resolve whatever is newest on PyPI",
        )

    return problems


def main() -> int:
    """Validate every .mcpb in the given directory; return a shell exit code."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dist", type=Path, help="directory holding the built .mcpb")
    parser.add_argument("expected_version", help="PEP 440 version the bundle must pin")
    parser.add_argument(
        "--pyproject",
        type=Path,
        default=Path("pyproject.toml"),
        help="source of truth for the package name, entry script and extra",
    )
    args = parser.parse_args()

    try:
        package_spec, entry_script = read_expectations(args.pyproject)
    except (OSError, KeyError, ExpectationError) as exc:
        _fail(f"cannot derive expectations from {args.pyproject}: {exc}")
        return 1

    bundles = sorted(args.dist.glob("*.mcpb"))
    if not bundles:
        _fail(f"no .mcpb bundle found in {args.dist}")
        return 1

    problems: list[str] = []
    for bundle in bundles:
        problems.extend(validate(bundle, args.expected_version, package_spec, entry_script))

    if problems:
        for problem in problems:
            _fail(problem)
        return 1

    for bundle in bundles:
        print(
            f"OK: {bundle.name} launches {entry_script} from "
            f"{package_spec}=={args.expected_version}",
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
