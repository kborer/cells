"""Prevent publishing stale or incomplete build payloads."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.check_dist import check_checkout_payload, terminal_modes


class PackagingTests(unittest.TestCase):
    def test_checked_in_manual_is_fresh(self):
        from tools.manpage import render

        manual = Path(__file__).resolve().parents[1] / "docs/cells.1"
        if not manual.is_file():
            self.skipTest("manual is not present in this checkout")
        self.assertEqual(manual.read_text(), render())

    def test_terminal_modes_ignore_pending_input_but_detect_changed_echo(self):
        try:
            import termios
        except ImportError:
            self.skipTest("requires POSIX terminal settings")
        baseline = [0, 0, 0, termios.ECHO | termios.ICANON, 0, 0, []]
        pending = list(baseline)
        pending[3] |= 0x20000000
        with (
            patch.object(termios, "PENDIN", 0x20000000, create=True),
            patch.object(termios, "tcgetattr", return_value=pending),
        ):
            self.assertEqual(terminal_modes(0), baseline)
            self.assertNotEqual(pending, baseline, "normalization must not mutate the saved state")
            pending[3] &= ~termios.ECHO
            self.assertNotEqual(
                terminal_modes(0), baseline, "echo restoration must still be checked"
            )

    def test_release_payload_must_match_all_checkout_modules(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "terminal_cells").mkdir()
            (root / "cells.py").write_bytes(b"entry point\n")
            (root / "terminal_cells" / "interaction.py").write_bytes(b"new footer\n")
            payload = {
                "cells.py": b"entry point\n",
                "terminal_cells/interaction.py": b"new footer\n",
            }
            check_checkout_payload(root, payload)
            for broken in (
                payload | {"terminal_cells/interaction.py": b"old toolbar\n"},
                {"cells.py": b"entry point\n"},
                payload | {"terminal_cells/deleted.py": b"obsolete module\n"},
            ):
                with self.subTest(files=tuple(broken)):
                    with self.assertRaisesRegex(ValueError, "rebuild before release"):
                        check_checkout_payload(root, broken)


if __name__ == "__main__":
    unittest.main()
