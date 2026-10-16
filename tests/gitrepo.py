"""Fixture builder for integration tests: real git repositories in temp dirs."""
import shutil
import subprocess
import tempfile
from pathlib import Path


class GitRepo:
    """A disposable git repository used to exercise analyzers end to end."""

    def __init__(self, path: str):
        self.path = path
        self.path_obj = Path(path)

    @classmethod
    def init(cls, initial_branch: str = "main") -> "GitRepo":
        path = tempfile.mkdtemp(prefix="gs test ")
        repo = cls(path)
        repo.run("init", "--initial-branch", initial_branch)
        repo.run("config", "user.email", "fixture@example.invalid")
        repo.run("config", "user.name", "Fixture")
        return repo

    def run(self, *args: str) -> str:
        result = subprocess.run(
            ["git", "-C", self.path, *args],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout

    def commit(self, filename: str, content: str, message: str) -> str:
        target = self.path_obj / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        self.run("add", filename)
        self.run("commit", "-m", message)
        return self.head()

    def branch(self, name: str) -> None:
        self.run("checkout", "-b", name)

    def checkout(self, name: str) -> None:
        self.run("checkout", name)

    def merge(self, branch: str, no_ff: bool) -> str:
        if no_ff:
            self.run("merge", "--no-ff", branch, "-m", f"merge {branch}")
        else:
            self.run("merge", "--ff-only", branch)
        return self.head()

    def tag(self, name: str, annotated: bool, message: str = "") -> None:
        if annotated:
            self.run("tag", "-a", name, "-m", message or name)
        else:
            self.run("tag", name)

    def head(self) -> str:
        return self.run("rev-parse", "HEAD").strip()

    def current_branch(self) -> str:
        return self.run("symbolic-ref", "--short", "HEAD").strip()

    def cleanup(self) -> None:
        shutil.rmtree(self.path, ignore_errors=True)
