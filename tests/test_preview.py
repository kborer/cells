"""Preview sampling must stay aligned after drawing modules are split."""

import importlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import preview


class HalfBlockPreviewTests(unittest.TestCase):
    def test_sampling_is_aligned_and_globals_restored_on_success_and_failure(self):
        modules = [
            importlib.import_module("terminal_cells." + name)
            for name in ("render", "frame", "geometry", "event_render")
        ]
        originals = [module.ASPECT for module in modules]
        original_render = preview.render
        calls = []

        def inspect(world, unicode):
            calls.append([module.ASPECT for module in modules])
            return original_render(world, unicode)

        with tempfile.TemporaryDirectory() as directory:
            with (
                patch.object(preview, "render", side_effect=inspect),
                patch.object(preview, "atlas") as atlas,
            ):
                preview.half_block_preview(Path(directory))
            panels = atlas.call_args.args[2]
            self.assertEqual([(f.width, f.height) for _, f in panels], [(120, 36)] * 2)
            self.assertEqual(calls, [[1] * 4, originals])
            self.assertEqual([module.ASPECT for module in modules], originals)
            self.assertTrue(set(panels[1][1].plain()) <= set(" ▀▄█\n"))
            with patch.object(preview, "render", side_effect=RuntimeError("drawing failed")):
                with self.assertRaisesRegex(RuntimeError, "drawing failed"):
                    preview.half_block_preview(Path(directory))
            self.assertEqual([module.ASPECT for module in modules], originals)
