import unittest

from steward.git import commit_subjects_between
from tests.gitrepo import GitRepo


class CommitSubjectsBetweenTests(unittest.TestCase):
    def setUp(self):
        self.repo = GitRepo.init()
        self.addCleanup(self.repo.cleanup)

    def test_returns_subjects_for_commits_after_from_rev(self):
        first = self.repo.commit("a.txt", "1", "chore: init")
        self.repo.commit("a.txt", "2", "feat: add thing")
        last = self.repo.commit("a.txt", "3", "fix: bug")
        result = commit_subjects_between(self.repo.path, first, last)
        subjects = [subject for _, subject in result]
        self.assertEqual(subjects, ["fix: bug", "feat: add thing"])

    def test_empty_range_returns_empty_tuple(self):
        sha = self.repo.commit("a.txt", "1", "init")
        result = commit_subjects_between(self.repo.path, sha, sha)
        self.assertEqual(result, ())


if __name__ == "__main__":
    unittest.main()
