"""Tag-and-version-audit analyzer: tag placement, naming, and the version-registry checks."""
import re

from steward.config import Config
from steward.git import GitRunner, RepoState
from steward.model import Finding, Severity
from steward.versions import registry, schemes
from steward.versions.readers import ReadError

_FINAL_RE = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")
_RC_RE = re.compile(r"^v\d+\.\d+\.\d+-rc\.\d+$")


def _ancestors(sha, commits):
    seen, stack = set(), [sha]
    while stack:
        s = stack.pop()
        if s in seen or s not in commits:
            continue
        seen.add(s)
        stack.extend(commits[s].parents)
    return seen


def _check_annotated(state: RepoState) -> list[Finding]:
    findings = []
    for tag in state.tags:
        if (_FINAL_RE.match(tag.name) or _RC_RE.match(tag.name)) and not tag.annotated:
            findings.append(Finding(
                rule="tag.not-annotated",
                severity=Severity.FAIL,
                subject=tag.name,
                message=f"{tag.name} is a lightweight tag; release tags must be annotated",
            ))
    return findings


def _check_placement(state: RepoState, release_ancestors_by_name: dict) -> list[Finding]:
    findings = []
    main = next((b for b in state.branches if b.name == "main"), None)
    main_ancestors = _ancestors(main.sha, state.commits) if main else set()
    for tag in state.tags:
        if _RC_RE.match(tag.name):
            on_release = any(tag.sha in anc for anc in release_ancestors_by_name.values())
            if not on_release:
                findings.append(Finding(
                    rule="tag.rc-misplaced",
                    severity=Severity.FAIL,
                    subject=tag.name,
                    message=f"{tag.name} does not point to a commit reachable from any release/* branch",
                ))
        elif _FINAL_RE.match(tag.name):
            if tag.sha not in main_ancestors:
                findings.append(Finding(
                    rule="tag.final-misplaced",
                    severity=Severity.FAIL,
                    subject=tag.name,
                    message=f"{tag.name} does not point to a commit reachable from main",
                ))
    return findings


def _check_no_reuse(state: RepoState) -> list[Finding]:
    by_name: dict[str, set[str]] = {}
    for tag in state.tags:
        by_name.setdefault(tag.name, set()).add(tag.sha)
    findings = []
    for name, shas in by_name.items():
        if len(shas) > 1:
            findings.append(Finding(
                rule="tag.reused",
                severity=Severity.FAIL,
                subject=name,
                message=f"{name} has pointed to more than one commit",
                evidence={"commits": ",".join(sorted(shas))},
            ))
    return findings


def _check_minor_increment(state: RepoState) -> list[Finding]:
    finals = sorted(
        (m for t in state.tags if (m := _FINAL_RE.match(t.name))),
        key=lambda m: (int(m.group(1)), int(m.group(2)), int(m.group(3))),
    )
    pre_one_oh = [m for m in finals if int(m.group(1)) == 0]
    findings = []
    for prev, curr in zip(pre_one_oh, pre_one_oh[1:]):
        prev_minor, curr_minor = int(prev.group(2)), int(curr.group(2))
        if curr_minor != prev_minor + 1:
            findings.append(Finding(
                rule="tag.minor-skip",
                severity=Severity.FAIL,
                subject=curr.group(0),
                message=f"{curr.group(0)} skips a MINOR version after {prev.group(0)}",
            ))
    return findings


def _check_manifest_matches_tag(state: RepoState, config: Config, read_file_at, tracked_files_at) -> list[Finding]:
    findings = []
    entries = registry.load(state.root)
    final_tags = [t for t in state.tags if _FINAL_RE.match(t.name)]
    for tag in final_tags:
        tag_version = schemes.parse("semver", tag.name[1:])
        read_file = lambda glob, _rev=tag.sha: read_file_at(_rev, glob)
        tracked = tracked_files_at(tag.sha)
        for entry in entries:
            if not registry.detect(entry, tracked):
                continue
            try:
                if registry.is_tag_derived(entry, read_file):
                    findings.append(Finding(
                        rule="version.tag-derived",
                        severity=Severity.INFO,
                        subject=entry.id,
                        message=f"{entry.name} version is tag-derived at {tag.name}",
                    ))
                    continue
                manifest_version = registry.agree(entry, read_file)
            except ReadError as exc:
                findings.append(Finding(
                    rule="version.unresolved",
                    severity=registry.gate(entry, Severity.FAIL),
                    subject=entry.id,
                    message=f"{entry.name} at {tag.name}: {exc}",
                ))
                continue
            if manifest_version != tag_version:
                findings.append(Finding(
                    rule="version.disagree",
                    severity=registry.gate(entry, Severity.FAIL),
                    subject=entry.id,
                    message=f"{entry.name} manifest version does not match tag {tag.name}",
                    evidence={"tag": tag.name},
                ))
    return findings


def _last_final_tag(state: RepoState, main_ancestors: set[str]):
    finals = [t for t in state.tags if _FINAL_RE.match(t.name) and t.sha in main_ancestors]
    if not finals:
        return None
    return max(finals, key=lambda t: t.tagger_date or "")


def _check_develop_bumped(state: RepoState, config: Config, read_file_at, tracked_files_at) -> list[Finding]:
    develop = next((b for b in state.branches if b.name == "develop"), None)
    main = next((b for b in state.branches if b.name == "main"), None)
    if develop is None or main is None:
        return []
    main_ancestors = _ancestors(main.sha, state.commits)
    last = _last_final_tag(state, main_ancestors)
    if last is None:
        return []
    last_version = schemes.parse("semver", last.name[1:])
    entries = registry.load(state.root)
    tracked = tracked_files_at(develop.sha)
    read_file = lambda glob: read_file_at(develop.sha, glob)
    findings = []
    for entry in entries:
        if entry.dev_marker is None or not registry.detect(entry, tracked):
            continue
        try:
            develop_version = registry.agree(entry, read_file)
        except ReadError:
            continue
        if not (develop_version > last_version):
            findings.append(Finding(
                rule="version.not-bumped",
                severity=registry.gate(entry, Severity.FAIL),
                subject=entry.id,
                message=f"develop's {entry.name} version is not strictly greater than {last.name}",
            ))
    return findings


def check(
    state: RepoState,
    config: Config,
    *,
    read_file_at=None,
    tracked_files_at=None,
) -> list[Finding]:
    """Run every tag-and-version-audit rule against one RepoState snapshot.

    `read_file_at(rev, path)` and `tracked_files_at(rev)` read version-manifest
    content at an arbitrary rev; they default to `GitRunner(state.root)` so the
    CLI can call `check(state, config)` directly, but tests can inject fakes
    to stay git-free, matching how `registry.resolve()` takes a `read_file` callback.
    """
    if read_file_at is None:
        read_file_at = GitRunner(state.root).show
    if tracked_files_at is None:
        tracked_files_at = GitRunner(state.root).ls_tree

    release_ancestors_by_name = {
        b.name: _ancestors(b.sha, state.commits)
        for b in state.branches if b.name.startswith("release/")
    }
    findings: list[Finding] = []
    findings.extend(_check_annotated(state))
    findings.extend(_check_placement(state, release_ancestors_by_name))
    findings.extend(_check_no_reuse(state))
    findings.extend(_check_minor_increment(state))
    findings.extend(_check_manifest_matches_tag(state, config, read_file_at, tracked_files_at))
    findings.extend(_check_develop_bumped(state, config, read_file_at, tracked_files_at))
    return findings
