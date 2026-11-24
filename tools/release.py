#!/usr/bin/env python3
"""Prepare releases and verify promotions; never stores upload credentials."""

from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
from email.utils import format_datetime
import gzip
import os
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def version(root=None):
    root = ROOT if root is None else root
    text = (root / "terminal_cells/__init__.py").read_text()
    return re.search(r'^__version__ = [\'"]([^\'"]+)', text, re.M)[1]


def policy():
    config = json.loads((ROOT / "release-policy.json").read_text())
    for field in ("repository", "ppa"):
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", config[field]):
            raise ValueError("Invalid repository or PPA identity")
    if config["distribution"] != "terminal-cells" or not re.fullmatch(
        r"[1-9][0-9]*ppa[1-9][0-9]*", config["ppa_revision"]
    ):
        raise ValueError("Invalid distribution or PPA revision")
    for release, series in config["ubuntu"].items():
        if not re.fullmatch(r"[0-9]{2}\.[0-9]{2}", release) or not re.fullmatch(
            r"[a-z][a-z0-9]+", series
        ):
            raise ValueError("Invalid Ubuntu release or series")
    return config


def safe_name(name):
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.+~-]*", name):
        raise ValueError("Unsafe release filename")
    return name


def verify_manifest(directory, manifest, *, commit=None, expected_version=None):
    if commit is not None and manifest["commit"] != commit:
        raise ValueError("Candidate commit does not match release tag")
    if expected_version is not None and manifest["version"] != expected_version:
        raise ValueError("Candidate version does not match release tag")
    files = manifest["files"]
    if (
        len(files) != 2
        or sum(name.endswith(".whl") for name in files) != 1
        or sum(name.endswith(".tar.gz") for name in files) != 1
    ):
        raise ValueError("Expected one wheel and one source archive")
    actual = {p.name for p in directory.iterdir() if p.name != "SHA256SUMS"}
    if actual != set(files):
        raise ValueError("Unexpected or missing release files")
    for name, digest in files.items():
        safe_name(name)
        if not re.fullmatch(r"[a-f0-9]{64}", digest) or (directory / name).is_symlink():
            raise ValueError("Invalid release digest or symlink")
        if hashlib.sha256((directory / name).read_bytes()).hexdigest() != digest:
            raise ValueError("Release checksum mismatch")


def source_epoch():
    value = os.environ.get("SOURCE_DATE_EPOCH")
    if value is None:
        value = (
            subprocess.check_output(["git", "log", "-1", "--format=%ct"], cwd=ROOT).decode().strip()
        )
    if not value.isdecimal():
        raise ValueError("Invalid source timestamp")
    return int(value)


def write_manifest(directory, commit):
    files = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in directory.iterdir()
        if p.name.endswith((".whl", ".tar.gz"))
    }
    manifest = {
        "version": version(),
        "commit": commit,
        "files": files,
        "policy": policy(),
        "source_date_epoch": source_epoch(),
    }
    verify_manifest(directory, manifest)
    (directory.parent / "release-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def verify_candidate(run, repository, commit):
    if (
        run.get("repository", {}).get("full_name") != repository
        or run.get("head_sha") != commit
        or run.get("conclusion") != "success"
        or run.get("event") != "workflow_dispatch"
        or run.get("path") != ".github/workflows/publish.yml"
    ):
        raise ValueError(
            "Candidate must be a successful publishing run for this repository and commit"
        )


def prepare(new_version):
    def version_key(value):
        match = re.fullmatch(
            r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:(a|b|rc)(0|[1-9][0-9]*))?", value
        )
        if not match:
            raise ValueError("Use a three-part version, optionally followed by aN, bN or rcN")
        major, minor, patch, stage, number = match.groups()
        return (
            int(major),
            int(minor),
            int(patch),
            {"a": 0, "b": 1, "rc": 2, None: 3}[stage],
            int(number or 0),
        )

    if version_key(new_version) <= version_key(version()):
        raise ValueError("The next release version must increase")
    version_path = ROOT / "terminal_cells/__init__.py"
    changelog_path = ROOT / "CHANGELOG.md"
    changelog = changelog_path.read_text()
    if len(re.findall(r"^## Unreleased$", changelog, re.M)) != 1:
        raise ValueError("Expected exactly one '## Unreleased' changelog heading")
    if re.search(rf"^## {re.escape(new_version)}(?:\s|$)", changelog, re.M):
        raise ValueError("The new version already has a changelog entry")
    source, count = re.subn(
        r'^__version__ = [\'"][^\'"]+[\'"]',
        f'__version__ = "{new_version}"',
        version_path.read_text(),
        flags=re.M,
    )
    if count != 1:
        raise ValueError("Expected exactly one upstream version declaration")
    from tools.manpage import render as manual

    # Validate and generate everything before changing any release source file.
    manual_content = manual(new_version)
    changelog = changelog.replace(
        "## Unreleased\n",
        f"## Unreleased\n\n## {new_version} — {date.today().isoformat()}\n",
        1,
    )
    manual_path = ROOT / "docs/cells.1"
    manual_path.parent.mkdir(parents=True, exist_ok=True)
    version_path.write_text(source)
    changelog_path.write_text(changelog)
    manual_path.write_text(manual_content)


def deb_source(output, series, upstream=None):
    """Use a verified release sdist, or tracked checkout files for PR builds."""
    config = policy()
    if series not in config["ubuntu"].values():
        raise ValueError("Unsupported Ubuntu series")
    output.mkdir(parents=True, exist_ok=True)
    v = version()
    orig = output / f"terminal-cells_{v}.orig.tar.gz"
    tree = output / f"terminal-cells-{v}"
    if tree.exists() or orig.exists():
        raise ValueError("Use an empty output directory")
    epoch = source_epoch()
    if upstream:
        from tools.check_dist import extract_source

        archive, manifest_path = upstream
        manifest = json.loads(manifest_path.read_text())
        epoch = manifest["source_date_epoch"]
        verify_manifest(archive.parent, manifest, expected_version=v)
        if archive.name not in manifest["files"] or not archive.name.endswith(".tar.gz"):
            raise ValueError("Expected the manifest source archive")
        shutil.copyfile(archive, orig)
        with tempfile.TemporaryDirectory() as temporary:
            source = extract_source(orig, Path(temporary))
            shutil.copytree(source, tree)
    else:
        tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\0")
        with (
            orig.open("wb") as raw,
            gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=epoch) as compressed,
            tarfile.open(fileobj=compressed, mode="w") as archive,
        ):
            for name in sorted(tracked):
                if name and not name.startswith("debian/"):
                    info = archive.gettarinfo(
                        str(ROOT / name), arcname=f"terminal-cells-{v}/{name}"
                    )
                    info.mtime, info.uid, info.gid, info.uname, info.gname = epoch, 0, 0, "", ""
                    with (ROOT / name).open("rb") as payload:
                        archive.addfile(info, payload)
        with tempfile.TemporaryDirectory() as temporary:
            from tools.check_dist import extract_source

            source = extract_source(orig, Path(temporary))
            shutil.copytree(source, tree)
    tracked_debian = (
        subprocess.check_output(["git", "ls-files", "-z", "debian"], cwd=ROOT).decode().split("\0")
    )
    for name in tracked_debian:
        if name:
            destination = tree / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, destination)
    (tree / "debian/changelog").write_text(
        f"terminal-cells ({v}-1~{series}1) {series}; urgency=medium\n\n"
        "  * Package the selected upstream release.\n\n"
        f" -- cells contributors <640862+kborer@users.noreply.github.com>  {format_datetime(datetime.fromtimestamp(epoch, timezone.utc))}\n"
    )
    print(tree)


def assemble(
    directory=Path("dist"),
    manifest_path=Path("release-manifest.json"),
    ubuntu=Path("ubuntu"),
    output=Path("release-assets"),
):
    manifest = json.loads(manifest_path.read_text())
    verify_manifest(directory, manifest, expected_version=version())
    output.mkdir(exist_ok=False)
    for name in manifest["files"]:
        shutil.copyfile(directory / name, output / name)
    shutil.copyfile(manifest_path, output / "release-manifest.json")
    for release in policy()["ubuntu"]:
        folder = ubuntu / f"ubuntu-{release}-packages"
        entries = [line.split() for line in (folder / "SHA256SUMS").read_text().splitlines()]
        names = [safe_name(name) for digest, name in entries]
        if len(set(names)) != len(names) or set(names) != {
            p.name for p in folder.iterdir() if p.name != "SHA256SUMS"
        }:
            raise ValueError("Unexpected Ubuntu artifact set")
        for digest, name in entries:
            if (folder / name).is_symlink() or hashlib.sha256(
                (folder / name).read_bytes()
            ).hexdigest() != digest:
                raise ValueError("Ubuntu artifact checksum mismatch")
        binaries = list(folder.glob("*.deb"))
        if len(binaries) != 1:
            raise ValueError("Expected one Ubuntu binary package")
        shutil.copyfile(binaries[0], output / binaries[0].name.replace("~", "."))
        with tarfile.open(output / f"ubuntu-{release}-source.tar.gz", "w:gz") as archive:
            for name in names:
                if not name.endswith(".deb"):
                    archive.add(folder / name, arcname=name, recursive=False)
    (output / "SHA256SUMS").write_text(
        "".join(
            f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n"
            for p in sorted(output.iterdir())
        )
    )
    changelog = (ROOT / "CHANGELOG.md").read_text()
    match = re.search(
        rf"^## {re.escape(version())}[^\n]*\n(.*?)(?=^## |\Z)", changelog, re.M | re.S
    )
    if not match:
        raise ValueError("Release notes are missing")
    Path("release-notes.md").write_text(match[1].strip() + "\n")


def ppa_source(output, series, archive, manifest, maintainer, sign_key=None):
    if not re.fullmatch(r"[^<>\n]+ <[^<>\n ]+@[^<>\n ]+>", maintainer):
        raise ValueError("Provide a public Name <email> maintainer identity")
    if sign_key and not re.fullmatch(r"[A-Fa-f0-9]{40}", sign_key):
        raise ValueError("Use the full signing fingerprint")
    deb_source(output, series, (archive, manifest))
    tree = output / f"terminal-cells-{version()}"
    p = policy()
    release = next(v for v, s in p["ubuntu"].items() if s == series)
    package_version = f"{version()}-{p['ppa_revision']}~{release}.1"
    changelog = tree / "debian/changelog"
    text = changelog.read_text().replace(f"{version()}-1~{series}1", package_version)
    text = text.replace("cells contributors <640862+kborer@users.noreply.github.com>", maintainer)
    changelog.write_text(text)
    subprocess.run(
        ["dpkg-buildpackage", "-S", "-nc", "-d", "-us", "-uc", "-sa"], cwd=tree, check=True
    )
    changes = output / f"terminal-cells_{package_version}_source.changes"
    if sign_key:
        subprocess.run(["debsign", f"-k{sign_key}", str(changes.resolve())], check=True)
    print(f"Review the source upload: {changes}")


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    sub = cli.add_subparsers(dest="command", required=True)
    sub.add_parser("version")
    sub.add_parser("assemble")
    p = sub.add_parser("prepare")
    p.add_argument("version")
    p = sub.add_parser("manifest")
    p.add_argument("--dist", type=Path, default=Path("dist"))
    p.add_argument("--commit", required=True)
    p = sub.add_parser("verify")
    p.add_argument("--dist", type=Path, default=Path("dist"))
    p.add_argument("--manifest", type=Path, default=Path("release-manifest.json"))
    p.add_argument("--commit")
    p = sub.add_parser("candidate")
    p.add_argument("run", type=Path)
    p.add_argument("--commit", required=True)
    p = sub.add_parser("deb-source")
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--series", required=True)
    p.add_argument("--archive", type=Path)
    p.add_argument("--manifest", type=Path)
    p = sub.add_parser("ppa-source")
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--series", required=True)
    p.add_argument("--archive", type=Path, required=True)
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--maintainer", required=True)
    p.add_argument("--sign-key")
    args = cli.parse_args()
    if args.command == "assemble":
        assemble()
    elif args.command == "ppa-source":
        ppa_source(
            args.output.resolve(),
            args.series,
            args.archive.resolve(),
            args.manifest.resolve(),
            args.maintainer,
            args.sign_key,
        )
    elif args.command == "version":
        print(version())
    elif args.command == "prepare":
        prepare(args.version)
    elif args.command == "manifest":
        write_manifest(args.dist, args.commit)
    elif args.command == "verify":
        verify_manifest(
            args.dist,
            json.loads(args.manifest.read_text()),
            commit=args.commit,
            expected_version=version(),
        )
    elif args.command == "candidate":
        verify_candidate(json.loads(args.run.read_text()), policy()["repository"], args.commit)
    elif args.command == "deb-source":
        if bool(args.archive) != bool(args.manifest):
            cli.error("--archive and --manifest must be supplied together")
        deb_source(
            args.output, args.series, (args.archive, args.manifest) if args.archive else None
        )


if __name__ == "__main__":
    import sys

    sys.path.insert(0, str(ROOT))
    main()
