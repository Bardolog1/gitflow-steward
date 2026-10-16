import io
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from steward.cli import main


def run_cli(argv):
    out = io.StringIO()
    exit_code = main(argv, stdin=io.StringIO(""), stdout=out)
    return exit_code, out.getvalue()


class LintCommandTests(unittest.TestCase):
    def test_fail_finding_exits_one(self):
        with TemporaryDirectory() as root:
            path = Path(root, "doc.md")
            path.write_text("Please leverage this feature.", encoding="utf-8")
            exit_code, output = run_cli(["lint", str(path)])
        payload = json.loads(output)
        self.assertEqual(exit_code, 1)
        self.assertEqual(payload["heading"], "style findings")
        self.assertTrue(any(f["severity"] == "FAIL" for f in payload["findings"]))

    def test_only_warn_findings_exit_zero(self):
        with TemporaryDirectory() as root:
            path = Path(root, "doc.md")
            path.write_text("It is fast, reliable, and secure.", encoding="utf-8")
            exit_code, output = run_cli(["lint", str(path)])
        payload = json.loads(output)
        self.assertEqual(exit_code, 0)
        self.assertTrue(any(f["severity"] == "WARN" for f in payload["findings"]))

    def test_missing_file_exits_two(self):
        exit_code, output = run_cli(["lint", "does-not-exist.md"])
        payload = json.loads(output)
        self.assertEqual(exit_code, 2)
        self.assertIn("error", payload)


if __name__ == "__main__":
    unittest.main()
