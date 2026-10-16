import unittest

from steward.guards.cmdparse import split


class SplitTests(unittest.TestCase):
    def test_single_command_has_one_segment_and_no_operator(self):
        result = split("git status")
        self.assertEqual(result.segments, (("git", "status"),))
        self.assertFalse(result.has_control_operator)

    def test_quoted_argument_stays_one_token(self):
        result = split('sh -c "git push origin main"')
        self.assertEqual(result.segments, (("sh", "-c", "git push origin main"),))
        self.assertFalse(result.has_control_operator)

    def test_and_chain_splits_into_two_segments_and_flags_operator(self):
        result = split("git status && git push origin main")
        self.assertEqual(
            result.segments,
            (("git", "status"), ("git", "push", "origin", "main")),
        )
        self.assertTrue(result.has_control_operator)

    def test_semicolon_chain_splits_and_flags_operator(self):
        result = split("git push; echo done")
        self.assertEqual(result.segments, (("git", "push"), ("echo", "done")))
        self.assertTrue(result.has_control_operator)

    def test_pipe_splits_and_flags_operator(self):
        result = split("echo hi | cat")
        self.assertEqual(result.segments, (("echo", "hi"), ("cat",)))
        self.assertTrue(result.has_control_operator)

    def test_or_chain_flags_operator(self):
        result = split("git push || true")
        self.assertTrue(result.has_control_operator)

    def test_background_operator_flags_operator(self):
        result = split("git push &")
        self.assertTrue(result.has_control_operator)

    def test_redirection_flags_operator(self):
        result = split("git push >> out.txt")
        self.assertTrue(result.has_control_operator)

    def test_embedded_newline_flags_operator(self):
        result = split("git status\ngit push")
        self.assertTrue(result.has_control_operator)

    def test_backtick_flags_operator(self):
        result = split("echo `git rev-parse HEAD`")
        self.assertTrue(result.has_control_operator)

    def test_dollar_paren_flags_operator(self):
        result = split("echo $(git rev-parse HEAD)")
        self.assertTrue(result.has_control_operator)

    def test_malformed_quoting_is_rejected_not_raised(self):
        result = split('git commit -m "unterminated')
        self.assertTrue(result.has_control_operator)
        self.assertEqual(result.segments, ())


if __name__ == "__main__":
    unittest.main()
