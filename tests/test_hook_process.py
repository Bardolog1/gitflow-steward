import json
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
STEWARD_CLI = REPO_ROOT / "steward_cli.py"


def _run_hook(kind: str, command: str, cwd: str | None = None) -> dict:
    result = subprocess.run(
        [sys.executable, str(STEWARD_CLI), "hook", kind],
        input=json.dumps({"tool_input": {"command": command}, "cwd": cwd or str(REPO_ROOT)}),
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)["hookSpecificOutput"]


class ReadonlyHookProcessTests(unittest.TestCase):
    def test_unknown_command_rejected_by_default(self):
        payload = _run_hook("readonly", "rm -rf /")
        self.assertEqual(payload["permissionDecision"], "deny")

    def test_recognized_read_only_command_allowed(self):
        payload = _run_hook("readonly", "git log --oneline -20")
        self.assertEqual(payload["permissionDecision"], "allow")

    def test_shell_wrapping_a_push_is_rejected(self):
        payload = _run_hook("readonly", 'sh -c "git push origin main"')
        self.assertEqual(payload["permissionDecision"], "deny")

    def test_chained_command_hiding_a_write_rejects_the_whole_chain(self):
        payload = _run_hook("readonly", "git status && git push origin main")
        self.assertEqual(payload["permissionDecision"], "deny")


class PushHookProcessTests(unittest.TestCase):
    def test_push_requires_confirmation(self):
        payload = _run_hook("push", "git push origin main")
        self.assertEqual(payload["permissionDecision"], "ask")

    def test_branch_deletion_requires_confirmation(self):
        payload = _run_hook("push", "git branch -D release/1.3.0")
        self.assertEqual(payload["permissionDecision"], "ask")

    def test_gh_release_create_requires_confirmation(self):
        payload = _run_hook("push", "gh release create v1.3.0")
        self.assertEqual(payload["permissionDecision"], "ask")

    def test_already_confirmed_in_chat_still_asks(self):
        # The operator may have already asked in conversation; the guard
        # does not trust that and asks again independently.
        payload = _run_hook("push", "git push origin main")
        self.assertEqual(payload["permissionDecision"], "ask")

    def test_plain_status_gets_no_decision(self):
        payload = _run_hook("push", "git status")
        self.assertIsNone(payload["permissionDecision"])


if __name__ == "__main__":
    unittest.main()
