import unittest

from steward.lint import runner
from steward.lint.doc import build_doc
from steward.lint.warn_rules import check

_RULES = runner.load_rules()


def _rule_ids(text, path="doc.md", rules=None):
    return {f.rule for f in check(build_doc(path, text), rules or _RULES)}


class AiVocabularyTests(unittest.TestCase):
    def test_high_density_warns(self):
        text = "utilize delve boost tapestry landscape foster vibrant navigate unlock harness"
        self.assertIn("lint.warn.ai_vocabulary", _rule_ids(text))

    def test_low_density_passes(self):
        text = " ".join(["word"] * 50) + " utilize"
        self.assertNotIn("lint.warn.ai_vocabulary", _rule_ids(text))

    def test_lowering_threshold_changes_output(self):
        text = "utilize " + " ".join(["word"] * 99)
        lenient_rules = {"fail": {}, "warn": dict(_RULES["warn"], ai_vocabulary_threshold_per_100_words=100)}
        strict_rules = {"fail": {}, "warn": dict(_RULES["warn"], ai_vocabulary_threshold_per_100_words=1)}
        self.assertNotIn("lint.warn.ai_vocabulary", _rule_ids(text, rules=lenient_rules))
        self.assertIn("lint.warn.ai_vocabulary", _rule_ids(text, rules=strict_rules))

    def test_density_never_fails(self):
        text = "utilize delve boost tapestry landscape foster vibrant navigate unlock harness"
        self.assertEqual({f.severity for f in check(build_doc("doc.md", text), _RULES) if f.rule == "lint.warn.ai_vocabulary"}, {"WARN"})


class TriadTests(unittest.TestCase):
    def test_triad_warns_not_fails(self):
        findings = check(build_doc("doc.md", "It is fast, reliable, and secure."), _RULES)
        triad = [f for f in findings if f.rule == "lint.warn.triad"]
        self.assertEqual(len(triad), 1)
        self.assertEqual(triad[0].severity, "WARN")

    def test_two_items_do_not_warn(self):
        self.assertNotIn("lint.warn.triad", _rule_ids("It is fast and reliable."))


class NegativeParallelismTests(unittest.TestCase):
    def test_not_x_but_y_warns(self):
        self.assertIn("lint.warn.negative_parallelism", _rule_ids("This is not a bug, but a feature."))

    def test_plain_sentence_passes(self):
        self.assertNotIn("lint.warn.negative_parallelism", _rule_ids("This is a feature."))


class VagueAttributionTests(unittest.TestCase):
    def test_vague_phrase_warns(self):
        self.assertIn("lint.warn.vague_attribution", _rule_ids("Studies show this works."))

    def test_specific_attribution_passes(self):
        self.assertNotIn("lint.warn.vague_attribution", _rule_ids("The 2023 benchmark report shows this works."))


class ParagraphLengthTests(unittest.TestCase):
    def test_long_paragraph_warns(self):
        text = " ".join(["word"] * 200)
        self.assertIn("lint.warn.paragraph_length", _rule_ids(text))

    def test_short_paragraph_passes(self):
        self.assertNotIn("lint.warn.paragraph_length", _rule_ids("A short paragraph."))


class NonParallelListTests(unittest.TestCase):
    def test_mixed_gerund_forms_warn(self):
        text = "- Running the build\n- test the output\n- Deploying the result\n"
        self.assertIn("lint.warn.non_parallel_list", _rule_ids(text))

    def test_consistent_forms_pass(self):
        text = "- Running the build\n- Testing the output\n- Deploying the result\n"
        self.assertNotIn("lint.warn.non_parallel_list", _rule_ids(text))


class EmDashTests(unittest.TestCase):
    def test_em_dash_warns_when_enabled(self):
        rules = {"fail": {}, "warn": dict(_RULES["warn"], em_dash_enabled=True)}
        self.assertIn("lint.warn.em_dash", _rule_ids("A sentence — with an em dash.", rules=rules))

    def test_em_dash_silent_when_disabled_by_default(self):
        self.assertNotIn("lint.warn.em_dash", _rule_ids("A sentence — with an em dash."))


if __name__ == "__main__":
    unittest.main()
