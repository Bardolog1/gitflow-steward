"""Version registry entry schema: frozen dataclasses with load-time validation."""
import re
from dataclasses import dataclass, field
from pathlib import Path

_KINDS = ("json", "toml", "xml", "ini", "plist", "regex", "text")
_SCOPES = ("root", "members")
_STRIP_MODES = ("hash", "slash", "xml")
_SCHEMES = ("semver", "pep440", "rubygems", "maven", "numeric")
_STATUSES = ("verified", "provisional")


class SchemaError(RuntimeError):
    pass


@dataclass(frozen=True)
class FileSpec:
    glob: str
    kind: str
    key: str | None = None
    pattern: str | None = None
    scope: str = "root"
    strip_comments: str | None = None
    inherits: tuple["Inherit", ...] = ()
    indirect: bool = False
    optional: bool = False

    def __post_init__(self) -> None:
        if self.kind not in _KINDS:
            raise SchemaError(f"invalid kind: {self.kind!r}")
        if self.scope not in _SCOPES:
            raise SchemaError(f"invalid scope: {self.scope!r}")
        if self.strip_comments is not None and self.strip_comments not in _STRIP_MODES:
            raise SchemaError(f"invalid strip_comments: {self.strip_comments!r}")
        if self.kind == "regex":
            _validate_regex_pattern(self.pattern)
        elif self.kind != "text" and self.key is None:
            raise SchemaError(f"{self.kind} kind requires key")


def _validate_regex_pattern(pattern: str | None) -> None:
    if not pattern:
        raise SchemaError("regex kind requires pattern")
    if not pattern.startswith("^"):
        raise SchemaError(f"pattern must be anchored with ^: {pattern!r}")
    if re.compile(pattern).groups != 1:
        raise SchemaError(f"pattern must have exactly one capture group: {pattern!r}")


@dataclass(frozen=True)
class Inherit:
    when: str
    source: FileSpec


@dataclass(frozen=True)
class Entry:
    id: str
    name: str
    status: str
    docs: str
    detect: tuple[str, ...]
    files: tuple[FileSpec, ...]
    scheme: str
    numeric_parts: int | None = None
    tag_derived: tuple[FileSpec, ...] = ()
    dev_marker: str | None = None
    workspace: str | None = None
    extra_agree: tuple[FileSpec, ...] = field(default_factory=tuple)
    excludes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.id:
            raise SchemaError("entry id is required")
        if self.status not in _STATUSES:
            raise SchemaError(f"{self.id}: invalid status: {self.status!r}")
        if not self.docs.startswith("https://"):
            raise SchemaError(f"{self.id}: docs must be an https URL")
        if self.scheme not in _SCHEMES:
            raise SchemaError(f"{self.id}: invalid scheme: {self.scheme!r}")
        if not self.files and not self.tag_derived:
            raise SchemaError(f"{self.id}: requires files or tag_derived")


def validate_fixtures(entries: tuple[Entry, ...], fixtures_root: Path) -> None:
    """Every entry needs a tests/fixtures/versions/<id>/ directory."""
    ids = [entry.id for entry in entries]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        raise SchemaError(f"duplicate registry entry ids: {dupes}")
    missing = [entry.id for entry in entries if not (fixtures_root / entry.id).is_dir()]
    if missing:
        raise SchemaError(f"entries missing fixture directories: {missing}")
