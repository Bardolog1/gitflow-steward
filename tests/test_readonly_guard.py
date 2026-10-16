import unittest

from steward.guards.readonly_guard import decide

STEWARD_HOME = "/home/user/.claude/gitflow-steward"


class AllowedTests(unittest.TestCase):
    def test_recognized_git_log_allowed(self):
        self.assertTrue(decide("git log --oneline -20", STEWARD_HOME).allow)

    def test_git_status_allowed(self):
        self.assertTrue(decide("git status", STEWARD_HOME).allow)

    def test_git_branch_list_allowed(self):
        self.assertTrue(decide("git branch --list", STEWARD_HOME).allow)

    def test_gh_pr_list_allowed(self):
        self.assertTrue(decide("gh pr list", STEWARD_HOME).allow)

    def test_gh_issue_view_allowed(self):
        self.assertTrue(decide("gh issue view 12", STEWARD_HOME).allow)

    def test_pwd_allowed(self):
        self.assertTrue(decide("pwd", STEWARD_HOME).allow)

    def test_steward_audit_through_resolved_home_allowed(self):
        cmd = f'bash "{STEWARD_HOME}/bin/steward" audit'
        self.assertTrue(decide(cmd, STEWARD_HOME).allow)

    def test_steward_notes_draft_allowed(self):
        cmd = f'bash "{STEWARD_HOME}/bin/steward" notes draft'
        self.assertTrue(decide(cmd, STEWARD_HOME).allow)


class DefaultDenyTests(unittest.TestCase):
    def test_unknown_command_rejected(self):
        result = decide("docker ps", STEWARD_HOME)
        self.assertFalse(result.allow)
        self.assertIn("docker", result.reason)

    def test_git_fetch_rejected(self):
        self.assertFalse(decide("git fetch", STEWARD_HOME).allow)

    def test_git_push_rejected(self):
        self.assertFalse(decide("git push origin main", STEWARD_HOME).allow)

    def test_gh_api_always_rejected(self):
        self.assertFalse(decide("gh api repos/foo/bar", STEWARD_HOME).allow)

    def test_steward_bin_outside_resolved_home_rejected(self):
        cmd = 'bash "/tmp/evil/bin/steward" audit'
        self.assertFalse(decide(cmd, STEWARD_HOME).allow)


class BypassFormTests(unittest.TestCase):
    def test_git_dash_c_global_option_rejected(self):
        self.assertFalse(decide("git -C . push", STEWARD_HOME).allow)

    def test_sh_dash_c_rejected(self):
        self.assertFalse(decide('sh -c "git push origin main"', STEWARD_HOME).allow)

    def test_bash_dash_lc_rejected(self):
        self.assertFalse(decide('bash -lc "git push"', STEWARD_HOME).allow)

    def test_gh_api_post_rejected(self):
        self.assertFalse(decide("gh api -X POST repos/foo/bar", STEWARD_HOME).allow)

    def test_env_prefixed_write_rejected(self):
        self.assertFalse(decide("FOO=1 git push", STEWARD_HOME).allow)

    def test_and_chain_with_write_rejected_entirely(self):
        self.assertFalse(decide("git status && git push origin main", STEWARD_HOME).allow)

    def test_semicolon_chain_rejected(self):
        self.assertFalse(decide("git status; git push", STEWARD_HOME).allow)

    def test_pipe_chain_rejected(self):
        self.assertFalse(decide("git log | git push", STEWARD_HOME).allow)

    def test_any_control_operator_rejected_even_if_segments_look_safe(self):
        self.assertFalse(decide("git status && git log", STEWARD_HOME).allow)


class ErrorHandlingTests(unittest.TestCase):
    def test_empty_command_rejected_not_raised(self):
        result = decide("", STEWARD_HOME)
        self.assertFalse(result.allow)

    def test_malformed_quoting_rejected_not_raised(self):
        result = decide('git commit -m "unterminated', STEWARD_HOME)
        self.assertFalse(result.allow)


if __name__ == "__main__":
    unittest.main()
