import os
import re
from dataclasses import dataclass

from steward.guards import cmdparse

_ENV_PREFIX_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")

_SIMPLE_GIT_SUBCOMMANDS = {
    "status", "log", "show", "diff", "rev-parse", "rev-list", "merge-base",
    "describe", "for-each-ref", "cat-file", "ls-files", "ls-tree",
    "shortlog", "name-rev", "blame",
}
_LISTING_ONLY_GIT_SUBCOMMANDS = {"branch", "tag", "config", "remote", "reflog"}
_DANGEROUS_GIT_FLAGS = {"--ext-diff", "--upload-pack", "--exec"}

_GH_NOUNS = {"issue", "pr", "run", "release", "repo"}
_GH_VERBS = {"list", "view", "checks"}

_STEWARD_SINGLE_SUBS = {"audit", "readiness", "route", "lint"}
_STEWARD_NOTES_SUBS = {"questions", "draft", "check"}


@dataclass(frozen=True)
class Decision:
    allow: bool
    reason: str


def _deny(reason: str) -> Decision:
    return Decision(allow=False, reason=reason)


def _is_dangerous_git_flag(arg: str) -> bool:
    if arg.startswith("--output"):
        return True
    for flag in _DANGEROUS_GIT_FLAGS:
        if arg == flag or arg.startswith(flag + "="):
            return True
    return False


def _decide_git(args: tuple[str, ...]) -> Decision:
    if not args:
        return _deny("git requires a subcommand")
    sub = args[0]
    if sub.startswith("-"):
        return _deny(f"git global option rejected: {sub}")
    rest = args[1:]
    if any(_is_dangerous_git_flag(arg) for arg in rest):
        return _deny("git command uses a disallowed flag")
    if sub in _SIMPLE_GIT_SUBCOMMANDS:
        return Decision(allow=True, reason="recognized read-only git subcommand")
    if sub in _LISTING_ONLY_GIT_SUBCOMMANDS:
        if any(not arg.startswith("-") for arg in rest):
            return _deny(f"git {sub} with a positional argument is not a listing operation")
        return Decision(allow=True, reason=f"git {sub} listing form")
    return _deny(f"unrecognized git subcommand: {sub}")


def _decide_gh(args: tuple[str, ...]) -> Decision:
    if not args:
        return _deny("gh requires a noun")
    noun = args[0]
    if noun == "api":
        return _deny("gh api is always rejected")
    if noun in _GH_NOUNS and len(args) >= 2 and args[1] in _GH_VERBS:
        return Decision(allow=True, reason=f"recognized gh {noun} {args[1]}")
    return _deny(f"unrecognized gh command: {' '.join(args)}")


def _resolve(path: str) -> str:
    return os.path.normpath(path).replace("\\", "/")


def _decide_steward_launcher(args: tuple[str, ...], steward_home: str) -> Decision:
    if not args:
        return _deny("bash requires a script path")
    script = args[0]
    expected = _resolve(os.path.join(steward_home, "bin", "steward"))
    if _resolve(script) != expected:
        return _deny("bash script is not the resolved steward launcher")
    rest = args[1:]
    if not rest:
        return _deny("steward launcher requires a subcommand")
    if rest[0] in _STEWARD_SINGLE_SUBS:
        return Decision(allow=True, reason=f"steward {rest[0]}")
    if rest[0] == "notes" and len(rest) >= 2 and rest[1] in _STEWARD_NOTES_SUBS:
        return Decision(allow=True, reason=f"steward notes {rest[1]}")
    return _deny(f"unrecognized steward subcommand: {' '.join(rest)}")


def decide(cmd: str, steward_home: str) -> Decision:
    """Allow a command only if it matches the read-only allowlist exactly.

    Fails safe: any parse error, control operator, or unrecognized shape
    is denied.
    """
    try:
        parsed = cmdparse.split(cmd)
        if parsed.has_control_operator:
            return _deny("command contains a shell control operator")
        if len(parsed.segments) != 1:
            return _deny("command must be a single segment")
        segment = parsed.segments[0]
        if not segment:
            return _deny("empty command")

        first = segment[0]
        if _ENV_PREFIX_RE.match(first):
            return _deny(f"environment-prefixed command rejected: {first}")

        if first == "git":
            return _decide_git(segment[1:])
        if first == "gh":
            return _decide_gh(segment[1:])
        if first == "bash":
            return _decide_steward_launcher(segment[1:], steward_home)
        if first == "pwd" and len(segment) == 1:
            return Decision(allow=True, reason="pwd")
        return _deny(f"unrecognized command: {first}")
    except Exception as exc:  # noqa: BLE001 - guard must never crash, fail safe to deny
        return _deny(f"guard error, denying by default: {exc}")
