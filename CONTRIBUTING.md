# Contributing to TanabeSugano
---

👍🎉 First off, thanks for taking the time to contribute! 🎉👍

## Development

```bash
uv sync --all-groups --extra mcp   # Python >= 3.12
uv run pytest -vv                  # full suite
uv run pytest -vv -m mcp           # MCP layer only
uv run pre-commit run --all-files  # what CI's lint job runs
```

## Cutting a release

Releases are tag-driven. Pushing a `v*` tag runs the whole pipeline in
`.github/workflows/cicd.yml`: build → `.mcpb` bundle → SBOM → PyPI → GitHub Release
(body *and* all assets in one atomic job) → post-release bundle smoke test.

1. `uv run rrt bump <major|minor|patch|alpha|beta|rc|X.Y.Z>` on a release branch.
   This updates `pyproject.toml`, `src/tanabesugano/__init__.py` and `CITATION.cff`,
   and moves `[Unreleased]` into a versioned `CHANGELOG.md` heading.
2. **Verify the release body resolves before pushing anything:**
   ```bash
   uv run rrt release notes --version <the version rrt just wrote>
   ```
   This must exit 0 with a non-empty body. Because `changelog_workflow = "incremental"`
   empties `[Unreleased]` at bump time, a bare `rrt release notes` always exits 1 — the
   release job targets the tag's own section for exactly this reason.
3. Update `date-released:` in `CITATION.cff` to the release date. `rrt` tracks the
   `version:` field there, but has no notion of a date, so this one line is manual.
   (`url:` is deliberately version-independent, and `doi:` points at the Zenodo record
   — change it only if you mint a new one.)

   Note: `CITATION.cff` gets exactly **one** `[[tool.rrt.version_targets]]` entry.
   `rrt` reads every target from disk before writing any of them, so two targets on
   the same file silently lose one update — and report success for both.
4. Open a PR, get it reviewed, merge.
5. Push the tag: `git tag v<X.Y.Z> && git push origin v<X.Y.Z>`.

### Pre-releases and the two version spellings

`rrt bump alpha|beta|rc` writes **SemVer-style** pre-releases — `1.8.0-alpha.1` — into
`pyproject.toml` and the git tag. The wheel uv builds, the version on PyPI, and the
version a `.mcpb` bundle pins are all the **PEP 440 normalisation** of that string:
`1.8.0a1`. Both spellings denote the same release, but they are not interchangeable.

`scripts/release_version.py` is the single place that resolves this. It parses the tag
with `packaging.version.Version` rather than pattern-matching it — a regex on the raw
string reads `1.8.0-alpha.1` as a *stable* release — and it fails the build when a tag
disagrees with the artifact actually built (i.e. the bump never landed on the tagged
commit). Both the `mcpb` and `release` jobs call it, so pre-release detection and the
bundle's version pin can never drift apart.

Cutting an `alpha` first is the cheapest way to prove the whole pipeline before a real
release: it exercises PyPI publish, Release creation, asset attachment and the bundle
smoke test, while being marked as a prerelease and never becoming the default `pip
install` target.

### If a tag pipeline fails

`publish-pypi` uses `skip-existing: true`, so re-running a failed tag run is safe — it
will not 400 on the already-uploaded files.
