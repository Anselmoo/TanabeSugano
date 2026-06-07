"""Build the .mcpb release bundle for tanabesugano.

Creates dist/tanabesugano-{version}.mcpb (release) or
dist/tanabesugano-{version}-dev.mcpb (dev) — a ZIP archive containing:
  manifest.json     DXT spec v0.4 manifest
  server/main.py    stdlib-only uvx launcher shim (DXT entry_point)

Modes
-----
Release (default)  Uses the PyPI-published package.  Run after `uv publish`.
  python scripts/build_mcpb.py

Dev (--dev)        Uses the local source tree.  Use when the package has not
  python scripts/build_mcpb.py --dev   been published yet or for local testing.

Deliberately does NOT bundle pyproject.toml: including it at archive root
triggers Claude Desktop's build_editable path, which fails because the full
source tree is absent. The shim + mcp_config.command=uv tool run is the
correct pattern for PyPI-distributed uv servers.

Both modes pin the fastmcp version resolved in uv.lock to prevent version-drift
crashes in Claude Desktop when a new fastmcp release is published after the
.mcpb is built.
"""

from __future__ import annotations

import argparse
import json
import textwrap
import tomllib
import zipfile

from pathlib import Path


_PACKAGE_NAME = "tanabesugano"
_ENTRYPOINT = "tanabesugano-mcp"


def _read_version(root: Path) -> str:
    with (root / "pyproject.toml").open("rb") as fh:
        data = tomllib.load(fh)
    return data["project"]["version"]


def _read_fastmcp_version(root: Path) -> str:
    """Return the fastmcp version pinned in uv.lock."""
    with (root / "uv.lock").open("rb") as fh:
        data = tomllib.load(fh)
    for pkg in data.get("package", []):
        if pkg.get("name") == "fastmcp":
            return pkg["version"]
    msg = "fastmcp not found in uv.lock — run `uv sync --extra mcp` first"
    raise RuntimeError(msg)


def _read_numpy_version(root: Path) -> str:
    """Return the numpy version pinned in uv.lock."""
    with (root / "uv.lock").open("rb") as fh:
        data = tomllib.load(fh)
    for pkg in data.get("package", []):
        if pkg.get("name") == "numpy":
            return pkg["version"]
    msg = "numpy not found in uv.lock — run `uv sync` first"
    raise RuntimeError(msg)


def _build_manifest(
    version: str,
    fastmcp_version: str,
    numpy_version: str,
    dev_path: str | None = None,
) -> dict:
    # Release mode launches the PyPI-published package via `uv tool run`:
    # immutable version pin → cached install is always correct.
    # Dev mode launches via `uv run --project <local-source>`: that uses
    # the project's editable venv, so source edits propagate without a
    # cache-invalidation dance (`uv tool run --from <local-path>` installs
    # to a hashed cache that silently keeps the stale build between edits;
    # `--reinstall-package` is documented-ignored by `uv tool run`).
    if dev_path:
        mcp_args = [
            "run",
            "--project",
            dev_path,
            "--extra",
            "mcp",
            _ENTRYPOINT,
        ]
    else:
        mcp_args = [
            "tool",
            "run",
            "--from",
            f"{_PACKAGE_NAME}[mcp]=={version}",
            "--with",
            f"fastmcp[apps]=={fastmcp_version}",
            "--with",
            f"numpy=={numpy_version}",
            _ENTRYPOINT,
        ]

    return {
        "manifest_version": "0.4",
        "name": _PACKAGE_NAME,
        "display_name": "TanabeSugano",
        "version": version,
        "description": (
            "Tanabe-Sugano and energy-correlation diagram solver for d2-d8 "
            "transition-metal complexes, exposed via the Model Context Protocol."
        ),
        "author": {
            "name": "Anselm Hahn",
            "email": "anselm.hahn@gmail.com",
            "url": "https://github.com/Anselmoo/TanabeSugano",
        },
        "repository": {
            "type": "git",
            "url": "https://github.com/Anselmoo/TanabeSugano",
        },
        "homepage": "https://pypi.org/project/TanabeSugano",
        "license": "MIT",
        "keywords": [
            "tanabe-sugano",
            "energy-correlation",
            "ligand-field",
            "transition-metal",
            "mcp",
        ],
        "server": {
            "type": "uv",
            "entry_point": "server/main.py",
            "mcp_config": {
                "command": "uv",
                "args": mcp_args,
            },
        },
        "tools_generated": True,
        "compatibility": {
            "claude_desktop": ">=0.10.0",
            "platforms": ["darwin", "win32", "linux"],
            "runtimes": {"python": ">=3.12"},
        },
    }


def _build_shim(
    version: str,
    fastmcp_version: str,
    numpy_version: str,
    dev_path: str | None = None,
) -> str:
    """Return a stdlib-only launcher shim with the version and dependency pins baked in."""
    if dev_path:
        # Dev mode runs the local source through the project's editable venv
        # so source edits always propagate. No fastmcp/numpy --with pins —
        # pyproject.toml declares them with the same constraints.
        exec_args = f'["uv", "run", "--project", "{dev_path}", "--extra", "mcp", "{_ENTRYPOINT}"]'
    else:
        # Release mode runs the immutable PyPI version with explicit pins.
        exec_args = (
            "["
            '"uv", "tool", "run", '
            f'"--from", "{_PACKAGE_NAME}[mcp]=={version}", '
            f'"--with", "fastmcp[apps]=={fastmcp_version}", '
            f'"--with", "numpy=={numpy_version}", '
            f'"{_ENTRYPOINT}"'
            "]"
        )

    return textwrap.dedent(f"""\
        \"\"\"TanabeSugano — uvx launcher shim.

        Serves as the DXT entry_point. The preferred launch path is
        mcp_config.command (uv tool run / uv run) declared in manifest.json;
        this file acts as a direct fallback when run via
        ``uv run server/main.py``.
        \"\"\"

        from __future__ import annotations

        import os


        def main() -> None:
            os.execvp("uv", {exec_args})


        if __name__ == "__main__":
            main()
        """)


def main() -> None:
    """Write dist/tanabesugano-{{version}}[-dev].mcpb."""
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--dev",
        action="store_true",
        help="Build a dev bundle pointing to the local source tree (for pre-publish testing).",
    )
    args = parser.parse_args()

    root = Path(__file__).parent.parent
    version = _read_version(root)
    fastmcp_version = _read_fastmcp_version(root)
    numpy_version = _read_numpy_version(root)
    dev_path = str(root) if args.dev else None

    manifest = _build_manifest(version, fastmcp_version, numpy_version, dev_path)
    shim = _build_shim(version, fastmcp_version, numpy_version, dev_path)

    dist = root / "dist"
    dist.mkdir(exist_ok=True)

    suffix = "-dev" if args.dev else ""
    mcpb_path = dist / f"{_PACKAGE_NAME}-{version}{suffix}.mcpb"
    with zipfile.ZipFile(mcpb_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest, indent=2))
        zf.writestr("server/main.py", shim)

    mode = "dev (local source)" if args.dev else "release (PyPI)"
    print(f"Built {mcpb_path}  [{mode}, fastmcp=={fastmcp_version}, numpy=={numpy_version}]")


if __name__ == "__main__":
    main()
