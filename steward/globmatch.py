"""Repo-relative glob matcher. 3.11-safe: no PurePath.full_match."""
import re


def _translate(pattern: str) -> str:
    i, n = 0, len(pattern)
    out = []
    while i < n:
        if pattern[i : i + 3] == "**/":
            out.append("(?:.*/)?")
            i += 3
        elif pattern[i : i + 2] == "**":
            out.append(".*")
            i += 2
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return "^" + "".join(out) + "$"


def compile_glob(pattern: str) -> re.Pattern:
    return re.compile(_translate(pattern))


def match(pattern: str, path: str) -> bool:
    return compile_glob(pattern).match(path) is not None
