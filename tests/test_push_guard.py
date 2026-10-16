import unittest
from unittest.mock import patch

from steward.guards.push_guard import decide


class AskTests(unittest.TestCase):
    def test_git_push_asks(self):
        result = decide("git push origin main", cwd=".")
        self.assertEqual(result.decision, "ask")

    def test_git_push_force_asks(self):
        result = decide("git push --force", cwd=".")
        self.assertEqual(result.decision, "ask")

    def test_tag_push_asks(self):
        result = decide("git push origin v1.2.0", cwd=".")
        self.assertEqual(result.decision, "ask")

    def test_tag_delete_asks(self):
        result = decide("git tag -d v1.2.0", cwd=".")
        self.assertEqual(result.decision, "ask")

    def test_branch_delete_dash_d_asks(self):
        result = decide("git branch -d release/1.1.0", cwd=".")
        self.assertEqual(result.decision, "ask")

    def test_branch_delete_dash_capital_d_asks(self):
        result = decide("git branch -D release/1.1.0", cwd=".")
        self.assertEqual(result.decision, "ask")

    def test_branch_delete_long_form_asks(self):
        result = decide("git branch --delete release/1.1.0", cwd=".")
        self.assertEqual(result.decision, "ask")

    def test_gh_release_create_asks(self):
        result = decide("gh release create v1.2.0", cwd=".")
        self.assertEqual(result.decision, "ask")

    def test_gh_release_delete_asks(self):
        result = decide("gh release delete v1.2.0", cwd=".")
        self.assertEqual(result.decision, "ask")

    def test_gh_pr_merge_asks(self):
        result = decide("gh pr merge 5", cwd=".")
        self.assertEqual(result.decision, "ask")

    def test_gh_api_asks(self):
        result = decide("gh api repos/foo/bar", cwd=".")
        self.assertEqual(result.decision, "ask")

    @patch("steward.guards.push_guard._current_branch", return_value="main")
    def test_merge_while_head_is_main_asks(self, _mock):
        result = decide("git merge release/1.1.0", cwd=".")
        self.assertEqual(result.decision, "ask")

    def test_merge_after_checkout_to_main_in_same_command_asks(self):
        result = decide("git checkout main && git merge release/1.1.0", cwd=".")
        self.assertEqual(result.decision, "ask")

    def test_merge_after_switch_to_main_in_same_command_asks(self):
        result = decide("git switch main && git merge release/1.1.0", cwd=".")
        self.assertEqual(result.decision, "ask")


class ObfuscationAsksTests(unittest.TestCase):
    def test_sh_dash_c_asks(self):
        self.assertEqual(decide('sh -c "git push origin main"', cwd=".").decision, "ask")

    def test_bash_dash_c_asks(self):
        self.assertEqual(decide('bash -c "git push"', cwd=".").decision, "ask")

    def test_bash_dash_lc_asks(self):
        self.assertEqual(decide('bash -lc "git push"', cwd=".").decision, "ask")

    def test_eval_asks(self):
        self.assertEqual(decide('eval "git push"', cwd=".").decision, "ask")

    def test_dollar_paren_asks(self):
        self.assertEqual(decide("echo $(git push)", cwd=".").decision, "ask")

    def test_backtick_asks(self):
        self.assertEqual(decide("echo `git push`", cwd=".").decision, "ask")

    def test_env_wrapper_asks(self):
        self.assertEqual(decide("env FOO=1 git push", cwd=".").decision, "ask")

    def test_git_dash_capital_c_asks(self):
        self.assertEqual(decide("git -C . status", cwd=".").decision, "ask")

    def test_git_dash_c_option_asks(self):
        self.assertEqual(decide("git -c core.pager=cat status", cwd=".").decision, "ask")


class NoDecisionTests(unittest.TestCase):
    @patch("steward.guards.push_guard._current_branch", return_value="develop")
    def test_safe_read_command_returns_none(self, _mock):
        result = decide("git status", cwd=".")
        self.assertIsNone(result.decision)

    @patch("steward.guards.push_guard._current_branch", return_value="develop")
    def test_merge_while_not_on_main_returns_none(self, _mock):
        result = decide("git merge feature/x", cwd=".")
        self.assertIsNone(result.decision)

    @patch("steward.guards.push_guard._current_branch", return_value="develop")
    def test_normal_commit_returns_none(self, _mock):
        result = decide('git commit -m "msg"', cwd=".")
        self.assertIsNone(result.decision)


class ErrorHandlingTests(unittest.TestCase):
    def test_malformed_quoting_asks_not_raises(self):
        result = decide('git commit -m "unterminated', cwd=".")
        self.assertEqual(result.decision, "ask")

    @patch("steward.guards.push_guard._current_branch", side_effect=RuntimeError("boom"))
    def test_current_branch_lookup_failure_falls_back_to_ask_for_merge(self, _mock):
        result = decide("git merge release/1.1.0", cwd=".")
        self.assertEqual(result.decision, "ask")


if __name__ == "__main__":
    unittest.main()
