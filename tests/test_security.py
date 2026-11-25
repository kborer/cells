"""Adversarial archive, release-promotion, CLI, and terminal-input boundaries."""

from pathlib import Path
import hashlib
import io
import json
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from tools.check_dist import extract_source, validate_wheel_members
from tools.release import verify_candidate, verify_manifest
from terminal_cells.interaction import read_click


class SecurityTests(unittest.TestCase):
    def test_source_rejects_traversal_links_devices_duplicates_and_oversize(self):
        for name, kind, size in [
            ("root/../../escape", tarfile.REGTYPE, 0),
            ("/escape", tarfile.REGTYPE, 0),
            ("root/link", tarfile.SYMTYPE, 0),
            ("root/device", tarfile.CHRTYPE, 0),
            ("root/huge", tarfile.REGTYPE, 101 * 1024 * 1024),
            ("root/file", tarfile.REGTYPE, 0),
        ]:
            with self.subTest(name=name, kind=kind), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                archive = root / "source.tar.gz"
                with tarfile.open(archive, "w:gz") as output:
                    member = tarfile.TarInfo(name)
                    member.type = kind
                    # Oversize header without allocating its claimed payload.
                    if size:
                        member.size = size
                        output.fileobj.write(member.tobuf())
                    else:
                        output.addfile(member, io.BytesIO())
                        if name == "root/file":
                            output.addfile(member, io.BytesIO())
                with self.assertRaises((ValueError, tarfile.ReadError)):
                    extract_source(archive, root / "out")
                self.assertFalse((root / "escape").exists())

    def test_source_cannot_follow_a_preexisting_destination_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            outside = root / "outside"
            outside.mkdir()
            destination = root / "destination"
            destination.mkdir()
            (destination / "pkg").symlink_to(outside, target_is_directory=True)
            archive = root / "source.tar.gz"
            with tarfile.open(archive, "w:gz") as output:
                member = tarfile.TarInfo("pkg/file")
                member.size = 1
                output.addfile(member, io.BytesIO(b"x"))
            with self.assertRaisesRegex(ValueError, "escapes"):
                extract_source(archive, destination)
            self.assertFalse((outside / "file").exists())

    def test_wheel_rejects_injected_startup_code_and_unsafe_members(self):
        for name in (
            "../escape",
            "/escape",
            "startup.pth",
            "sitecustomize.py",
            "terminal_cells/../../escape",
            "terminal_cells\\evil.py",
        ):
            with self.subTest(name=name), io.BytesIO() as data:
                with zipfile.ZipFile(data, "w") as archive:
                    archive.writestr(name, "malicious payload")
                    with self.assertRaises(ValueError):
                        validate_wheel_members(archive)

    def test_promotion_rejects_tampering_missing_extra_and_foreign_builds(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            files = {"terminal_cells-1.0.0.whl": b"wheel", "terminal_cells-1.0.0.tar.gz": b"source"}
            for name, data in files.items():
                (root / name).write_bytes(data)
            manifest = dict(
                version="1.0.0",
                commit="abc",
                files={n: hashlib.sha256(d).hexdigest() for n, d in files.items()},
            )
            verify_manifest(root, manifest, commit="abc", expected_version="1.0.0")
            for changed in (dict(manifest, commit="foreign"), dict(manifest, version="2.0.0")):
                with self.assertRaises(ValueError):
                    verify_manifest(root, changed, commit="abc", expected_version="1.0.0")
            (root / "extra.pth").write_text("injection")
            with self.assertRaises(ValueError):
                verify_manifest(root, manifest)
            (root / "extra.pth").unlink()
            (root / "terminal_cells-1.0.0.whl").write_bytes(b"tampered")
            with self.assertRaises(ValueError):
                verify_manifest(root, manifest)
            (root / "terminal_cells-1.0.0.whl").unlink()
            with self.assertRaises(ValueError):
                verify_manifest(root, manifest)
        run = dict(
            repository={"full_name": "kborer/cells"},
            head_sha="abc",
            conclusion="success",
            event="workflow_dispatch",
            path=".github/workflows/publish.yml",
        )
        verify_candidate(run, "kborer/cells", "abc")
        for key, value in [
            ("repository", {"full_name": "attacker/cells"}),
            ("head_sha", "other"),
            ("event", "pull_request"),
            ("conclusion", "failure"),
            ("path", ".github/workflows/other.yml"),
        ]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                verify_candidate(dict(run, **{key: value}), "kborer/cells", "abc")

    def test_release_preparation_updates_one_version_source_and_changelog(self):
        from tools import release

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "terminal_cells").mkdir()
            (root / "terminal_cells/__init__.py").write_text('__version__ = "0.1.0"\n')
            (root / "CHANGELOG.md").write_text("# Changelog\n\n## Unreleased\n\n- A fix.\n")
            with patch.object(release, "ROOT", root):
                for value in (
                    "../escape",
                    "1.0.0;echo bad",
                    "0.1.0",
                    "0.0.1",
                    "0.1.0rc1",
                    "00.2.0",
                    "0.2.0rc01",
                ):
                    with self.assertRaises(ValueError):
                        release.prepare(value)
                release.prepare("0.2.0")
                self.assertEqual(release.version(), "0.2.0")
                self.assertIn("## 0.2.0", (root / "CHANGELOG.md").read_text())
                self.assertIn("- A fix.", (root / "CHANGELOG.md").read_text())
                self.assertIn("cells 0.2.0", (root / "docs/cells.1").read_text())

    def test_release_preparation_validates_before_changing_files(self):
        from tools import release

        for changelog in (
            "# Changelog\n",
            "### Unreleased\n",
            "## Unreleased\n## Unreleased\n",
            "## Unreleased\n\n## 0.2.1\n",
        ):
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / "terminal_cells").mkdir()
                source = root / "terminal_cells/__init__.py"
                source.write_text('__version__ = "0.2.0"\n')
                (root / "CHANGELOG.md").write_text(changelog)
                with patch.object(release, "ROOT", root):
                    with self.assertRaisesRegex(ValueError, "changelog"):
                        release.prepare("0.2.1")
                self.assertEqual(source.read_text(), '__version__ = "0.2.0"\n')
                self.assertEqual((root / "CHANGELOG.md").read_text(), changelog)
                self.assertFalse((root / "docs/cells.1").exists())

    def test_malformed_mouse_events_are_ignored(self):
        class Backend:
            class error(Exception):
                pass

            BUTTON1_PRESSED = 1

            def getmouse(self):
                return self.event

        backend = Backend()
        for event in (
            (),
            (0, 1),
            None,
            (0, -1, 2, 0, 1),
            (0, 1, 2, 0, "bad"),
            (0, float("nan"), 2, 0, 1),
        ):
            backend.event = event
            self.assertIsNone(read_click(backend))

    def test_extreme_and_malformed_cli_inputs_fail_without_tracebacks(self):
        for args in [
            ("--size", "999999999999999999x24"),
            ("--seed", "9" * 5000),
            ("--at", "nan"),
            ("--at", "1e999"),
            ("--duration", "-inf"),
            ("--size", "1x1x1"),
        ]:
            result = subprocess.run(
                [sys.executable, "-m", "cells", "--snapshot", *args],
                capture_output=True,
                text=True,
                timeout=5,
            )
            self.assertEqual(result.returncode, 2)
            self.assertNotIn("Traceback", result.stderr)

    def test_diagnostics_escape_terminal_control_characters(self):
        import os

        env = dict(
            os.environ,
            TERM="\x1b]52;c;payload\x07",
            NO_COLOR="\x1b[31m",
            COLUMNS="invalid",
            LINES="-1",
        )
        result = subprocess.run(
            [sys.executable, "-m", "cells", "--diagnostics"],
            env=env,
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
        self.assertNotIn("\x1b", result.stdout)
        self.assertEqual(json.loads(result.stdout)["term"], env["TERM"])
