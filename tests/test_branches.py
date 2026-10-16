import unittest
from itertools import combinations

from steward.branches import check
from steward.config import Config
from steward.git import Branch, Commit, RepoState, Tag


def _commit(sha, parents=(), date="2024-01-01T00:00:00+00:00", message="msg"):
    return Commit(sha=sha, parents=parents, author_date=date, message=message)


def _state(branches, tags, commits, head="main"):
    commits_dict = {c.sha: c for c in commits}
    names = tuple(sorted(b.name for b in branches))
    merge_bases = {}
    shas = {b.name: b.sha for b in branches}
    for a, b in combinations(names, 2):
        merge_bases[tuple(sorted((a, b)))] = _merge_base(commits_dict, shas[a], shas[b])
    head_branch = next((b for b in branches if b.name == head), branches[0])
    return RepoState(
        root="/fake",
        head=head,
        head_sha=head_branch.sha,
        branches=tuple(branches),
        tags=tuple(tags),
        commits=commits_dict,
        merge_bases=merge_bases,
    )


def _ancestors(sha, commits):
    seen, stack = set(), [sha]
    while stack:
        s = stack.pop()
        if s in seen or s not in commits:
            continue
        seen.add(s)
        stack.extend(commits[s].parents)
    return seen


def _merge_base(commits, a, b):
    anc_a, anc_b = _ancestors(a, commits), _ancestors(b, commits)
    common = anc_a & anc_b
    if not common:
        return None
    # pick the one with the latest date among commits still reachable from both
    return max(common, key=lambda s: commits[s].author_date)


class BugfixFromDevelopTests(unittest.TestCase):
    def test_bugfix_branched_from_develop_instead_of_release(self):
        c0 = _commit("c0", date="2024-01-01T00:00:00+00:00")
        c1 = _commit("c1", parents=("c0",), date="2024-01-02T00:00:00+00:00")
        release_tip = _commit("r0", parents=("c1",), date="2024-01-03T00:00:00+00:00")
        bugfix_tip = _commit("bf0", parents=("c1",), date="2024-01-04T00:00:00+00:00")
        branches = [
            Branch("main", "c0"),
            Branch("develop", c1.sha),
            Branch("release/1.3.0", release_tip.sha),
            Branch("bugfix/typo-fix", bugfix_tip.sha),
        ]
        state = _state(branches, [], [c0, c1, release_tip, bugfix_tip])
        findings = check(state, Config())
        mismatches = [f for f in findings if f.rule == "branch.origin-mismatch" and f.subject == "bugfix/typo-fix"]
        self.assertEqual(len(mismatches), 1)
        self.assertEqual(mismatches[0].evidence["actual_origin"], "develop")


class DirectCommitTests(unittest.TestCase):
    def test_direct_commit_on_release_branch(self):
        c0 = _commit("c0")
        direct = _commit("d0", parents=("c0",), date="2024-01-02T00:00:00+00:00")
        branches = [Branch("main", "c0"), Branch("develop", "c0"), Branch("release/1.3.0", direct.sha)]
        state = _state(branches, [], [c0, direct])
        findings = check(state, Config())
        hits = [f for f in findings if f.rule == "branch.direct-commit"]
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].evidence["commit"], "d0")


class FastForwardTests(unittest.TestCase):
    def test_fast_forward_merge_into_develop(self):
        base = _commit("c0")
        feature_tip = _commit("f0", parents=("c0",), date="2024-01-02T00:00:00+00:00")
        branches = [
            Branch("main", "c0"),
            Branch("develop", feature_tip.sha),
            Branch("feature/x", feature_tip.sha),
        ]
        state = _state(branches, [], [base, feature_tip])
        findings = check(state, Config())
        hits = [f for f in findings if f.rule == "branch.fast-forward-merge"]
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].subject, "develop")


class BackMergeTests(unittest.TestCase):
    def test_promotion_without_back_merge(self):
        c0 = _commit("c0")
        release_tip = _commit("r0", parents=("c0",), date="2024-01-02T00:00:00+00:00")
        merge_to_main = _commit("m0", parents=("c0", "r0"), date="2024-01-03T00:00:00+00:00")
        branches = [
            Branch("main", merge_to_main.sha),
            Branch("develop", "c0"),
            Branch("release/1.3.0", release_tip.sha),
        ]
        state = _state(branches, [], [c0, release_tip, merge_to_main])
        findings = check(state, Config())
        hits = [f for f in findings if f.rule == "branch.missing-back-merge"]
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].subject, "release/1.3.0")


class OpenReleaseCountTests(unittest.TestCase):
    def test_two_open_release_branches(self):
        c0 = _commit("c0")
        r1 = _commit("r1", parents=("c0",), date="2024-01-02T00:00:00+00:00")
        r2 = _commit("r2", parents=("c0",), date="2024-01-03T00:00:00+00:00")
        branches = [
            Branch("main", "c0"),
            Branch("develop", "c0"),
            Branch("release/1.3.0", r1.sha),
            Branch("release/1.4.0", r2.sha),
        ]
        state = _state(branches, [], [c0, r1, r2])
        findings = check(state, Config())
        hits = [f for f in findings if f.rule == "branch.multiple-open-releases"]
        self.assertEqual(len(hits), 1)


class DriftTests(unittest.TestCase):
    def test_develop_ahead_of_last_release(self):
        c0 = _commit("c0")
        d1 = _commit("d1", parents=("c0",), date="2024-01-02T00:00:00+00:00")
        d2 = _commit("d2", parents=("d1",), date="2024-01-03T00:00:00+00:00")
        d3 = _commit("d3", parents=("d2",), date="2024-01-04T00:00:00+00:00")
        d4 = _commit("d4", parents=("d3",), date="2024-01-05T00:00:00+00:00")
        d5 = _commit("d5", parents=("d4",), date="2024-01-06T00:00:00+00:00")
        branches = [Branch("main", "c0"), Branch("develop", "d5")]
        tags = [Tag(name="v1.2.0", sha="c0", annotated=True, tagger_date="2024-01-01T00:00:00+00:00")]
        state = _state(branches, tags, [c0, d1, d2, d3, d4, d5])
        findings = check(state, Config())
        hits = [f for f in findings if f.rule == "branch.drift"]
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].evidence["ahead"], "5")
        self.assertEqual(hits[0].evidence["behind"], "0")


class StaleCleanupTests(unittest.TestCase):
    def test_merged_feature_branch_left_behind(self):
        c0 = _commit("c0")
        feature_tip = _commit("f0", parents=("c0",), date="2024-01-02T00:00:00+00:00")
        merge = _commit("m0", parents=("c0", "f0"), date="2024-01-03T00:00:00+00:00")
        branches = [
            Branch("main", "c0"),
            Branch("develop", merge.sha),
            Branch("feature/old-work", feature_tip.sha),
        ]
        state = _state(branches, [], [c0, feature_tip, merge])
        findings = check(state, Config())
        hits = [f for f in findings if f.rule == "branch.pending-cleanup" and f.subject == "feature/old-work"]
        self.assertEqual(len(hits), 1)
        delete_calls = [f for f in findings if "delete" in f.message.lower()]
        self.assertEqual(delete_calls, [])


if __name__ == "__main__":
    unittest.main()
