"""Branch-audit analyzer: origin, direct commits, FF merges, back-merge, open releases, drift, cleanup."""
import re
from datetime import datetime, timedelta, timezone

from steward.config import Config
from steward.git import RepoState
from steward.model import Finding, Severity

_STALE_DAYS_DEFAULT = 90
_FINAL_TAG_RE = re.compile(r"^v\d+\.\d+\.\d+$")
_SOURCE_PREFIXES = ("feature/", "bugfix/", "hotfix/")


def _ancestors(sha: str | None, commits: dict) -> set[str]:
    if sha is None:
        return set()
    seen: set[str] = set()
    stack = [sha]
    while stack:
        s = stack.pop()
        if s in seen or s not in commits:
            continue
        seen.add(s)
        stack.extend(commits[s].parents)
    return seen


def _merge_base(state: RepoState, a: str, b: str) -> str | None:
    if a == b:
        return None
    return state.merge_bases.get(tuple(sorted((a, b))))


def _mainline_unique(state: RepoState, tip_sha: str, fork_sha: str) -> list:
    out = []
    sha: str | None = tip_sha
    while sha and sha != fork_sha:
        commit = state.commits.get(sha)
        if commit is None:
            break
        out.append(commit)
        sha = commit.parents[0] if commit.parents else None
    return out


def _expected_origins(name: str, open_release_names: tuple[str, ...]) -> tuple[str, ...] | None:
    if name.startswith("feature/") or name.startswith("release/"):
        return ("develop",)
    if name.startswith("bugfix/"):
        return open_release_names
    if name.startswith("hotfix/"):
        return ("main",)
    return None


def _check_origins(state: RepoState, by_name: dict, open_release_names: tuple[str, ...]) -> list[Finding]:
    findings = []
    candidates = [n for n in by_name if n in ("develop", "main") or n.startswith("release/")]
    for name, branch in by_name.items():
        expected = _expected_origins(name, open_release_names)
        if expected is None:
            continue
        best_parent, best_date = None, None
        for cand in candidates:
            if cand == name:
                continue
            base = _merge_base(state, name, cand)
            commit = state.commits.get(base) if base else None
            if commit is None:
                continue
            if best_date is None or commit.author_date > best_date:
                best_date, best_parent = commit.author_date, cand
        if best_parent is not None and best_parent not in expected:
            findings.append(Finding(
                rule="branch.origin-mismatch",
                severity=Severity.FAIL,
                subject=name,
                message=f"{name} appears to originate from {best_parent}, expected one of {expected}",
                evidence={"actual_origin": best_parent, "expected": ",".join(expected)},
            ))
    return findings


def _check_direct_commits(state: RepoState, branch) -> list[Finding]:
    fork = _merge_base(state, branch.name, "develop")
    if fork is None:
        return []
    findings = []
    for commit in _mainline_unique(state, branch.sha, fork):
        if len(commit.parents) < 2:
            findings.append(Finding(
                rule="branch.direct-commit",
                severity=Severity.FAIL,
                subject=branch.name,
                message=f"direct commit on {branch.name}: {commit.sha}",
                evidence={"commit": commit.sha},
            ))
    return findings


def _check_non_ff(state: RepoState, by_name: dict, protected_name: str) -> list[Finding]:
    protected = by_name.get(protected_name)
    if protected is None:
        return []
    commit = state.commits.get(protected.sha)
    if commit is None or len(commit.parents) >= 2:
        return []
    findings = []
    for name, branch in by_name.items():
        # ponytail: equality only (not ancestor-of), so a shared root commit
        # on every branch never counts as evidence of a fast-forward.
        if not name.startswith(_SOURCE_PREFIXES) or name == protected_name:
            continue
        if protected.sha == branch.sha:
            findings.append(Finding(
                rule="branch.fast-forward-merge",
                severity=Severity.FAIL,
                subject=protected_name,
                message=f"{protected_name} advanced by fast-forwarding {name} instead of a --no-ff merge",
                evidence={"source": name, "commit": protected.sha},
            ))
            break
    return findings


def _check_back_merge(state: RepoState, by_name: dict, release_branches: tuple) -> list[Finding]:
    main = by_name.get("main")
    develop = by_name.get("develop")
    if main is None or develop is None:
        return []
    main_ancestors = _ancestors(main.sha, state.commits)
    develop_ancestors = _ancestors(develop.sha, state.commits)
    findings = []
    for branch in release_branches:
        if branch.sha not in main_ancestors:
            continue
        if branch.sha not in develop_ancestors:
            findings.append(Finding(
                rule="branch.missing-back-merge",
                severity=Severity.FAIL,
                subject=branch.name,
                message=f"{branch.name} was promoted to main but is not reachable from develop",
            ))
    return findings


def _check_open_release_count(open_releases: tuple) -> list[Finding]:
    if len(open_releases) <= 1:
        return []
    names = ", ".join(b.name for b in open_releases)
    return [Finding(
        rule="branch.multiple-open-releases",
        severity=Severity.FAIL,
        subject=names,
        message=f"more than one open release branch: {names}",
    )]


def _check_drift(state: RepoState, by_name: dict) -> list[Finding]:
    develop = by_name.get("develop")
    main = by_name.get("main")
    if develop is None or main is None:
        return []
    main_ancestors = _ancestors(main.sha, state.commits)
    final_tags = [t for t in state.tags if _FINAL_TAG_RE.match(t.name) and t.sha in main_ancestors]
    if not final_tags:
        return []
    latest = max(final_tags, key=lambda t: t.tagger_date or "")
    develop_ancestors = _ancestors(develop.sha, state.commits)
    tag_ancestors = _ancestors(latest.sha, state.commits)
    ahead = len(develop_ancestors - tag_ancestors)
    behind = len(tag_ancestors - develop_ancestors)
    return [Finding(
        rule="branch.drift",
        severity=Severity.INFO,
        subject="develop",
        message=f"develop is {ahead} commit(s) ahead of and {behind} behind {latest.name}",
        evidence={"ahead": str(ahead), "behind": str(behind), "tag": latest.name},
    )]


def _check_stale_and_cleanup(state: RepoState, by_name: dict, config: Config) -> list[Finding]:
    findings: list[Finding] = []
    develop = by_name.get("develop")
    main = by_name.get("main")
    now = datetime.now(timezone.utc)
    threshold = timedelta(days=_STALE_DAYS_DEFAULT)
    for name, branch in by_name.items():
        if not name.startswith(_SOURCE_PREFIXES):
            continue
        commit = state.commits.get(branch.sha)
        if commit is not None:
            try:
                last = datetime.fromisoformat(commit.author_date)
            except ValueError:
                last = None
            if last is not None and now - last > threshold:
                findings.append(Finding(
                    rule="branch.stale",
                    severity=Severity.WARN,
                    subject=name,
                    message=f"{name} has no commits in over {_STALE_DAYS_DEFAULT} days",
                ))
        target = main if name.startswith("hotfix/") else develop
        if target is not None:
            target_ancestors = _ancestors(target.sha, state.commits)
            if branch.sha in target_ancestors:
                findings.append(Finding(
                    rule="branch.pending-cleanup",
                    severity=Severity.INFO,
                    subject=name,
                    message=f"{name} is fully merged and still present",
                ))
    return findings


def check(state: RepoState, config: Config) -> list[Finding]:
    """Run every branch-audit rule against one RepoState snapshot."""
    by_name = {b.name: b for b in state.branches}
    main = by_name.get("main")
    release_branches = tuple(b for b in state.branches if b.name.startswith("release/"))
    main_ancestors = _ancestors(main.sha, state.commits) if main else set()
    open_releases = tuple(b for b in release_branches if b.sha not in main_ancestors)
    open_release_names = tuple(b.name for b in open_releases)

    findings: list[Finding] = []
    findings.extend(_check_origins(state, by_name, open_release_names))
    for branch in release_branches:
        findings.extend(_check_direct_commits(state, branch))
    for name in ("develop", "main") + tuple(b.name for b in release_branches):
        findings.extend(_check_non_ff(state, by_name, name))
    findings.extend(_check_back_merge(state, by_name, release_branches))
    findings.extend(_check_open_release_count(open_releases))
    findings.extend(_check_drift(state, by_name))
    findings.extend(_check_stale_and_cleanup(state, by_name, config))
    return findings
