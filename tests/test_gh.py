import json
import unittest
from unittest import mock

from steward import gh


class GhAvailabilityTests(unittest.TestCase):
    def test_is_available_true_when_on_path(self):
        with mock.patch("shutil.which", return_value="/usr/bin/gh"):
            self.assertTrue(gh.is_available())

    def test_is_available_false_when_missing(self):
        with mock.patch("shutil.which", return_value=None):
            self.assertFalse(gh.is_available())


class RunJsonTests(unittest.TestCase):
    def test_returns_none_when_gh_missing(self):
        with mock.patch("shutil.which", return_value=None):
            self.assertIsNone(gh.run_json("pr", "list"))

    def test_parses_json_stdout(self):
        fake = mock.Mock(returncode=0, stdout=json.dumps([{"number": 1}]), stderr="")
        with mock.patch("shutil.which", return_value="/usr/bin/gh"), \
             mock.patch("subprocess.run", return_value=fake):
            result = gh.run_json("pr", "list")
        self.assertEqual(result, [{"number": 1}])

    def test_raises_gherror_on_nonzero_exit(self):
        fake = mock.Mock(returncode=1, stdout="", stderr="not logged in")
        with mock.patch("shutil.which", return_value="/usr/bin/gh"), \
             mock.patch("subprocess.run", return_value=fake):
            with self.assertRaises(gh.GhError):
                gh.run_json("pr", "list")


class MissingFindingTests(unittest.TestCase):
    def test_missing_finding_is_info_not_fail(self):
        from steward.model import Severity

        self.assertEqual(gh.GH_MISSING.severity, Severity.INFO)


if __name__ == "__main__":
    unittest.main()
