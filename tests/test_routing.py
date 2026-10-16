import unittest

from steward.routing import (
    CRITICAL,
    NON_CRITICAL,
    UNDETERMINED,
    BugReport,
    RoutingError,
    classify,
    route,
)


class ClassifyTests(unittest.TestCase):
    def test_data_loss_bug_is_critical(self):
        report = BugReport(data_loss=True)
        self.assertEqual(classify(report), CRITICAL)

    def test_main_flow_crash_is_critical_when_task_is_declared_core(self):
        report = BugReport(ux_signal="crash-in-main-flow", task="checkout")
        self.assertEqual(classify(report, core_tasks=("checkout",)), CRITICAL)

    def test_cosmetic_misalignment_is_not_critical(self):
        report = BugReport(ux_signal="cosmetic-misalignment")
        self.assertEqual(classify(report), NON_CRITICAL)

    def test_no_core_tasks_declared_bug_is_ambiguous(self):
        report = BugReport(ux_signal="unreadable-main-flow", task="settings")
        self.assertEqual(classify(report, core_tasks=()), UNDETERMINED)

    def test_plain_bug_with_no_signal_is_non_critical(self):
        self.assertEqual(classify(BugReport()), NON_CRITICAL)


class RouteTests(unittest.TestCase):
    def test_critical_bug_found_in_an_rc_routes_to_bugfix_on_the_release(self):
        plan = route(CRITICAL, "rc", open_release="release/1.4.0")
        self.assertEqual(plan.branch_type, "bugfix")
        self.assertEqual(plan.from_branch, "release/1.4.0")

    def test_critical_bug_in_released_version_routes_to_hotfix_from_main(self):
        plan = route(CRITICAL, "released")
        self.assertEqual(plan.branch_type, "hotfix")
        self.assertEqual(plan.from_branch, "main")

    def test_non_critical_bug_ships_later_via_feature_from_develop(self):
        plan = route(NON_CRITICAL, "released")
        self.assertEqual(plan.branch_type, "feature")
        self.assertEqual(plan.from_branch, "develop")

    def test_undetermined_severity_is_never_routed(self):
        with self.assertRaises(RoutingError):
            route(UNDETERMINED, "released")


if __name__ == "__main__":
    unittest.main()
