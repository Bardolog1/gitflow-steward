import unittest
import unittest.mock as mock
from pathlib import Path

from tests.gitrepo import GitRepo

from steward.notes import publish as publish_module


class PublishTests(unittest.TestCase):
    def setUp(self):
        self.repo = GitRepo.init()
        self.addCleanup(self.repo.cleanup)

    def test_writes_notes_file_and_reports_gh_available(self):
        with mock.patch("steward.notes.publish.gh.is_available", return_value=True):
            result = publish_module.publish("## Added\n\n- thing\n", repo_root=self.repo.path)
        self.assertTrue(result["gh_available"])
        self.assertEqual(Path(result["file"]).read_text(encoding="utf-8"), "## Added\n\n- thing\n")

    def test_reports_gh_unavailable_but_still_writes_file(self):
        with mock.patch("steward.notes.publish.gh.is_available", return_value=False):
            result = publish_module.publish("notes body", repo_root=self.repo.path)
        self.assertFalse(result["gh_available"])
        self.assertTrue(Path(result["file"]).exists())


if __name__ == "__main__":
    unittest.main()
