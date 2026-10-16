import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from steward.lint import runner


class CheckTests(unittest.TestCase):
    def test_fail_finding_sets_exit_relevant_flag(self):
        with TemporaryDirectory() as root:
            path = Path(root, "doc.md")
            path.write_text("Please leverage this feature.", encoding="utf-8")
            report = runner.check([str(path)], root=root)
        self.assertTrue(report.has_fail())

    def test_clean_text_has_no_findings(self):
        with TemporaryDirectory() as root:
            path = Path(root, "doc.md")
            path.write_text("This is plain, ordinary text.", encoding="utf-8")
            report = runner.check([str(path)], root=root)
        self.assertEqual(report.findings, ())


class LintConfigTests(unittest.TestCase):
    def test_disable_warn_rules_suppresses_rule(self):
        with TemporaryDirectory() as root:
            Path(root, ".gitflow.toml").write_text(
                'rc_minimum = 1\n[lint]\ndisable_warn_rules = ["triad"]\n', encoding="utf-8"
            )
            path = Path(root, "doc.md")
            path.write_text("It is fast, reliable, and secure.", encoding="utf-8")
            report = runner.check([str(path)], root=root)
        self.assertNotIn("lint.warn.triad", {f.rule for f in report.findings})

    def test_fail_rule_cannot_be_disabled(self):
        with TemporaryDirectory() as root:
            Path(root, ".gitflow.toml").write_text(
                '[lint]\ndisable_warn_rules = ["hype_word"]\n', encoding="utf-8"
            )
            path = Path(root, "doc.md")
            path.write_text("Please leverage this feature.", encoding="utf-8")
            report = runner.check([str(path)], root=root)
        self.assertIn("lint.fail.hype_word", {f.rule for f in report.findings})

    def test_extra_ai_vocabulary_word_is_picked_up(self):
        with TemporaryDirectory() as root:
            Path(root, ".gitflow.toml").write_text(
                '[lint]\nextra_ai_vocabulary = ["gizmo"]\n', encoding="utf-8"
            )
            path = Path(root, "doc.md")
            text = " ".join(["gizmo"] * 5 + ["word"] * 50)
            path.write_text(text, encoding="utf-8")
            report = runner.check([str(path)], root=root)
        self.assertIn("lint.warn.ai_vocabulary", {f.rule for f in report.findings})


if __name__ == "__main__":
    unittest.main()
