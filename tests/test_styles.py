"""Presentation selection must preserve the shared simulation and classic output."""

import copy
from contextlib import redirect_stdout
import io
import pickle
import unittest
from unittest.mock import patch

from terminal_cells import World, render
from terminal_cells.cli import diagnostics, main, parser
from terminal_cells.frame import Frame, Ink
from terminal_cells.styles import DEFAULT_STYLE, RenderOptions, get_style


class StyleTests(unittest.TestCase):
    def test_classic_matches_legacy_renderer_without_changing_world(self):
        world = World(100, 32, 42)
        for steps in (0, 120, 900):
            for _ in range(steps):
                world.update()
            before = copy.deepcopy(world.__dict__)
            rng = world.rng.getstate()
            for unicode in (False, True):
                for fill in (False, True):
                    with self.subTest(time=world.time, unicode=unicode, fill=fill):
                        frame = get_style().render(world, RenderOptions(unicode, fill))
                        expected = render(world, unicode, fill)
                        self.assertEqual(frame.pixels, expected.pixels)
                        self.assertEqual((frame.width, frame.height), (100, 32))
                        # Repeated rendering is stable, including textured backgrounds.
                        self.assertEqual(
                            frame.pixels,
                            get_style().render(world, RenderOptions(unicode, fill)).pixels,
                        )
            # Pickle compares the complete object graph without requiring entity
            # identity equality on the deep copy; RNG is also checked explicitly.
            self.assertEqual(pickle.dumps(world.__dict__), pickle.dumps(before))
            self.assertEqual(world.rng.getstate(), rng)

    def test_default_and_explicit_classic_snapshots_are_identical(self):
        outputs = []
        for extra in ([], ["--style", "classic"]):
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(main(["--snapshot", "--seed", "42", "--at", "0", *extra]), 0)
            outputs.append(output.getvalue())
        self.assertEqual(outputs[0], outputs[1])
        self.assertTrue(outputs[0].isascii())

    def test_snapshot_dispatches_to_selected_style_with_plain_options(self):
        class ExampleStyle:
            name = "example"

            def render(self, world, options):
                self.options = options
                frame = Frame(round(world.width), round(world.height / 2))
                frame.text(0, 0, "example", Ink.TEXT)
                return frame

        style = ExampleStyle()
        output = io.StringIO()
        with (
            patch("terminal_cells.cli.STYLES", {"example": style}),
            patch("terminal_cells.styles.STYLES", {"example": style}),
            redirect_stdout(output),
        ):
            main(["--snapshot", "--style", "example", "--at", "0", "--unicode", "always", "--fill"])
        self.assertTrue(output.getvalue().startswith("example"))
        self.assertEqual(style.options, RenderOptions())

    def test_unknown_styles_are_rejected_and_diagnostics_report_selection(self):
        self.assertEqual(parser().parse_args([]).style, DEFAULT_STYLE)
        self.assertEqual(diagnostics(parser().parse_args([]))["style"], "classic")
        with self.assertRaises(ValueError):
            get_style("missing")
        with redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit) as error, patch("sys.stderr", io.StringIO()):
                parser().parse_args(["--style", "missing"])
        self.assertEqual(error.exception.code, 2)
