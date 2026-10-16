"""Conventional Commits parser and grouping for automatic-mode release notes."""
import re
from collections.abc import Iterable, Sequence

BREAKING = "Breaking"
FEATURES = "Features"
FIXES = "Fixes"
PERFORMANCE = "Performance"
OTHER = "Other"

GROUP_ORDER = (BREAKING, FEATURES, FIXES, PERFORMANCE, OTHER)

_TYPE_GROUPS = {"feat": FEATURES, "fix": FIXES, "perf": PERFORMANCE}
_SKIP_TYPES = {"chore", "ci", "build"}
_PATTERN = re.compile(r"^(?P<type>[a-zA-Z]+)(?:\([^)]*\))?(?P<bang>!)?:\s*(?P<desc>.+)$")


def group_commits(commits: Iterable[Sequence[str]]) -> dict[str, tuple[str, ...]]:
    """Groups `(sha, subject)` pairs by Conventional Commits type.

    `chore`/`ci`/`build` are dropped unless marked breaking (`!`).
    """
    groups: dict[str, list[str]] = {key: [] for key in GROUP_ORDER}
    for _sha, subject in commits:
        match = _PATTERN.match(subject)
        if match is None:
            groups[OTHER].append(subject)
            continue
        commit_type = match.group("type").lower()
        desc = match.group("desc").strip()
        if match.group("bang"):
            groups[BREAKING].append(desc)
            continue
        if commit_type in _SKIP_TYPES:
            continue
        groups[_TYPE_GROUPS.get(commit_type, OTHER)].append(desc)
    return {key: tuple(value) for key, value in groups.items() if value}
