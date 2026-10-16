import unittest

from steward.config import Config
from steward.git import Branch, Commit, RepoState, Tag, collect
from steward.tags import check
from tests.gitrepo import GitRepo


def _commit(sha, parents=(), date="2024-01-01T00:00:00+00:00"):
    return Commit(sha=sha, parents=parents, author_date=date, message="msg")


def _state(branches, tags, commits):
    return RepoState(
        root="/fake",
        head="main",
        head_sha=branches[0].sha,
        branches=tuple(branches),
        tags=tuple(tags),
        commits={c.sha: c for c in commits},
        merge_bases={},
    )


def _check(state, config):
    """Run tags.check with git-free fakes: no version files resolve anywhere."""
    return check(state, config, read_file_at=lambda rev, path: None, tracked_files_at=lambda rev: ())


class AnnotatedTagTests(unittest.TestCase):
    def test_lightweight_tag_found(self):
        c0 = _commit("c0")
        branches = [Branch("main", "c0")]
        tags = [Tag(name="v1.3.0", sha="c0", annotated=False)]
        findings = _check(_state(branches, tags, [c0]), Config())
        hits = [f for f in findings if f.rule == "tag.not-annotated"]
        self.assertEqual(len(hits), 1)


class PlacementTests(unittest.TestCase):
    def test_rc_tag_on_develop(self):
        c0 = _commit("c0")
        branches = [Branch("main", "c0"), Branch("develop", "c0")]
        tags = [Tag(name="v1.4.0-rc.1", sha="c0", annotated=True, tagger_date="2024-01-01T00:00:00+00:00")]
        findings = _check(_state(branches, tags, [c0]), Config())
        hits = [f for f in findings if f.rule == "tag.rc-misplaced"]
        self.assertEqual(len(hits), 1)

    def test_final_tag_off_main(self):
        c0 = _commit("c0")
        release_tip = _commit("r0", parents=("c0",), date="2024-01-02T00:00:00+00:00")
        branches = [Branch("main", "c0"), Branch("release/1.3.0", release_tip.sha)]
        tags = [Tag(name="v1.3.0", sha=release_tip.sha, annotated=True, tagger_date="2024-01-02T00:00:00+00:00")]
        findings = _check(_state(branches, tags, [c0, release_tip]), Config())
        hits = [f for f in findings if f.rule == "tag.final-misplaced"]
        self.assertEqual(len(hits), 1)


class NoReuseTests(unittest.TestCase):
    def test_tag_moved_to_a_different_commit(self):
        c0, c1 = _commit("c0"), _commit("c1", parents=("c0",), date="2024-01-02T00:00:00+00:00")
        branches = [Branch("main", "c1")]
        tags = [
            Tag(name="v1.3.0", sha="c0", annotated=True, tagger_date="2024-01-01T00:00:00+00:00"),
            Tag(name="v1.3.0", sha="c1", annotated=True, tagger_date="2024-01-02T00:00:00+00:00"),
        ]
        findings = _check(_state(branches, tags, [c0, c1]), Config())
        hits = [f for f in findings if f.rule == "tag.reused"]
        self.assertEqual(len(hits), 1)


class MinorIncrementTests(unittest.TestCase):
    def test_skipped_minor_version(self):
        c0 = _commit("c0")
        branches = [Branch("main", "c0")]
        tags = [
            Tag(name="v0.3.0", sha="c0", annotated=True, tagger_date="2024-01-01T00:00:00+00:00"),
            Tag(name="v0.5.0", sha="c0", annotated=True, tagger_date="2024-01-02T00:00:00+00:00"),
        ]
        findings = _check(_state(branches, tags, [c0]), Config())
        hits = [f for f in findings if f.rule == "tag.minor-skip"]
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].subject, "v0.5.0")


class ManifestVersionIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.repo = GitRepo.init()
        self.addCleanup(self.repo.cleanup)

    def test_manifest_and_tag_disagree(self):
        sha = self.repo.commit("package.json", '{"version": "1.2.9"}', "release prep")
        self.repo.tag("v1.3.0", annotated=True, message="release")
        state = collect(self.repo.path)
        findings = check(state, Config())
        hits = [f for f in findings if f.rule == "version.disagree"]
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].subject, "npm")

    def test_manifest_and_tag_agree_no_finding(self):
        self.repo.commit("package.json", '{"version": "1.3.0"}', "release prep")
        self.repo.tag("v1.3.0", annotated=True, message="release")
        state = collect(self.repo.path)
        findings = check(state, Config())
        hits = [f for f in findings if f.rule in ("version.disagree", "version.unresolved")]
        self.assertEqual(hits, [])


class DevelopBumpedIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.repo = GitRepo.init()
        self.addCleanup(self.repo.cleanup)

    def test_develop_version_not_bumped(self):
        self.repo.commit("pyproject.toml", '[project]\nversion = "1.3.0"\n', "release prep")
        self.repo.tag("v1.3.0", annotated=True, message="release")
        self.repo.branch("develop")
        state = collect(self.repo.path)
        findings = check(state, Config())
        hits = [f for f in findings if f.rule == "version.not-bumped"]
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].subject, "python")

    def test_develop_version_bumped_no_finding(self):
        self.repo.commit("pyproject.toml", '[project]\nversion = "1.3.0"\n', "release prep")
        self.repo.tag("v1.3.0", annotated=True, message="release")
        self.repo.branch("develop")
        self.repo.commit("pyproject.toml", '[project]\nversion = "1.4.0.dev0"\n', "bump")
        state = collect(self.repo.path)
        findings = check(state, Config())
        hits = [f for f in findings if f.rule == "version.not-bumped"]
        self.assertEqual(hits, [])


if __name__ == "__main__":
    unittest.main()
