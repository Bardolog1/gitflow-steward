import unittest

from steward.notes import render


class LoadQuestionsTests(unittest.TestCase):
    def test_loads_eight_questions_in_order(self):
        questions = render.load_questions()
        self.assertEqual(len(questions), 8)
        self.assertEqual([q["id"] for q in questions], list(range(1, 9)))
        self.assertEqual(questions[0]["slot"], "summary")
        self.assertEqual(questions[1]["slot"], "breaking")
        self.assertEqual(questions[7]["slot"], "known_issues")
        self.assertTrue(questions[0]["question"].startswith("One-sentence summary"))


class RenderGuidedTests(unittest.TestCase):
    def test_full_answers_render_every_section(self):
        answers = {
            "summary": "Adds the audit engine.",
            "breaking": "None.",
            "added": "The audit command.",
            "changed": "Default soak time is now zero days.",
            "deprecated": "The old --strict flag.",
            "removed": "The legacy config loader.",
            "fixed": "Crash on empty repositories.",
            "known_issues": "Windows paths with spaces are untested.",
        }
        text = render.render_guided(answers)
        self.assertIn("Adds the audit engine.", text)
        self.assertIn("## Breaking Changes & Upgrade Steps", text)
        self.assertIn("## Added", text)
        self.assertIn("## Changed", text)
        self.assertIn("## Deprecated", text)
        self.assertIn("## Removed", text)
        self.assertIn("## Fixed", text)
        self.assertIn("## Known Issues", text)
        self.assertLess(text.index("## Breaking"), text.index("## Added"))
        self.assertLess(text.index("## Fixed"), text.index("## Known Issues"))

    def test_empty_answer_omits_that_section(self):
        answers = {
            "summary": "Adds the audit engine.",
            "breaking": "None.",
            "added": "The audit command.",
            "changed": "",
            "deprecated": "none",
            "removed": "",
            "fixed": "Crash on empty repositories.",
            "known_issues": "",
        }
        text = render.render_guided(answers)
        self.assertNotIn("## Changed", text)
        self.assertNotIn("## Removed", text)
        self.assertNotIn("## Known Issues", text)
        self.assertIn("## Added", text)
        self.assertIn("## Fixed", text)

    def test_breaking_section_always_present_even_when_empty(self):
        answers = {"summary": "Patch release.", "breaking": ""}
        text = render.render_guided(answers)
        self.assertIn("## Breaking Changes & Upgrade Steps", text)


class RenderAutomaticTests(unittest.TestCase):
    def test_renders_groups_in_fixed_order(self):
        groups = {
            "Fixes": ("crash on empty input",),
            "Breaking": ("drop legacy config key",),
            "Features": ("add widget",),
        }
        text = render.render_automatic(groups)
        self.assertLess(text.index("## Breaking"), text.index("## Features"))
        self.assertLess(text.index("## Features"), text.index("## Fixes"))
        self.assertIn("- drop legacy config key", text)
        self.assertIn("- add widget", text)
        self.assertIn("- crash on empty input", text)

    def test_no_groups_renders_empty_string(self):
        self.assertEqual(render.render_automatic({}), "")


if __name__ == "__main__":
    unittest.main()
