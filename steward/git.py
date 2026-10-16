"""Read-only git access: a subprocess runner and a RepoState snapshot builder."""
import os
import subprocess
from dataclasses import dataclass, field
from itertools import combinations

_RS = "\x1e"
_FS = "\x1f"


class GitError(RuntimeError):
    pass


class GitRunner:
    """Runs git read-only against one repository root."""

    def __init__(self, root: str):
        self.root = root

    def run(self, *args: str) -> str:
        env = dict(os.environ)
        env["GIT_TERMINAL_PROMPT"] = "0"
        result = subprocess.run(
            ["git", "-C", self.root, "-c", "core.quotepath=off", *args],
            capture_output=True,
            env=env,
        )
        if result.returncode != 0:
            raise GitError(result.stderr.decode("utf-8", "replace").strip())
        return result.stdout.decode("utf-8", "replace").replace("\r\n", "\n")

    def show(self, rev: str, path: str) -> str | None:
        """Read a file's content at a rev, straight from the git object. None if absent there."""
        try:
            return self.run("show", f"{rev}:{path}")
        except GitError:
            return None

    def ls_tree(self, rev: str) -> tuple[str, ...]:
        """Tracked file paths at a rev (read-only; never touches the working tree)."""
        out = self.run("ls-tree", "-r", "--name-only", "-z", rev)
        return tuple(p for p in out.split("\x00") if p)


@dataclass(frozen=True)
class Commit:
    sha: str
    parents: tuple[str, ...]
    author_date: str
    message: str


@dataclass(frozen=True)
class Branch:
    name: str
    sha: str


@dataclass(frozen=True)
class Tag:
    name: str
    sha: str
    annotated: bool
    tagger_date: str | None = None


@dataclass(frozen=True)
class RepoState:
    root: str
    head: str
    head_sha: str
    branches: tuple[Branch, ...]
    tags: tuple[Tag, ...]
    commits: dict[str, Commit] = field(default_factory=dict)
    merge_bases: dict[tuple[str, str], str | None] = field(default_factory=dict)


def _branches(runner: GitRunner) -> tuple[Branch, ...]:
    out = runner.run("for-each-ref", f"--format=%(refname:short){_FS}%(objectname)", "refs/heads/")
    branches = []
    for line in out.splitlines():
        if not line:
            continue
        name, sha = line.split(_FS)
        branches.append(Branch(name=name, sha=sha))
    return tuple(branches)


def _tags(runner: GitRunner) -> tuple[Tag, ...]:
    fmt = f"%(refname:short){_FS}%(objectname){_FS}%(objecttype){_FS}%(*objectname){_FS}%(creatordate:iso-strict)"
    out = runner.run("for-each-ref", f"--format={fmt}", "refs/tags/")
    tags = []
    for line in out.splitlines():
        if not line:
            continue
        name, objectname, objecttype, peeled, creatordate = line.split(_FS)
        annotated = objecttype == "tag"
        sha = peeled if annotated else objectname
        tags.append(Tag(name=name, sha=sha, annotated=annotated, tagger_date=creatordate or None if annotated else None))
    return tuple(tags)


def _head(runner: GitRunner) -> tuple[str, str]:
    try:
        name = runner.run("symbolic-ref", "--short", "HEAD").strip()
    except GitError:
        name = runner.run("rev-parse", "HEAD").strip()
    sha = runner.run("rev-parse", "HEAD").strip()
    return name, sha


def _commits(runner: GitRunner) -> dict[str, Commit]:
    fmt = f"%H{_FS}%P{_FS}%aI{_FS}%s{_RS}"
    out = runner.run("log", "--all", f"--format={fmt}")
    commits: dict[str, Commit] = {}
    for record in out.split(_RS):
        record = record.strip("\n")
        if not record:
            continue
        sha, parents, author_date, message = record.split(_FS)
        commits[sha] = Commit(
            sha=sha,
            parents=tuple(parents.split()) if parents else (),
            author_date=author_date,
            message=message,
        )
    return commits


def _merge_bases(runner: GitRunner, branch_names: tuple[str, ...]) -> dict[tuple[str, str], str | None]:
    bases: dict[tuple[str, str], str | None] = {}
    for a, b in combinations(sorted(branch_names), 2):
        try:
            bases[(a, b)] = runner.run("merge-base", a, b).strip()
        except GitError:
            bases[(a, b)] = None
    return bases


def commit_subjects_between(root: str, from_rev: str, to_rev: str) -> tuple[tuple[str, str], ...]:
    """`(sha, subject)` pairs reachable from `to_rev` but not `from_rev`, newest first."""
    runner = GitRunner(root)
    fmt = f"%H{_FS}%s{_RS}"
    out = runner.run("log", f"{from_rev}..{to_rev}", f"--format={fmt}")
    result = []
    for record in out.split(_RS):
        record = record.strip("\n")
        if not record:
            continue
        sha, subject = record.split(_FS)
        result.append((sha, subject))
    return tuple(result)


def collect(root: str) -> RepoState:
    """Build one frozen RepoState snapshot. Analyzers read this; they never call git."""
    runner = GitRunner(root)
    head, head_sha = _head(runner)
    branches = _branches(runner)
    tags = _tags(runner)
    commits = _commits(runner)
    merge_bases = _merge_bases(runner, tuple(b.name for b in branches))
    return RepoState(
        root=root,
        head=head,
        head_sha=head_sha,
        branches=branches,
        tags=tags,
        commits=commits,
        merge_bases=merge_bases,
    )
