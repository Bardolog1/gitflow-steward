import unittest

from steward.globmatch import match


class GlobMatchTests(unittest.TestCase):
    def test_star_stops_at_slash(self):
        self.assertTrue(match("*.lock", "yarn.lock"))
        self.assertFalse(match("*.lock", "sub/yarn.lock"))

    def test_double_star_slash_matches_any_depth(self):
        self.assertTrue(match("dist/**", "dist/a.js"))
        self.assertTrue(match("dist/**", "dist/sub/a.js"))
        self.assertTrue(match("dist/**", "dist/"))
        self.assertFalse(match("dist/**", "other/a.js"))

    def test_literal_segment_must_match_exactly(self):
        self.assertTrue(match("package.json", "package.json"))
        self.assertFalse(match("package.json", "sub/package.json"))

    def test_any_depth_in_the_middle(self):
        self.assertTrue(match("**/package.json", "package.json"))
        self.assertTrue(match("**/package.json", "a/b/package.json"))
        self.assertFalse(match("**/package.json", "a/b/package.jsonx"))

    def test_question_mark_matches_single_non_slash_char(self):
        self.assertTrue(match("a?.txt", "ab.txt"))
        self.assertFalse(match("a?.txt", "a/.txt"))


if __name__ == "__main__":
    unittest.main()
