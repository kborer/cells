# Release guide

The prepared distribution name is `terminal-cells`; the command is `cells`.
Nothing is uploaded by building locally or running CI. Publishing is a separate,
manually dispatched workflow.

## One-time repository and account setup

1. The planned public home in `pyproject.toml` is `https://github.com/kborer/cells`.
   This location is confirmed; change all project URLs together if another owner
   or name is chosen. Initialize the Git repository in a normal
   writable checkout. Do not create a second README or license on GitHub.
2. The selected license is Zero-Clause BSD (`0BSD`), also used for contributions.
   No copyright assignment or separate contributor license agreement is required.
   Any future change must update `LICENSE`, the SPDX identifier in `pyproject.toml`,
   README/PyPI documentation, contribution terms, and any distribution recipes.
   Preserve any third-party notices and confirm permission for others' work.
3. Confirm the PyPI name is available. If it changes, update the project name,
   installation instructions, package validator, and publish workflow together.
   The name has not been reserved by this preparation work.
4. Create GitHub environments named `testpypi` and `pypi`. Restrict the production
   environment to version tags and require a deployment reviewer. Enable private
   vulnerability reporting and secret scanning. Protect `main` against force
   pushes/deletion and require the CI matrix before merging. Protect version
   tags against unauthorized creation, modification, or deletion. Review source,
   generated media, and any imported Git history for private data before making
   the repository public. Never commit local environments or `dist`/`build`.
5. Register a pending or existing Trusted Publisher separately on TestPyPI and
   PyPI: your GitHub owner, repository, workflow filename **publish.yml**, and
   matching environment name. No upload token needs to be stored in GitHub.

See [PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/using-a-publisher/).

## Validate a release locally

Use a development environment as described in [CONTRIBUTING.md](../CONTRIBUTING.md).

```sh
python -m pip install -r requirements-build.txt
ruff check .
ruff format --check .
python -m unittest discover -s tests -v
python tools/preview.py
export SOURCE_DATE_EPOCH="$(git log -1 --format=%ct)"
python tools/check_reproducible.py
python -m build --no-isolation
python -m twine check --strict dist/*.whl dist/*.tar.gz
python tools/check_dist.py --expected-version 0.1.0
```

Build into an empty `dist` directory; move old artifacts aside before building
another version. The validator requires exactly one wheel and one source archive.
It checks the license and entry point, rebuilds a wheel from the source archive,
and installs both wheels into separate fresh virtual environments. It exercises
the installed `cells` command from outside the checkout, including a snapshot
and a real pseudo-terminal session. It writes SHA-256 hashes to `dist/SHA256SUMS`.
Neither installation smoke test downloads runtime dependencies.
The validator also rejects a wheel whose application modules differ from the
current checkout, including omitted modules and obsolete build leftovers.
The Ubuntu/macOS matrix tests Python 3.10 through 3.14, builds a wheel on each platform and runs
`tools/check_dist.py --wheel-only` there, using a fresh installation outside
the checkout.

`terminal_cells.__version__` in `terminal_cells/__init__.py` is the single source of the package version.
To prepare another release, update that value, add release notes to
[CHANGELOG.md](../CHANGELOG.md), and rebuild. TestPyPI and PyPI do not allow a
published filename to be overwritten; use a new version for a changed upload.

## TestPyPI rehearsal

The GitHub repository may remain private during this rehearsal. TestPyPI uploads
are public: the package source and metadata will be downloadable there, even
while the GitHub repository remains private. TestPyPI accounts and publisher
registrations are separate from production PyPI.

Sign in at <https://test.pypi.org/manage/account/publishing/> and add a pending
GitHub publisher with these exact values:

| Field | Value |
| --- | --- |
| PyPI project name | `terminal-cells` |
| Owner | `kborer` |
| Repository name | `cells` |
| Workflow name | `publish.yml` |
| Environment name | `testpypi` |

The GitHub `testpypi` environment is configured. The repository is public, with
main-branch and release-tag protection enabled.
A pending publisher does not reserve the package name; only the first successful
upload creates the project. Do not register the production publisher as a
substitute for the TestPyPI registration.

After the TestPyPI Trusted Publisher is configured:

1. Open Actions → Publish → Run workflow.
2. Choose the intended branch or tag and target **testpypi** (the default).
3. The workflow runs the Ubuntu/macOS test matrix and validates its artifacts
   before uploading those same artifacts to TestPyPI.
   It then downloads the exact published version into a fresh virtual environment
   using only TestPyPI, checks `cells --version`, and renders a seeded snapshot
   from outside the source checkout. If this check fails after upload, inspect
   the failure before rerunning: the upload may already have succeeded, and its
   files cannot be overwritten.
4. Test the result in a fresh environment:

```sh
python3 -m venv /tmp/cells-testpypi
/tmp/cells-testpypi/bin/python -m pip install --no-deps --index-url https://test.pypi.org/simple/ terminal-cells==0.1.0
/tmp/cells-testpypi/bin/cells --version
/tmp/cells-testpypi/bin/cells
```

## Publish to PyPI

The TestPyPI rehearsal for version 0.1.0 passed, including all ten Linux/macOS
test jobs, archive validation, and installation of the uploaded wheel:
<https://github.com/kborer/cells/actions/runs/43959940186>.
Both publishing environments exist;
the production `pypi` environment allows deployment only from `v*` tags.
This environment restriction is separate from protection against modifying tags.

For the initial production release, sign in at
<https://pypi.org/manage/account/publishing/> and register the same pending
GitHub publisher shown above, with environment **`pypi`** instead of `testpypi`.
The project name remains `terminal-cells`, owner `kborer`, repository `cells`,
and workflow filename `publish.yml`. Production and test registrations do not
share authorization.

After reviewing the candidate and successful CI results, set the changelog's
release date and create a tag exactly matching the version, for example
`v0.1.0`. Push that tag. Manually run **Publish** on that tag with target **pypi**.
The workflow rejects a production dispatch from a branch or a mismatched tag.
It does not publish automatically when a branch, tag, or GitHub release is created.

Create a GitHub release using the tag, changelog entry, and verified wheel/source
artifacts. CI artifact downloads also include a separate checksum artifact.
The publish job downloads those checksums and verifies the exact archive set
again before upload. Attach `SHA256SUMS` to the GitHub release as well.
Verify the public installation with `pipx install terminal-cells==0.1.0`.

Before tagging, manually check at least two terminal applications on Linux and
one on macOS: mouse press/release and held clicks, keyboard tools, help, pause,
resize, ASCII/Unicode, colorless output, and terminal restoration after Ctrl-C.
Record the terminal/version and results in the release notes. Hosted and manual
checks are pending until actually run; local Linux checks do not establish them.

## Distribution follow-up

- Linux and macOS: PyPI/pipx is the initial installation route. CI includes both
  platforms, but successful hosted CI must be observed after the repository is
  pushed; local validation does not establish macOS compatibility by itself.
- Ubuntu: prepare Debian packaging and a `.deb`/Launchpad PPA after the initial
  release. A PPA is not inclusion in Ubuntu's default repositories. For eventual
  Debian/Ubuntu inclusion, follow the
  [Ubuntu new-package guide](https://ubuntu.com/project/docs/contributors/new-package/create-a-new-package/).
- macOS: a personal Homebrew tap can follow once release URLs are stable.
- Windows: document WSL first. Native Windows requires additional terminal and
  curses compatibility work and is not advertised as supported.

For Debian/Ubuntu, keep `terminal-cells` as the package name and `cells` as the
command. Packaging files and Ubuntu CI are now included; see
[the Ubuntu guide](UBUNTU.md) for building and PPA prerequisites.
Use the distro's Python interpreter with
`dh-python` and `pybuild-plugin-pyproject`, install the manual page, and declare
runtime Python dependencies through `${python3:Depends}`. Builds and tests must
use packaged build tools without fetching dependencies from the network. The
installed-package test should run `cells --version` and a seeded `--snapshot`
outside the source tree. Test installation, upgrade, removal, and `lintian` in
a clean container for each target Ubuntu release. A real maintainer contact,
final license, and released source archive are required before uploading a
signed source package to a PPA. See the
[Launchpad source-package instructions](https://ubuntu.com/docs/launchpad/user/how-to/packaging/build-deb-packages-in-launchpad/).

For a Homebrew tap, generate a formula from the final source release URL with
`brew create`, use Homebrew's Python virtualenv helpers, and record the archive
SHA-256 and final SPDX license. Declare every required Python build resource
and test the installed `cells --version` and `--snapshot` commands. Run
`brew audit --strict`, a source installation, and `brew test` on macOS before
advertising the tap. Do not fill release URLs or archive hashes with guesses.
See the [Homebrew Python guide](https://docs.brew.sh/Python-for-Formula-Authors).

## Release integrity

Actions are pinned to verified full commit IDs; Dependabot proposes updates.
Release build tools are pinned in `requirements-build.txt` and CI uses
`SOURCE_DATE_EPOCH` from the source commit. The reproducibility check builds two
wheels from separate clean source copies and compares every byte. It verifies
wheel reproducibility with the same Python/build-tool versions, not reproducible
source tarballs or all cross-version builds. Checksums cover both final archives.
Trusted Publishing provides short-lived credentials and PyPA publishing emits
attestations by default. See [PyPI attestation documentation](https://docs.pypi.org/attestations/producing-attestations/).

Before the first public upload, confirm ownership of contributions and any
third-party notices, verify the Zero-Clause BSD text and `0BSD` package metadata,
review the generated demo, and inspect
successful hosted CI. Build release artifacts from the final tested Git commit.
Building locally does not reserve the package name or publish anything.
