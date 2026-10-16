import unittest

from steward.notes import conventional


class GroupCommitsTests(unittest.TestCase):
    def test_feat_goes_to_features(self):
        groups = conventional.group_commits([("a", "feat: add widget")])
        self.assertEqual(groups["Features"], ("add widget",))

    def test_fix_goes_to_fixes(self):
        groups = conventional.group_commits([("a", "fix: crash on empty input")])
        self.assertEqual(groups["Fixes"], ("crash on empty input",))

    def test_perf_goes_to_performance(self):
        groups = conventional.group_commits([("a", "perf: speed up audit")])
        self.assertEqual(groups["Performance"], ("speed up audit",))

    def test_bang_marks_breaking_regardless_of_type(self):
        groups = conventional.group_commits([("a", "feat!: drop legacy config key")])
        self.assertEqual(groups["Breaking"], ("drop legacy config key",))
        self.assertNotIn("Features", groups)

    def test_chore_ci_build_are_skipped(self):
        groups = conventional.group_commits([
            ("a", "chore: bump deps"),
            ("b", "ci: tweak workflow"),
            ("c", "build: pin version"),
        ])
        self.assertEqual(groups, {})

    def test_breaking_chore_is_kept_as_breaking(self):
        groups = conventional.group_commits([("a", "chore!: remove deprecated flag")])
        self.assertEqual(groups["Breaking"], ("remove deprecated flag",))

    def test_unrecognized_type_goes_to_other(self):
        groups = conventional.group_commits([("a", "wip: half-done thing")])
        self.assertEqual(groups["Other"], ("half-done thing",))

    def test_non_conventional_subject_goes_to_other(self):
        groups = conventional.group_commits([("a", "quick fix without format")])
        self.assertEqual(groups["Other"], ("quick fix without format",))

    def test_empty_groups_are_omitted_entirely(self):
        groups = conventional.group_commits([])
        self.assertEqual(groups, {})

    def test_scope_is_accepted_and_stripped(self):
        groups = conventional.group_commits([("a", "fix(cli): handle missing arg")])
        self.assertEqual(groups["Fixes"], ("handle missing arg",))

    def test_group_order_constant_matches_breaking_first(self):
        self.assertEqual(
            conventional.GROUP_ORDER,
            ("Breaking", "Features", "Fixes", "Performance", "Other"),
        )


if __name__ == "__main__":
    unittest.main()
