# Release guide

The distribution is `terminal-cells`, executable `cells`, license `0BSD`.
Production publishing requires approval and a successful TestPyPI candidate for
the same tagged commit. Nothing is uploaded by PR checks or local builds.

## Prepare and validate

Run **Prepare release** with the next version and download its patch. Apply it in
a branch, finish the changelog, and open a PR. The workflow deliberately cannot
write main, approve PRs, or publish. `terminal_cells.__version__` remains the sole
upstream version source. `release-policy.json` records Ubuntu series, repository,
and PPA revision; generated release manifests record the actual build hashes.

```sh
python -m pip install -r requirements-dev.txt -r requirements-build.txt
ruff check .
ruff format --check .
python -m unittest discover -s tests -v
python tools/manpage.py --check
python tools/preview.py
export SOURCE_DATE_EPOCH="$(git log -1 --format=%ct)"
python tools/check_reproducible.py
python -m build --no-isolation
python -m twine check --strict dist/*.whl dist/*.tar.gz
python tools/check_dist.py
python tools/release.py manifest --commit "$(git rev-parse HEAD)"
```

Release preparation regenerates the manual with the new version. If CLI options
change afterward, run `python tools/manpage.py` again; CI checks freshness.

Start with an empty `dist/`. Validation rebuilds the source archive, installs
fresh isolated wheels outside the checkout, and exercises snapshots and real
pseudo-terminal sessions. Reproducibility covers wheel bytes with identical
Python/build-tool versions, not every platform or source-tarball build.
Manually check mouse press/release, keyboard tools, help, pause, resize,
ASCII/Unicode, colorless output, and cleanup in representative Linux/macOS terminals.
Record terminal versions and results; CI is not a substitute for visual testing.

## Stage and promote

After merging, create a version tag on the reviewed commit. In **Publish**, select
that tag and `testpypi`. The workflow tests Linux/macOS, builds Ubuntu packages,
validates distributions, writes the manifest, uploads to TestPyPI, and checks an
installation from the index. TestPyPI is public and requires its own publisher.

After success, run **Publish** on the same tag with `pypi` and that candidate run
ID. Approve the production deployment after checking its tag and candidate.
The workflow requires main ancestry, successful publishing-run provenance,
matching source SHA/version, exactly the tested archive set, and matching hashes.
It downloads and promotes the existing candidate; it does not rebuild.

After the production install check passes, GitHub provenance is attached and all
Python/Ubuntu files, source-package bundles, manifest, and checksums are staged in
a draft GitHub release before it is published. Future published releases are
immutable. Inspect partial failures before retrying; index filenames cannot be
replaced and immutable assets cannot be appended later.

Trusted publishers are configured separately on TestPyPI and PyPI with owner
`kborer`, repository `cells`, workflow `publish.yml`, and matching environment
`testpypi` or `pypi`. No upload password belongs in the repository.

## Recover after an accepted upload

An index can briefly lag an accepted upload. Fresh-index installation checks
retry for a bounded period. If PyPI accepted a version but the later install
check failed, inspect the index and compare its archive digests before retrying.
Do not upload that version again or move its tag.

Run **Complete published release** on `main` with the original version tag and
successful TestPyPI candidate run ID. Its separate `github-release` approval gate
protects publication. It requires protected-main ancestry, the matching staging
commit and version, and exact PyPI filenames, metadata hashes, and downloaded
archive bytes. It assembles the original tested assets with notes from the tag,
attests them, and publishes a complete draft. It has no PyPI upload step.
An existing public immutable release cannot be appended to; inspect an existing
partial draft manually before attempting recovery.

## Ubuntu, other platforms, and recovery

See [Ubuntu packaging and PPA instructions](UBUNTU.md) and
[maintenance and recovery](MAINTENANCE.md). PPA source preparation supports a
verified archive/manifest and optional local signing; keep that key off CI.
PyPI/pipx covers Linux/macOS. Native Windows is not supported; use WSL.
Maintain the separate tap using the [Homebrew guide](HOMEBREW.md). Official
Debian/Ubuntu archive inclusion is separate from the PPA.
