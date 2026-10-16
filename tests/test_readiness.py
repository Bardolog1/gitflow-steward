import json
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from steward.config import Config
from steward.git import Branch, Commit, RepoState, Tag
from steward.readiness import check, render_text


def _commit(sha, date="2024-01-01T00:00:00+00:00"):
    return Commit(sha=sha, parents=(), author_date=date, message="msg")


def _state(branches, tags, commits):
    return RepoState(
        root="/fake",
        head="main",
        head_sha=branches[0].sha,
        branches=tuple(branches),
        tags=tuple(tags),
        commits={c.sha: c for c in commits},
        merge_bases={},
    )


class ReadinessTests(unittest.TestCase):
    def setUp(self):
        patcher = patch("steward.readiness.gh.is_available", return_value=False)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_report_lists_all_inputs(self):
        c0, c1 = _commit("c0"), _commit("c1")
        branches = [
            Branch("main", "c0"),
            Branch("release/1.3.0", "c0"),
            Branch("bugfix/null-pointer", "c1"),
        ]
        tags = [
            Tag(name="v1.3.0-rc.1", sha="c0", annotated=True, tagger_date="2024-01-01T00:00:00+00:00"),
            Tag(name="v1.3.0-rc.2", sha="c0", annotated=True, tagger_date="2024-01-02T00:00:00+00:00"),
        ]
        report = check(_state(branches, tags, [c0, c1]), Config(), "release/1.3.0")
        rules = {f.rule for f in report.findings}
        self.assertIn("readiness.unmerged-bugfix", rules)
        rc_finding = next(f for f in report.findings if f.rule == "readiness.rc-count")
        self.assertEqual(rc_finding.evidence["rc_count"], "2")

    def test_unmerged_bugfix_branch_blocks(self):
        c0, c1 = _commit("c0"), _commit("c1")
        branches = [
            Branch("main", "c0"),
            Branch("release/1.3.0", "c0"),
            Branch("bugfix/null-pointer", "c1"),
        ]
        report = check(_state(branches, [], [c0, c1]), Config(), "release/1.3.0")
        self.assertEqual(report.decision, "no-go")
        self.assertTrue(any(f.subject == "bugfix/null-pointer" for f in report.blockers()))

    def test_gh_not_installed_ci_is_unknown_not_blocking(self):
        c0 = _commit("c0")
        branches = [Branch("main", "c0"), Branch("release/1.3.0", "c0")]
        report = check(_state(branches, [], [c0]), Config(rc_minimum=0), "release/1.3.0")
        self.assertEqual(report.decision, "go")
        self.assertTrue(any(f.rule == "readiness.ci-unknown" for f in report.findings))

    def test_blocker_issue_blocks(self):
        with patch("steward.readiness.gh.is_available", return_value=True):
            c0 = _commit("c0")
            branches = [Branch("main", "c0"), Branch("release/1.3.0", "c0")]

            def fake_gh(*args):
                if args[0] == "issue":
                    return [{"number": 42, "title": "data loss on save"}]
                return []

            report = check(_state(branches, [], [c0]), Config(rc_minimum=0), "release/1.3.0", gh_run_json=fake_gh)
            self.assertEqual(report.decision, "no-go")
            self.assertTrue(any(f.subject == "#42" for f in report.blockers()))

    def test_ci_failing_blocks(self):
        with patch("steward.readiness.gh.is_available", return_value=True):
            c0 = _commit("c0")
            branches = [Branch("main", "c0"), Branch("release/1.3.0", "c0")]

            def fake_gh(*args):
                if args[0] == "run":
                    return [{"status": "completed", "conclusion": "failure"}]
                return []

            report = check(_state(branches, [], [c0]), Config(rc_minimum=0), "release/1.3.0", gh_run_json=fake_gh)
            self.assertEqual(report.decision, "no-go")
            self.assertTrue(any(f.rule == "readiness.ci-failing" for f in report.blockers()))

    def test_below_configured_rc_minimum(self):
        c0 = _commit("c0")
        branches = [Branch("main", "c0"), Branch("release/1.3.0", "c0")]
        tags = [Tag(name="v1.3.0-rc.1", sha="c0", annotated=True, tagger_date="2024-01-01T00:00:00+00:00")]
        report = check(_state(branches, tags, [c0]), Config(rc_minimum=2), "release/1.3.0")
        self.assertEqual(report.decision, "no-go")
        self.assertTrue(any(f.rule == "readiness.rc-minimum" for f in report.blockers()))

    def test_soak_time_configured_and_not_met(self):
        c0 = _commit("c0")
        branches = [Branch("main", "c0"), Branch("release/1.3.0", "c0")]
        now = datetime.now(timezone.utc)
        rc_time = (now - timedelta(hours=6)).isoformat()
        tags = [Tag(name="v1.3.0-rc.1", sha="c0", annotated=True, tagger_date=rc_time)]
        report = check(_state(branches, tags, [c0]), Config(rc_minimum=0, soak_days=2), "release/1.3.0", now=now)
        self.assertEqual(report.decision, "no-go")
        self.assertTrue(any(f.rule == "readiness.soak-time-insufficient" for f in report.blockers()))

    def test_default_soak_time_is_advisory_only(self):
        c0 = _commit("c0")
        branches = [Branch("main", "c0"), Branch("release/1.3.0", "c0")]
        now = datetime.now(timezone.utc)
        rc_time = (now - timedelta(minutes=10)).isoformat()
        tags = [Tag(name="v1.3.0-rc.1", sha="c0", annotated=True, tagger_date=rc_time)]
        report = check(_state(branches, tags, [c0]), Config(rc_minimum=0), "release/1.3.0", now=now)
        self.assertEqual(report.decision, "go")
        warn = [f for f in report.findings if f.rule == "readiness.soak-time-insufficient"]
        self.assertEqual(len(warn), 1)
        self.assertEqual(str(warn[0].severity), "WARN")

    def test_json_output_matches_text_findings(self):
        c0 = _commit("c0")
        branches = [Branch("main", "c0"), Branch("release/1.3.0", "c0")]
        report = check(_state(branches, [], [c0]), Config(rc_minimum=0), "release/1.3.0")
        payload = json.dumps(report.to_dict())
        parsed = json.loads(payload)
        self.assertEqual(parsed["decision"], report.decision)
        self.assertEqual(len(parsed["findings"]), len(report.findings))
        self.assertIn("decision: go", render_text(report))


if __name__ == "__main__":
    unittest.main()
