import contextlib
import io
import json
import unittest

from steward.cli import main


def run_cli(argv, stdin_text=""):
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        exit_code = main(argv, stdin=io.StringIO(stdin_text))
    return exit_code, stdout.getvalue()


class AuditCommandTests(unittest.TestCase):
    def test_json_envelope_shape(self):
        exit_code, output = run_cli(["audit", "--json"])
        payload = json.loads(output)
        self.assertEqual(payload["schema"], 1)
        self.assertEqual(payload["command"], "audit")
        self.assertIn("repo", payload)
        self.assertIn("head", payload)
        self.assertIn("config_source", payload)
        self.assertEqual(payload["findings"], [])
        self.assertEqual(payload["summary"], {"fail": 0, "warn": 0, "info": 0})
        self.assertEqual(exit_code, 0)


class ReadinessCommandTests(unittest.TestCase):
    def test_envelope_adds_decision_and_blockers(self):
        exit_code, output = run_cli(["readiness", "--release", "release/1.1.0", "--json"])
        payload = json.loads(output)
        self.assertEqual(payload["command"], "readiness")
        self.assertEqual(payload["decision"], "go")
        self.assertEqual(payload["blockers"], [])
        self.assertEqual(exit_code, 0)


class RouteCommandTests(unittest.TestCase):
    def test_exit_code_is_always_zero(self):
        exit_code, output = run_cli([
            "route", "--severity", "critical", "--stage", "final",
        ])
        payload = json.loads(output)
        self.assertEqual(payload["command"], "route")
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
