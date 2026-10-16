import subprocess
import unittest

from tests.gitrepo import GitRepo


class GitRepoFixtureTests(unittest.TestCase):
    def test_init_creates_repo_with_space_in_path(self):
        repo = GitRepo.init()
        self.addCleanup(repo.cleanup)
        self.assertIn("gs test ", repo.path)
        self.assertTrue((repo.path_obj / ".git").is_dir())

    def test_commit_advances_head(self):
        repo = GitRepo.init()
        self.addCleanup(repo.cleanup)
        first = repo.commit("a.txt", "one", "first commit")
        second = repo.commit("a.txt", "two", "second commit")
        self.assertNotEqual(first, second)
        self.assertEqual(repo.head(), second)

    def test_branch_creates_and_switches(self):
        repo = GitRepo.init()
        self.addCleanup(repo.cleanup)
        repo.commit("a.txt", "one", "first commit")
        repo.branch("feature/x")
        self.assertEqual(repo.current_branch(), "feature/x")

    def test_merge_no_ff_creates_merge_commit(self):
        repo = GitRepo.init()
        self.addCleanup(repo.cleanup)
        repo.commit("a.txt", "one", "first commit")
        repo.branch("feature/x")
        repo.commit("b.txt", "two", "second commit")
        repo.checkout("main")
        merge_sha = repo.merge("feature/x", no_ff=True)
        parents = repo.run(
            "show", "-s", "--format=%P", merge_sha
        ).split()
        self.assertEqual(len(parents), 2)

    def test_merge_fast_forward_has_single_parent(self):
        repo = GitRepo.init()
        self.addCleanup(repo.cleanup)
        repo.commit("a.txt", "one", "first commit")
        repo.branch("feature/x")
        second = repo.commit("b.txt", "two", "second commit")
        repo.checkout("main")
        merge_sha = repo.merge("feature/x", no_ff=False)
        self.assertEqual(merge_sha, second)

    def test_tag_annotated_and_lightweight(self):
        repo = GitRepo.init()
        self.addCleanup(repo.cleanup)
        repo.commit("a.txt", "one", "first commit")
        repo.tag("v1.0.0", annotated=True, message="release")
        repo.tag("lightweight-tag", annotated=False)
        kinds = repo.run("cat-file", "-t", "v1.0.0").strip()
        self.assertEqual(kinds, "tag")
        kinds_light = repo.run("cat-file", "-t", "lightweight-tag").strip()
        self.assertEqual(kinds_light, "commit")

    def test_cleanup_removes_directory(self):
        repo = GitRepo.init()
        path = repo.path
        repo.cleanup()
        self.assertFalse(subprocess.run(
            ["git", "-C", path, "status"],
            capture_output=True,
        ).returncode == 0)


if __name__ == "__main__":
    unittest.main()
