"""Template assembly for guided and automatic release notes."""
import tomllib
from pathlib import Path

from steward.notes import conventional

_GUIDED_TOML = Path(__file__).parent / "guided.toml"

_SECTION_HEADERS = {
    "breaking": "## Breaking Changes & Upgrade Steps",
    "added": "## Added",
    "changed": "## Changed",
    "deprecated": "## Deprecated",
    "removed": "## Removed",
    "fixed": "## Fixed",
    "known_issues": "## Known Issues",
}
_OMIT_WHEN_EMPTY = ("added", "changed", "deprecated", "removed", "fixed", "known_issues")


def load_questions() -> tuple[dict, ...]:
    with _GUIDED_TOML.open("rb") as handle:
        data = tomllib.load(handle)
    return tuple(sorted(data["question"], key=lambda q: q["id"]))


def render_guided(answers: dict[str, str]) -> str:
    lines = []
    summary = answers.get("summary", "").strip()
    if summary:
        lines.append(summary)
    lines.append(_SECTION_HEADERS["breaking"])
    lines.append(answers.get("breaking", "").strip() or "None.")
    for slot in _OMIT_WHEN_EMPTY:
        text = answers.get(slot, "").strip()
        if not text:
            continue
        lines.append(_SECTION_HEADERS[slot])
        lines.append(text)
    return "\n\n".join(lines) + "\n"


def render_automatic(groups: dict[str, tuple[str, ...]]) -> str:
    lines = []
    for group in conventional.GROUP_ORDER:
        items = groups.get(group)
        if not items:
            continue
        lines.append(f"## {group}")
        lines.extend(f"- {item}" for item in items)
    return "\n".join(lines) + "\n" if lines else ""
