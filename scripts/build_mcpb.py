"""Build the .mcpb release bundle for tanabesugano.

Creates dist/tanabesugano-{version}.mcpb — a ZIP archive containing:
  manifest.json     DXT spec v0.4 manifest
  server/main.py    stdlib-only uvx launcher shim (DXT entry_point)

Deliberately does NOT bundle pyproject.toml: including it at archive root
triggers Claude Desktop's build_editable path, which fails because the full
source tree is absent. The shim + mcp_config.command=uv tool run is the
correct pattern for PyPI-distributed uv servers.
"""

from __future__ import annotations

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


def _build_manifest(version: str) -> dict:
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
                "args": [
                    "tool",
                    "run",
                    "--from",
                    f"{_PACKAGE_NAME}[mcp]=={version}",
                    _ENTRYPOINT,
                ],
            },
        },
        "tools_generated": True,
        "compatibility": {
            "claude_desktop": ">=0.10.0",
            "platforms": ["darwin", "win32", "linux"],
            "runtimes": {"python": ">=3.12"},
        },
    }


def _build_shim(version: str) -> str:
    """Return a stdlib-only launcher shim with the version baked in."""
    return textwrap.dedent(f"""\
        \"\"\"TanabeSugano — uvx launcher shim.

        Serves as the DXT entry_point. The preferred launch path is
        mcp_config.command (uv tool run) declared in manifest.json; this file
        acts as a direct fallback when run via ``uv run server/main.py``.
        \"\"\"

        from __future__ import annotations

        import os

        _PACKAGE = "{_PACKAGE_NAME}[mcp]"
        _VERSION = "{version}"
        _ENTRYPOINT = "{_ENTRYPOINT}"


        def main() -> None:
            spec = f"{{_PACKAGE}}=={{_VERSION}}"
            os.execvp("uv", ["uv", "tool", "run", "--from", spec, _ENTRYPOINT])


        if __name__ == "__main__":
            main()
        """)


def main() -> None:
    """Write dist/tanabesugano-{version}.mcpb."""
    root = Path(__file__).parent.parent
    version = _read_version(root)
    manifest = _build_manifest(version)
    shim = _build_shim(version)

    dist = root / "dist"
    dist.mkdir(exist_ok=True)

    mcpb_path = dist / f"{_PACKAGE_NAME}-{version}.mcpb"
    with zipfile.ZipFile(mcpb_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest, indent=2))
        zf.writestr("server/main.py", shim)

    print(f"Built {mcpb_path}")


if __name__ == "__main__":
    main()
