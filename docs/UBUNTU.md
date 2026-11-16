# Ubuntu packages

Debian-format packaging lives in `debian/`. CI builds the released upstream
0.1.0 source, verifies its SHA-256, and tests Ubuntu 24.04 and 26.04 separately.
It uses distro build tools, runs the application test suite, checks the result
with Lintian, then exercises installation, reinstallation, snapshot output,
manual-page placement, and removal. This does not establish native Windows
support or inclusion in Ubuntu's default repositories.

## Build locally

Use a disposable Ubuntu VM or container for the target release:

```sh
sudo apt-get update
sudo apt-get install build-essential debhelper dh-python pybuild-plugin-pyproject \
  python3-all python3-setuptools python3-wheel python3-hypothesis lintian curl
mkdir cells-deb
cd cells-deb
curl -fL https://github.com/kborer/cells/releases/download/v0.1.0/terminal_cells-0.1.0.tar.gz \
  -o terminal-cells_0.1.0.orig.tar.gz
echo 'b6ff320183c096f5126dca827143d0daed9d7613baaac54c147b2575645bcf46  terminal-cells_0.1.0.orig.tar.gz' | sha256sum -c
tar -xzf terminal-cells_0.1.0.orig.tar.gz
# Copy debian/ from the current Git checkout into terminal_cells-0.1.0/.
cd terminal_cells-0.1.0
series=$(. /etc/os-release; printf '%s' "$VERSION_CODENAME")
sed -i "1s/0.1.0-1) unstable/0.1.0-1~${series}1) ${series}/" debian/changelog
dpkg-buildpackage --no-sign -sa
lintian --fail-on error ../*.changes
sudo apt install ../terminal-cells_*_all.deb
sh debian/tests/smoke
```

The build applies a quilt patch to use setuptools' older license-table format
on Ubuntu 24.04. It preserves the 0BSD license and changes no runtime code.
The PyPI build continues to use modern SPDX metadata. Build dependencies come
from apt; the package build does not fetch Python dependencies from PyPI.
The package installs `/usr/bin/cells`, system Python modules, documentation,
and the `cells(1)` manual page. It has no third-party runtime Python dependencies.

## PPA publication

The current source-package changelog uses `unstable` for local validation.
Before uploading, confirm the public maintainer name/email, Launchpad account,
PPA name, and an existing OpenPGP signing key registered with Launchpad.
Do not upload the CI's unsigned `.changes` directly.

For each target Ubuntu series, start from a clean source extraction, add the
packaging, and create a distinct changelog version, such as
`0.1.0-0ubuntu1~ppa1~24.04.1` for `noble` and
`0.1.0-0ubuntu1~ppa1~26.04.1` for `resolute`. Use the confirmed maintainer identity.
Build and sign a source-only upload with `dpkg-buildpackage -S -sa -kKEYID`, then
upload its `_source.changes` using `dput ppa:OWNER/ARCHIVE ..._source.changes`.
Wait for Launchpad's build and publication to succeed, then test apt installation
from the actual PPA in a fresh target system before advertising PPA commands.
Never commit signing keys or tokens. A PPA is separate from the Ubuntu archive.

See the official [Launchpad PPA upload guide](https://ubuntu.com/docs/launchpad/user/how-to/packaging/upload-a-package-to-a-ppa/)
and [Debian Python policy](https://www.debian.org/doc/packaging-manuals/python-policy/).
