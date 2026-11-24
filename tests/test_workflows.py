"""Repository workflow invariants (configuration is omitted from source archives)."""

from pathlib import Path
import re
import unittest


WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/security.yml"


@unittest.skipUnless(WORKFLOW.is_file(), "repository workflow is not in this archive")
class WorkflowTests(unittest.TestCase):
    def test_codeql_steps_share_one_pinned_release(self):
        steps = re.findall(
            r"uses:\s+github/codeql-action/([^@\s]+)@([^\s#]+)", WORKFLOW.read_text()
        )
        self.assertEqual({name for name, _ in steps}, {"init", "analyze"})
        revisions = {revision for _, revision in steps}
        self.assertEqual(len(revisions), 1, "CodeQL rejects mismatched init/analyze versions")
        self.assertRegex(revisions.pop(), r"^[0-9a-f]{40}$")
