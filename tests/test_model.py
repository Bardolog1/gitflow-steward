import dataclasses
import unittest

from steward.model import Finding, Report, Severity


class SeverityTests(unittest.TestCase):
    def test_values(self):
        self.assertEqual(Severity.FAIL, "FAIL")
        self.assertEqual(Severity.WARN, "WARN")
        self.assertEqual(Severity.INFO, "INFO")


class FindingTests(unittest.TestCase):
    def test_is_frozen(self):
        finding = Finding(
            rule="branch.bugfix-origin",
            severity=Severity.FAIL,
            subject="bugfix/x",
            message="bugfix/x does not branch from an open release/*",
        )
        with self.assertRaises(dataclasses.FrozenInstanceError):
            finding.subject = "other"

    def test_defaults(self):
        finding = Finding(
            rule="r",
            severity=Severity.INFO,
            subject="s",
            message="m",
        )
        self.assertIsNone(finding.fix)
        self.assertEqual(finding.evidence, {})


class ReportTests(unittest.TestCase):
    def test_summary_counts_by_severity(self):
        findings = [
            Finding(rule="a", severity=Severity.FAIL, subject="x", message="m"),
            Finding(rule="b", severity=Severity.FAIL, subject="x", message="m"),
            Finding(rule="c", severity=Severity.WARN, subject="x", message="m"),
            Finding(rule="d", severity=Severity.INFO, subject="x", message="m"),
        ]
        report = Report(findings=tuple(findings))
        self.assertEqual(report.summary(), {"fail": 2, "warn": 1, "info": 1})

    def test_summary_with_no_findings(self):
        report = Report(findings=())
        self.assertEqual(report.summary(), {"fail": 0, "warn": 0, "info": 0})

    def test_has_fail(self):
        failing = Report(findings=(
            Finding(rule="a", severity=Severity.FAIL, subject="x", message="m"),
        ))
        clean = Report(findings=(
            Finding(rule="a", severity=Severity.INFO, subject="x", message="m"),
        ))
        self.assertTrue(failing.has_fail())
        self.assertFalse(clean.has_fail())


if __name__ == "__main__":
    unittest.main()
