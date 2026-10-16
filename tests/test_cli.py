import contextlib
import io
import json
import os
import unittest

from steward.cli import main
from tests.gitrepo import GitRepo


def run_cli(argv, stdin_text=""):
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        exit_code = main(argv, stdin=io.StringIO(stdin_text))
    return exit_code, stdout.getvalue()


class _InRepo(unittest.TestCase):
    """Runs the CLI with cwd set to a disposable fixture repository."""

    def setUp(self):
        self.repo = GitRepo.init()
        self._old_cwd = os.getcwd()
        os.chdir(self.repo.path)

    def tearDown(self):
        os.chdir(self._old_cwd)
        self.repo.cleanup()


class AuditCommandTests(_InRepo):
    def test_json_envelope_shape_on_a_clean_repo(self):
        self.repo.commit("a.txt", "1", "init")
        exit_code, output = run_cli(["audit", "--json"])
        payload = json.loads(output)
        self.assertEqual(payload["schema"], 1)
        self.assertEqual(payload["command"], "audit")
        self.assertEqual(payload["repo"], self.repo.path)
        self.assertEqual(payload["head"], "main")
        self.assertIsNone(payload["config_source"])
        self.assertEqual(payload["findings"], [])
        self.assertEqual(payload["summary"], {"fail": 0, "warn": 0, "info": 0})
        self.assertEqual(exit_code, 0)

    def test_fail_finding_sets_exit_code_one(self):
        self.repo.commit("a.txt", "1", "init")
        self.repo.tag("v1.0.0", annotated=False)
        exit_code, output = run_cli(["audit", "--json"])
        payload = json.loads(output)
        self.assertEqual(exit_code, 1)
        self.assertTrue(any(f["rule"] == "tag.not-annotated" for f in payload["findings"]))
        self.assertEqual(payload["summary"]["fail"], 1)

    def test_environment_error_exits_two(self):
        (self.repo.path_obj / ".gitflow.toml").write_text("rc_minimum = [", encoding="utf-8")
        exit_code, output = run_cli(["audit", "--json"])
        payload = json.loads(output)
        self.assertEqual(exit_code, 2)
        self.assertIn("error", payload)


class ReadinessCommandTests(_InRepo):
    def test_go_decision_with_no_blockers(self):
        self.repo.commit("a.txt", "1", "init")
        self.repo.branch("release/1.1.0")
        self.repo.tag("v1.1.0-rc.1", annotated=True)
        self.repo.checkout("main")
        exit_code, output = run_cli(["readiness", "--release", "release/1.1.0", "--json"])
        payload = json.loads(output)
        self.assertEqual(payload["command"], "readiness")
        self.assertEqual(payload["decision"], "go")
        self.assertEqual(payload["blockers"], [])
        self.assertEqual(exit_code, 0)

    def test_no_go_decision_lists_blockers(self):
        self.repo.commit("a.txt", "1", "init")
        self.repo.branch("release/1.1.0")
        self.repo.checkout("main")
        exit_code, output = run_cli(["readiness", "--release", "release/1.1.0", "--json"])
        payload = json.loads(output)
        self.assertEqual(payload["decision"], "no-go")
        self.assertIn("readiness.rc-minimum", payload["blockers"])
        self.assertEqual(exit_code, 1)


class RouteCommandTests(_InRepo):
    def test_critical_final_routes_to_hotfix_from_main(self):
        exit_code, output = run_cli(["route", "--severity", "critical", "--stage", "final"])
        payload = json.loads(output)
        self.assertEqual(payload["command"], "route")
        finding = payload["findings"][0]
        self.assertEqual(finding["rule"], "route.plan")
        self.assertEqual(finding["evidence"], {"branch_type": "hotfix", "from_branch": "main"})
        self.assertEqual(exit_code, 0)

    def test_unsure_severity_is_undetermined_and_still_exits_zero(self):
        exit_code, output = run_cli(["route", "--severity", "unsure", "--stage", "final"])
        payload = json.loads(output)
        self.assertEqual(payload["findings"][0]["rule"], "route.undetermined")
        self.assertEqual(exit_code, 0)

    def test_critical_rc_routes_to_bugfix_targeting_the_open_release(self):
        self.repo.commit("a.txt", "1", "init")
        self.repo.branch("release/1.2.0")
        self.repo.commit("version.txt", "1.2.0", "bump version")
        self.repo.checkout("main")
        exit_code, output = run_cli(["route", "--severity", "critical", "--stage", "rc"])
        payload = json.loads(output)
        finding = payload["findings"][0]
        self.assertEqual(finding["evidence"], {"branch_type": "bugfix", "from_branch": "release/1.2.0"})
        self.assertEqual(exit_code, 0)


class LintCommandTests(unittest.TestCase):
    def test_no_findings_exits_zero(self):
        exit_code, output = run_cli(["lint", "README.md", "--json"])
        payload = json.loads(output)
        self.assertEqual(payload["command"], "lint")
        self.assertEqual(exit_code, 0)


class NotesCommandTests(unittest.TestCase):
    def test_questions_subcommand(self):
        exit_code, output = run_cli(["notes", "questions", "--json"])
        payload = json.loads(output)
        self.assertEqual(payload["command"], "notes")
        self.assertEqual(exit_code, 0)


class HookCommandTests(unittest.TestCase):
    def test_hook_always_exits_zero_and_emits_decision_shape(self):
        exit_code, output = run_cli(["hook", "readonly"], stdin_text='{"tool_input": {"command": "pwd"}, "cwd": "."}')
        payload = json.loads(output)
        self.assertIn("hookSpecificOutput", payload)
        self.assertEqual(
            payload["hookSpecificOutput"]["hookEventName"], "PreToolUse"
        )
        self.assertEqual(exit_code, 0)

    def test_hook_never_raises_on_malformed_stdin(self):
        exit_code, output = run_cli(["hook", "push"], stdin_text="not json")
        self.assertEqual(exit_code, 0)
        payload = json.loads(output)
        self.assertIn("hookSpecificOutput", payload)

    def test_hook_readonly_allows_a_recognized_command(self):
        exit_code, output = run_cli(
            ["hook", "readonly"],
            stdin_text='{"tool_input": {"command": "git status"}, "cwd": "."}',
        )
        payload = json.loads(output)
        self.assertEqual(exit_code, 0)
        self.assertEqual(
            payload["hookSpecificOutput"]["permissionDecision"], "allow"
        )

    def test_hook_readonly_denies_an_unrecognized_command(self):
        exit_code, output = run_cli(
            ["hook", "readonly"],
            stdin_text='{"tool_input": {"command": "git push origin main"}, "cwd": "."}',
        )
        payload = json.loads(output)
        self.assertEqual(exit_code, 0)
        self.assertEqual(
            payload["hookSpecificOutput"]["permissionDecision"], "deny"
        )
        self.assertTrue(payload["hookSpecificOutput"]["permissionDecisionReason"])

    def test_hook_push_asks_for_a_push(self):
        exit_code, output = run_cli(
            ["hook", "push"],
            stdin_text='{"tool_input": {"command": "git push origin main"}, "cwd": "."}',
        )
        payload = json.loads(output)
        self.assertEqual(exit_code, 0)
        self.assertEqual(
            payload["hookSpecificOutput"]["permissionDecision"], "ask"
        )

    def test_hook_push_has_no_decision_for_a_safe_command(self):
        exit_code, output = run_cli(
            ["hook", "push"],
            stdin_text='{"tool_input": {"command": "git status"}, "cwd": "."}',
        )
        payload = json.loads(output)
        self.assertEqual(exit_code, 0)
        self.assertIsNone(payload["hookSpecificOutput"]["permissionDecision"])

    def test_hook_missing_tool_input_denies_readonly_without_raising(self):
        exit_code, output = run_cli(["hook", "readonly"], stdin_text="{}")
        payload = json.loads(output)
        self.assertEqual(exit_code, 0)
        self.assertEqual(
            payload["hookSpecificOutput"]["permissionDecision"], "deny"
        )


class UsageErrorTests(unittest.TestCase):
    def test_missing_subcommand_exits_two(self):
        exit_code, _ = run_cli([])
        self.assertEqual(exit_code, 2)

    def test_unknown_subcommand_exits_two(self):
        with self.assertRaises(SystemExit) as ctx:
            main(["bogus"])
        self.assertEqual(ctx.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
