import unittest

from steward.lint import runner
from steward.lint.doc import build_doc
from steward.lint.fail_rules import check

_DATA = runner.load_rules()["fail"]


def _rule_ids(text, path="doc.md"):
    return {f.rule for f in check(build_doc(path, text), _DATA)}


class HypeWordTests(unittest.TestCase):
    def test_leverage_fails(self):
        self.assertIn("lint.fail.hype_word", _rule_ids("You can leverage this tool."))

    def test_plain_text_passes(self):
        self.assertNotIn("lint.fail.hype_word", _rule_ids("You can use this tool."))


class EmojiTests(unittest.TestCase):
    def test_emoji_fails(self):
        self.assertIn("lint.fail.emoji", _rule_ids("Great work \U0001F680"))

    def test_em_dash_alone_never_fails(self):
        ids = _rule_ids("A long sentence — with an em dash and nothing else.")
        self.assertEqual(ids, set())


class ChatbotResidueTests(unittest.TestCase):
    def test_residue_phrase_fails(self):
        self.assertIn("lint.fail.chatbot_residue", _rule_ids("I hope this helps you out."))

    def test_unrelated_text_passes(self):
        self.assertNotIn("lint.fail.chatbot_residue", _rule_ids("The build finished."))


class OpenerCloserTests(unittest.TestCase):
    def test_opener_fails(self):
        self.assertIn("lint.fail.opener", _rule_ids("Great question! Here is the answer."))

    def test_closer_fails(self):
        self.assertIn("lint.fail.closer", _rule_ids("Hope that helps."))

    def test_plain_sentence_passes(self):
        ids = _rule_ids("The answer is in the config file.")
        self.assertNotIn("lint.fail.opener", ids)
        self.assertNotIn("lint.fail.closer", ids)


class NarratingCommentTests(unittest.TestCase):
    def test_narrating_comment_in_source_fails(self):
        self.assertIn("lint.fail.narrating_comment", _rule_ids("# This function adds two numbers\ndef add(a, b):\n    return a + b\n", path="code.py"))

    def test_rationale_comment_passes(self):
        ids = _rule_ids("# ponytail: naive scan, switch to index if this gets slow\ndef scan(xs):\n    return [x for x in xs]\n", path="code.py")
        self.assertNotIn("lint.fail.narrating_comment", ids)

    def test_narrating_comment_inside_fence_fails_for_markdown(self):
        text = "Some prose.\n\n```python\n# Here we loop over items\nfor x in xs:\n    pass\n```\n"
        self.assertIn("lint.fail.narrating_comment", _rule_ids(text, path="doc.md"))


if __name__ == "__main__":
    unittest.main()
