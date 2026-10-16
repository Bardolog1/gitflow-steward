"""Version normalization: a Version value and parsers for each registry scheme."""
import re
from dataclasses import dataclass
from functools import total_ordering


class VersionError(RuntimeError):
    pass


_PRE_RANK = {"a": 0, "alpha": 0, "b": 1, "beta": 1, "rc": 2, "c": 2, "pre": 2, "preview": 2}


def _pre_sort_key(pre: tuple[str, int] | None) -> tuple[int, int, int]:
    if pre is None:
        return (1, 0, 0)
    kind, num = pre
    return (0, _PRE_RANK.get(kind.lower(), 2), num)


@total_ordering
@dataclass(frozen=True, eq=False)
class Version:
    """A normalized version. `build` carries stripped metadata; it never affects equality."""

    release: tuple[int, ...]
    pre: tuple[str, int] | None = None
    dev: bool = False
    build: str | None = None

    def _sort_key(self) -> tuple:
        return (self.release, _pre_sort_key(self.pre), 0 if self.dev else 1)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Version):
            return NotImplemented
        return self._sort_key() == other._sort_key()

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Version):
            return NotImplemented
        return self._sort_key() < other._sort_key()

    def __hash__(self) -> int:
        return hash(self._sort_key())


def parse_semver(raw: str) -> Version:
    m = re.match(r"^(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?(?:\+([0-9A-Za-z.-]+))?$", raw.strip())
    if not m:
        raise VersionError(f"invalid semver: {raw!r}")
    release = (int(m.group(1)), int(m.group(2)), int(m.group(3)))
    pre = _split_dotted_pre(m.group(4)) if m.group(4) else None
    return Version(release=release, pre=pre, build=m.group(5))


def _split_dotted_pre(raw: str) -> tuple[str, int]:
    parts = raw.split(".")
    kind = parts[0]
    num = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
    return (kind, num)


_PEP440_PRE_ALIASES = {
    "a": "a", "alpha": "a",
    "b": "b", "beta": "b",
    "rc": "rc", "c": "rc", "pre": "rc", "preview": "rc",
}

_PEP440_RE = re.compile(
    r"^(?:\d+!)?"
    r"(\d+(?:\.\d+)*)"
    r"(?:[-._]?(a|b|c|rc|alpha|beta|pre|preview)[-._]?(\d*))?"
    r"(?:[-._]?dev(\d*))?"
    r"(?:\+([a-zA-Z0-9.]+))?$",
    re.IGNORECASE,
)


def parse_pep440(raw: str) -> Version:
    m = _PEP440_RE.match(raw.strip())
    if not m:
        raise VersionError(f"invalid pep440 version: {raw!r}")
    release = tuple(int(x) for x in m.group(1).split("."))
    pre = None
    if m.group(2):
        kind = _PEP440_PRE_ALIASES[m.group(2).lower()]
        num = int(m.group(3)) if m.group(3) else 0
        pre = (kind, num)
    dev = m.group(4) is not None
    return Version(release=release, pre=pre, dev=dev, build=m.group(5))


def parse_rubygems(raw: str) -> Version:
    s = raw.strip()
    if "-" in s:
        head, _, tail = s.partition("-")
        s = f"{head}.pre.{tail}"
    parts = s.split(".")
    release_parts: list[int] = []
    i = 0
    while i < len(parts) and parts[i].isdigit():
        release_parts.append(int(parts[i]))
        i += 1
    if not release_parts:
        raise VersionError(f"invalid rubygems version: {raw!r}")
    pre = None
    if i < len(parts):
        kind = parts[i]
        num = int(parts[i + 1]) if i + 1 < len(parts) and parts[i + 1].isdigit() else 0
        pre = (kind, num)
    return Version(release=tuple(release_parts), pre=pre)


def parse_maven(raw: str) -> Version:
    m = re.match(r"^(\d+(?:\.\d+)*)(?:-(.+))?$", raw.strip())
    if not m:
        raise VersionError(f"invalid maven version: {raw!r}")
    release = tuple(int(x) for x in m.group(1).split("."))
    qualifier = m.group(2)
    dev = bool(qualifier) and qualifier.upper() == "SNAPSHOT"
    pre = (qualifier.lower(), 0) if qualifier and not dev else None
    return Version(release=release, pre=pre, dev=dev)


def parse_numeric(raw: str, numeric_parts: int | None = None) -> Version:
    segments = raw.strip().split(".")
    if numeric_parts is not None and len(segments) > numeric_parts:
        raise VersionError(f"too many numeric parts in {raw!r}: expected <= {numeric_parts}")
    try:
        release = tuple(int(x) for x in segments)
    except ValueError as exc:
        raise VersionError(f"invalid numeric version: {raw!r}") from exc
    return Version(release=release)


_PARSERS = {
    "semver": lambda raw, numeric_parts: parse_semver(raw),
    "pep440": lambda raw, numeric_parts: parse_pep440(raw),
    "rubygems": lambda raw, numeric_parts: parse_rubygems(raw),
    "maven": lambda raw, numeric_parts: parse_maven(raw),
    "numeric": lambda raw, numeric_parts: parse_numeric(raw, numeric_parts),
}


def parse(scheme: str, raw: str, *, numeric_parts: int | None = None) -> Version:
    try:
        parser = _PARSERS[scheme]
    except KeyError as exc:
        raise VersionError(f"unknown scheme: {scheme!r}") from exc
    return parser(raw, numeric_parts)
