import unittest

from steward.git import GitError, GitRunner, collect
from tests.gitrepo import GitRepo


class GitRunnerTests(unittest.TestCase):
    def setUp(self):
        self.repo = GitRepo.init()
        self.addCleanup(self.repo.cleanup)

    def test_run_returns_normalized_stdout(self):
        self.repo.commit("a.txt", "one", "first")
        runner = GitRunner(self.repo.path)
        out = runner.run("rev-parse", "HEAD")
        self.assertEqual(out.strip(), self.repo.head())

    def test_run_raises_on_git_error(self):
        runner = GitRunner(self.repo.path)
        with self.assertRaises(GitError):
            runner.run("not-a-git-command")

    def test_run_works_with_space_in_path(self):
        self.assertIn(" ", self.repo.path)
        self.repo.commit("a.txt", "one", "first")
        runner = GitRunner(self.repo.path)
        self.assertEqual(runner.run("status", "--short"), "")


class CollectTests(unittest.TestCase):
    def setUp(self):
        self.repo = GitRepo.init()
        self.addCleanup(self.repo.cleanup)

    def test_collect_single_commit_repo(self):
        sha = self.repo.commit("a.txt", "one", "first")
        state = collect(self.repo.path)
        self.assertEqual(state.head, "main")
        self.assertEqual(state.head_sha, sha)
        self.assertEqual({b.name for b in state.branches}, {"main"})
        self.assertEqual(state.tags, ())
        self.assertIn(sha, state.commits)
        self.assertEqual(state.commits[sha].parents, ())
        self.assertEqual(state.commits[sha].message, "first")

    def test_collect_branches_and_merge_base(self):
        self.repo.commit("a.txt", "one", "first")
        base = self.repo.head()
        self.repo.branch("develop")
        self.repo.commit("b.txt", "two", "on develop")
        self.repo.branch("feature/x")
        feature_tip = self.repo.commit("c.txt", "three", "on feature")
        state = collect(self.repo.path)
        names = {b.name for b in state.branches}
        self.assertEqual(names, {"main", "develop", "feature/x"})
        mb = state.merge_bases[tuple(sorted(("main", "feature/x")))]
        self.assertEqual(mb, base)
        self.assertIn(feature_tip, state.commits)

    def test_collect_tags_annotated_and_lightweight(self):
        sha = self.repo.commit("a.txt", "one", "first")
        self.repo.tag("v1.0.0", annotated=True, message="release")
        self.repo.tag("light", annotated=False)
        state = collect(self.repo.path)
        by_name = {t.name: t for t in state.tags}
        self.assertTrue(by_name["v1.0.0"].annotated)
        self.assertEqual(by_name["v1.0.0"].sha, sha)
        self.assertIsNotNone(by_name["v1.0.0"].tagger_date)
        self.assertFalse(by_name["light"].annotated)
        self.assertEqual(by_name["light"].sha, sha)

    def test_collect_merge_commit_has_two_parents(self):
        self.repo.commit("a.txt", "one", "first")
        self.repo.branch("feature/x")
        self.repo.commit("b.txt", "two", "on feature")
        self.repo.checkout("main")
        merge_sha = self.repo.merge("feature/x", no_ff=True)
        state = collect(self.repo.path)
        self.assertEqual(len(state.commits[merge_sha].parents), 2)


if __name__ == "__main__":
    unittest.main()
