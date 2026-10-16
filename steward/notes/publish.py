"""Finished-notes publishing: writes the file always, reports gh availability.

Actually creating a `gh release` is a guarded, approval-gated action for the
release-operator agent (push_guard asks for it) -- this function only
prepares the artifact and the availability signal that decision needs.
"""
from pathlib import Path

from steward import gh


def publish(notes_text: str, *, repo_root: str, filename: str = "RELEASE_NOTES.md") -> dict:
    path = Path(repo_root, filename)
    path.write_text(notes_text, encoding="utf-8")
    return {"file": str(path), "gh_available": gh.is_available()}
