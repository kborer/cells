#!/usr/bin/env python3
"""Validate release archives and exercise clean installed copies (never upload)."""

from __future__ import annotations

import argparse
import configparser
from email.parser import BytesParser
import hashlib
import os
import re
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tarfile
import tempfile
import time
import venv
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def run(command, cwd: Path, env=None) -> str:
    result = subprocess.run(command, cwd=cwd, env=env, text=True, capture_output=True, timeout=180)
    if result.returncode:
        raise RuntimeError(
            f"Command failed: {' '.join(map(str, command))}\n{result.stdout}{result.stderr}"
        )
    return result.stdout


def validate_wheel_members(archive):
    names = archive.namelist()
    if len(names) != len(set(names)) or len(names) > 10000:
        raise ValueError("Duplicate or excessive wheel members")
    for info in archive.infolist():
        name = info.filename
        parts = PurePosixPath(name)
        if (
            parts.is_absolute()
            or ".." in parts.parts
            or "\\" in name
            or any(ord(c) < 32 for c in name)
            or info.file_size > 100 * 1024 * 1024
        ):
            raise ValueError("Unsafe wheel member")
        top = parts.parts[0] if parts.parts else ""
        allowed = (
            top in ("cells.py", "terminal_cells")
            or (top.startswith("terminal_cells-") and top.endswith(".dist-info"))
            or (
                top.startswith("terminal_cells-")
                and name.endswith(".data/data/share/man/man1/cells.1")
            )
        )
        if not allowed or name.endswith(".pth"):
            raise ValueError("Unexpected wheel payload")
    if sum(info.file_size for info in archive.infolist()) > 256 * 1024 * 1024:
        raise ValueError("Excessive wheel size")


def wheel_metadata(path: Path):
    with zipfile.ZipFile(path) as archive:
        validate_wheel_members(archive)
        names = archive.namelist()
        metadata_files = [n for n in names if n.endswith(".dist-info/METADATA")]
        if len(metadata_files) != 1 or "cells.py" not in names:
            raise ValueError(f"Invalid wheel contents: {path.name}")
        metadata = BytesParser().parsebytes(archive.read(metadata_files[0]))
        root = Path(__file__).resolve().parents[1]
        license_match = re.search(
            r'^license = "([^"]+)"$', (root / "pyproject.toml").read_text(), re.MULTILINE
        )
        if (
            not license_match
            or metadata["Name"] != "terminal-cells"
            or metadata["License-Expression"] != license_match[1]
        ):
            raise ValueError("Unexpected package name or license metadata")
        if metadata["Requires-Python"] != ">=3.10" or metadata.get_all("Requires-Dist"):
            raise ValueError("Expected Python 3.10+ and no third-party runtime dependencies")
        licenses = [n for n in names if n.endswith(".dist-info/licenses/LICENSE")]
        if len(licenses) != 1 or archive.read(licenses[0]) != (root / "LICENSE").read_bytes():
            raise ValueError("The wheel must contain the complete license text")
        manuals = [n for n in names if n.endswith("/share/man/man1/cells.1")]
        from tools.manpage import render as manual

        if len(manuals) != 1 or archive.read(manuals[0]).decode() != manual(metadata["Version"]):
            raise ValueError("The wheel must contain the current cells manual page")
        entries = configparser.ConfigParser()
        entries.read_string(
            archive.read(metadata_files[0].replace("METADATA", "entry_points.txt")).decode()
        )
        if entries.get("console_scripts", "cells", fallback="") != "terminal_cells.cli:main":
            raise ValueError("The cells console entry point is missing")
        return metadata, {
            n: archive.read(n)
            for n in names
            if n == "cells.py" or n.startswith("terminal_cells/") and n.endswith(".py")
        }


def check_checkout_payload(root: Path, module: dict[str, bytes]) -> None:
    """Reject stale builds, missing modules, and files left over from old builds."""
    current = {"cells.py": (root / "cells.py").read_bytes()}
    current.update(
        (path.relative_to(root).as_posix(), path.read_bytes())
        for path in (root / "terminal_cells").rglob("*.py")
    )
    changed = sorted(
        name for name in current.keys() | module.keys() if current.get(name) != module.get(name)
    )
    if changed:
        raise ValueError(
            "Wheel does not match the checkout; rebuild before release: " + ", ".join(changed)
        )


def extract_source(path: Path, destination: Path) -> Path:
    with tarfile.open(path, "r:gz") as archive:
        members = archive.getmembers()
        roots = set()
        seen = set()
        total = 0
        if len(members) > 10000:
            raise ValueError("Excessive source members")
        for member in members:
            parts = PurePosixPath(member.name)
            if (
                not parts.parts
                or "\\" in member.name
                or any(ord(c) < 32 for c in member.name)
                or parts.as_posix() in seen
                or member.size > 100 * 1024 * 1024
                or parts.is_absolute()
                or ".." in parts.parts
                or not (member.isfile() or member.isdir())
            ):
                raise ValueError(f"Unexpected source archive member: {member.name}")
            seen.add(parts.as_posix())
            total += member.size
            if total > 256 * 1024 * 1024:
                raise ValueError("Excessive source size")
            roots.add(parts.parts[0])
        if len(roots) != 1:
            raise ValueError("Expected one top-level source directory")
        # All paths and member types were validated above; compatible with 3.10.
        for member in members:
            target = destination.joinpath(*PurePosixPath(member.name).parts)
            if not target.resolve().is_relative_to(destination.resolve()):
                raise ValueError("Source destination escapes extraction directory")
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                source = archive.extractfile(member)
                target.write_bytes(source.read())
                target.chmod(member.mode & 0o777)
    root = destination / roots.pop()
    required = (
        "cells.py",
        "cells",
        "pyproject.toml",
        "LICENSE",
        "README.md",
        "CHANGELOG.md",
        "CONTRIBUTING.md",
        "requirements-dev.txt",
        "docs/PYPI.md",
        "docs/RELEASING.md",
        "docs/demo.gif",
        "tests/test_cells.py",
        "tools/check_dist.py",
        "tools/demo.py",
        "terminal_cells/cli.py",
        "terminal_cells/world.py",
        "terminal_cells/models.py",
        "terminal_cells/render.py",
        "terminal_cells/__init__.py",
        "requirements-build.txt",
        "tools/check_reproducible.py",
    )
    for filename in required:
        if not (root / filename).is_file():
            raise ValueError(f"Source archive is missing {filename}")
    return root


def terminal_modes(fd: int) -> list:
    """Compare settings, excluding the kernel's transient pending-input state."""
    import termios

    attributes = list(termios.tcgetattr(fd))
    # BSD/macOS can set PENDIN when curses restores canonical input. This
    # marks queued input for reprocessing, rather than a changed terminal mode.
    attributes[3] &= ~getattr(termios, "PENDIN", 0)
    return attributes


def terminal_smoke(command: Path, cwd: Path, env, interactive: bool = False) -> None:
    import fcntl
    import pty
    import select
    import struct
    import termios

    master, slave = pty.openpty()
    process = None
    try:
        before = terminal_modes(slave)
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 24, 80, 0, 0))
        process = subprocess.Popen(
            [
                str(command),
                "--ascii",
                "--seed",
                "42",
                "--duration",
                ".25",
                *(["--interactive"] if interactive else []),
            ],
            cwd=cwd,
            env=env | {"TERM": "xterm-256color"},
            stdin=slave,
            stdout=slave,
            stderr=slave,
        )
        output = bytearray()
        deadline = time.monotonic() + 10
        while process.poll() is None:
            if time.monotonic() >= deadline:
                raise RuntimeError("Installed interactive command timed out")
            if select.select([master], [], [], 0.05)[0]:
                output.extend(os.read(master, 65536))
        if process.returncode or b"Traceback" in output:
            raise RuntimeError(
                f"Installed interactive command failed: {output.decode(errors='replace')}"
            )
        if terminal_modes(slave) != before:
            raise RuntimeError("Installed command did not restore terminal settings")
    finally:
        if process is not None and process.poll() is None:
            process.kill()
            process.wait()
        os.close(master)
        os.close(slave)


def installed_smoke(wheel: Path, directory: Path, version: str) -> str:
    environment = directory / "venv"
    outside = directory / "outside-checkout"
    outside.mkdir(parents=True)
    venv.EnvBuilder(with_pip=True).create(environment)
    python = environment / "bin/python"
    command = environment / "bin/cells"
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONHOME")}
    env["PYTHONNOUSERSITE"] = "1"
    run(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--no-index",
            "--no-deps",
            str(wheel),
        ],
        outside,
        env,
    )
    if run([str(command), "--version"], outside, env).strip() != f"cells {version}":
        raise ValueError("Installed CLI and wheel versions do not match")
    installed_version = run(
        [
            str(python),
            "-I",
            "-c",
            "from importlib.metadata import version; print(version('terminal-cells'))",
        ],
        outside,
        env,
    )
    if installed_version.strip() != version:
        raise ValueError("Installed distribution metadata has the wrong version")
    help_text = run([str(command), "--help"], outside, env)
    if "--snapshot" not in help_text or "--screensaver" not in help_text:
        raise ValueError("Installed help is missing expected options")
    snapshot = run(
        [str(command), "--snapshot", "--seed", "42", "--size", "80x24", "--at", "1"], outside, env
    )
    if len(snapshot.splitlines()) != 24 or any(len(line) != 80 for line in snapshot.splitlines()):
        raise ValueError("Installed snapshot has the wrong dimensions")
    if not snapshot.isascii() or "\x1b" in snapshot:
        raise ValueError("Installed snapshot contains terminal escapes or non-ASCII text")
    import json

    report = json.loads(run([str(command), "--diagnostics"], outside, env))
    if report["version"] != version:
        raise ValueError("Installed diagnostics report the wrong version")
    terminal_smoke(command, outside, env)
    terminal_smoke(command, outside, env, interactive=True)
    return snapshot


def write_checksums(directory: Path, artifacts: list[Path]) -> None:
    checksums = "".join(
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n" for path in artifacts
    )
    (directory / "SHA256SUMS").write_text(checksums)
    print(checksums, end="")


def main() -> int:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--dist", type=Path, default=Path("dist"))
    cli.add_argument("--expected-version", help="Require this exact version (for release tags)")
    cli.add_argument(
        "--wheel-only",
        action="store_true",
        help="Check one wheel without a source rebuild (platform CI)",
    )
    args = cli.parse_args()
    directory = args.dist.resolve()
    wheels, sources = sorted(directory.glob("*.whl")), sorted(directory.glob("*.tar.gz"))
    if len(wheels) != 1 or (not args.wheel_only and len(sources) != 1):
        cli.error(
            "dist must contain exactly one wheel and one source archive; use a fresh directory"
        )
    if os.name != "posix":
        cli.error("release validation requires Linux or macOS pseudo-terminals")
    try:
        metadata, module = wheel_metadata(wheels[0])
        check_checkout_payload(Path(__file__).resolve().parents[1], module)
        version = metadata["Version"]
        if args.expected_version and version != args.expected_version:
            raise ValueError(f"Expected version {args.expected_version}, found {version}")
        print(f"Checking terminal-cells {version}", flush=True)
        with tempfile.TemporaryDirectory(prefix="cells-dist-") as temporary:
            workspace = Path(temporary)
            if args.wheel_only:
                installed_smoke(wheels[0], workspace / "installed", version)
                print("Passed: isolated wheel install and CLI/snapshot/terminal checks")
                write_checksums(directory, wheels)
                return 0
            source = extract_source(sources[0], workspace / "source")
            if any((source / name).read_bytes() != content for name, content in module.items()):
                raise ValueError("Source archive and wheel contain different application code")
            if (source / "LICENSE").read_bytes() != (
                Path(__file__).resolve().parents[1] / "LICENSE"
            ).read_bytes():
                raise ValueError("Source archive has different license text")
            print("Running the source archive test suite", flush=True)
            run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-q"], source)
            print("Rebuilding a wheel from the source archive", flush=True)
            rebuilt = workspace / "rebuilt"
            run(
                [
                    sys.executable,
                    "-m",
                    "build",
                    "--wheel",
                    "--no-isolation",
                    "--outdir",
                    str(rebuilt),
                ],
                source,
            )
            rebuilt_wheels = list(rebuilt.glob("*.whl"))
            if len(rebuilt_wheels) != 1:
                raise ValueError("Source archive did not rebuild into one wheel")
            rebuilt_metadata, rebuilt_module = wheel_metadata(rebuilt_wheels[0])
            if rebuilt_metadata["Version"] != version or rebuilt_module != module:
                raise ValueError("Rebuilt wheel differs in version or application code")
            print("Installing and exercising both wheels in fresh environments", flush=True)
            first = installed_smoke(wheels[0], workspace / "original", version)
            second = installed_smoke(rebuilt_wheels[0], workspace / "roundtrip", version)
            if first != second:
                raise ValueError("Original and rebuilt wheels produce different seeded snapshots")
        print("Passed: source tests, rebuild, two isolated installs, CLI/snapshot/terminal checks")
        write_checksums(directory, [wheels[0], sources[0]])
    except (ValueError, RuntimeError, OSError, subprocess.TimeoutExpired) as error:
        print(f"Release validation failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
