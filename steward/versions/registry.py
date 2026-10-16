"""Version registry: load entries, detect files, resolve inheritance, check agreement, gate severity."""
import re
import tomllib
from pathlib import Path

from steward import globmatch
from steward.model import Severity
from steward.versions import readers, schemes
from steward.versions.readers import ReadError
from steward.versions.schema import Entry, FileSpec, Inherit, SchemaError

_BUILTIN_REGISTRY_DIR = Path(__file__).parent / "registry"

_GLOBAL_EXCLUDES = (
    "*.lock",
    "*-lock.json",
    "*-lock.yaml",
    "dist/**",
    "build/**",
    "target/**",
    "node_modules/**",
)


class UnresolvedError(ReadError):
    pass


class DisagreementError(ReadError):
    def __init__(self, values: dict[str, str]):
        self.values = values
        super().__init__(f"versions disagree: {values}")


def _filespec_from_dict(data: dict) -> FileSpec:
    inherits = tuple(
        Inherit(when=item["when"], source=_filespec_from_dict(item["source"]))
        for item in data.get("inherits", ())
    )
    return FileSpec(
        glob=data["glob"],
        kind=data["kind"],
        key=data.get("key"),
        pattern=data.get("pattern"),
        scope=data.get("scope", "root"),
        strip_comments=data.get("strip_comments"),
        inherits=inherits,
        indirect=data.get("indirect", False),
        optional=data.get("optional", False),
    )


def _entry_from_dict(data: dict, *, default_status: str) -> Entry:
    return Entry(
        id=data["id"],
        name=data["name"],
        status=data.get("status", default_status),
        docs=data["docs"],
        detect=tuple(data["detect"]),
        files=tuple(_filespec_from_dict(f) for f in data.get("files", ())),
        scheme=data["scheme"],
        numeric_parts=data.get("numeric_parts"),
        tag_derived=tuple(_filespec_from_dict(f) for f in data.get("tag_derived", ())),
        dev_marker=data.get("dev_marker"),
        workspace=data.get("workspace"),
        extra_agree=tuple(_filespec_from_dict(f) for f in data.get("extra_agree", ())),
        excludes=tuple(data.get("excludes", ())),
    )


def load(root: str, *, registry_dir: Path | None = None) -> tuple[Entry, ...]:
    """Read built-in registry/*.toml plus .gitflow.toml [[versions.entry]] extensions."""
    registry_dir = registry_dir if registry_dir is not None else _BUILTIN_REGISTRY_DIR
    entries: list[Entry] = []
    for toml_path in sorted(registry_dir.glob("*.toml")):
        data = tomllib.loads(toml_path.read_text(encoding="utf-8"))
        for raw_entry in data.get("entry", ()):
            entries.append(_entry_from_dict(raw_entry, default_status="verified"))

    config_path = Path(root) / ".gitflow.toml"
    if config_path.exists():
        data = tomllib.loads(config_path.read_text(encoding="utf-8"))
        for raw_entry in data.get("versions", {}).get("entry", ()):
            entries.append(_entry_from_dict(raw_entry, default_status="provisional"))

    _validate_unique_ids(entries)
    return tuple(entries)


def _validate_unique_ids(entries: list[Entry]) -> None:
    ids = [entry.id for entry in entries]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        raise SchemaError(f"duplicate registry entry ids: {dupes}")


def detect(entry: Entry, tracked_files: tuple[str, ...]) -> tuple[str, ...]:
    """Tracked files matching entry.detect, after global and entry-level excludes."""
    excludes = _GLOBAL_EXCLUDES + entry.excludes
    matches = []
    for path in tracked_files:
        if any(globmatch.match(pattern, path) for pattern in excludes):
            continue
        if any(globmatch.match(pattern, path) for pattern in entry.detect):
            matches.append(path)
    return tuple(matches)


def resolve(spec: FileSpec, read_file, *, _hop: int = 0) -> str | None:
    """Read spec.glob via read_file(glob) -> str | None, follow one hop of inheritance."""
    content = read_file(spec.glob)
    if content is None:
        if spec.optional:
            return None
        raise UnresolvedError(f"file not found: {spec.glob}")

    raw = readers.read(spec, content)
    if raw is None:
        return None

    for inherit in spec.inherits:
        if re.match(inherit.when, raw):
            if _hop >= 1:
                raise UnresolvedError(f"inheritance cycle at {spec.glob}")
            return resolve(inherit.source, read_file, _hop=_hop + 1)

    return raw


def agree(entry: Entry, read_file) -> schemes.Version:
    """Resolve entry.files + extra_agree and require they all normalize to the same version."""
    specs = entry.files + entry.extra_agree
    values: dict[str, str] = {}
    for spec in specs:
        raw = resolve(spec, read_file)
        if raw is not None:
            values[spec.glob] = raw

    if not values:
        raise UnresolvedError(f"{entry.id}: no version file resolved")

    parsed = {
        glob: schemes.parse(entry.scheme, raw, numeric_parts=entry.numeric_parts)
        for glob, raw in values.items()
    }
    distinct = set(parsed.values())
    if len(distinct) > 1:
        raise DisagreementError(values)

    return next(iter(parsed.values()))


def gate(entry: Entry, severity: Severity) -> Severity:
    """Cap provisional-entry findings at WARN; verified entries pass severity through."""
    if entry.status == "provisional" and severity == Severity.FAIL:
        return Severity.WARN
    return severity


def is_tag_derived(entry: Entry, read_file) -> bool:
    """True when any tag_derived marker resolves, signalling the file-version check is skipped."""
    for marker in entry.tag_derived:
        try:
            if resolve(marker, read_file) is not None:
                return True
        except ReadError:
            continue
    return False
