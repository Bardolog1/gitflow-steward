"""Loads the optional .gitflow.toml at the repository root into a Config."""
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

_NOTES_MODES = ("manual", "guided", "automatic")


class ConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class Config:
    rc_minimum: int = 1
    soak_days: int = 0
    parallel_releases: bool = False
    core_tasks: tuple[str, ...] = ()
    notes_mode: str | None = None
    warnings: tuple[str, ...] = field(default_factory=tuple)
    source: str | None = None


def load(root: str) -> Config:
    path = Path(root) / ".gitflow.toml"
    if not path.exists():
        return Config()

    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"{path}: invalid TOML: {exc}") from exc

    warnings: list[str] = []

    rc_minimum = data.get("rc_minimum", 1)
    if not isinstance(rc_minimum, int) or isinstance(rc_minimum, bool) or rc_minimum < 1:
        raise ConfigError(f"{path}: rc_minimum must be an integer >= 1")

    soak_days = data.get("soak_days", 0)
    if not isinstance(soak_days, int) or isinstance(soak_days, bool) or soak_days < 0:
        raise ConfigError(f"{path}: soak_days must be an integer >= 0")

    parallel_releases = data.get("parallel_releases", False)
    if parallel_releases is not False:
        warnings.append("parallel_releases is not yet honored; enforcing a single open release")
        parallel_releases = False

    core_tasks = tuple(data.get("core_tasks", ()))

    notes_mode = data.get("notes_mode")
    if notes_mode is not None and notes_mode not in _NOTES_MODES:
        raise ConfigError(f"{path}: notes_mode must be one of {', '.join(_NOTES_MODES)}")

    return Config(
        rc_minimum=rc_minimum,
        soak_days=soak_days,
        parallel_releases=parallel_releases,
        core_tasks=core_tasks,
        notes_mode=notes_mode,
        warnings=tuple(warnings),
        source=str(path),
    )
