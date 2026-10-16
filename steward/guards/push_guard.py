import subprocess
from dataclasses import dataclass

from steward.guards import cmdparse

_OBFUSCATION_FIRST_TOKENS = {"eval", "env"}
_GH_RELEASE_VERBS = {"create", "edit", "delete", "upload"}


@dataclass(frozen=True)
class Decision:
    decision: str | None
    reason: str | None


def _ask(reason: str) -> Decision:
    return Decision(decision="ask", reason=reason)


_NO_DECISION = Decision(decision=None, reason=None)


def _current_branch(cwd: str) -> str | None:
    result = subprocess.run(
        ["git", "symbolic-ref", "--short", "HEAD"],
        cwd=cwd, capture_output=True, text=True, timeout=10,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _is_shell_wrapper(first: str, rest: tuple[str, ...]) -> bool:
    if first in ("sh", "bash") and rest and rest[0] in ("-c", "-lc"):
        return True
    return first in _OBFUSCATION_FIRST_TOKENS


def _segment_asks(seg: tuple[str, ...]) -> str | None:
    first = seg[0]
    rest = seg[1:]

    if _is_shell_wrapper(first, rest):
        return f"obfuscated shell invocation: {first}"

    if first == "git":
        if rest and rest[0] in ("-C", "-c"):
            return f"git global option is an obfuscation risk: {rest[0]}"
        if rest and rest[0] == "push":
            return "git push is irreversible without confirmation"
        if rest and rest[0] == "tag" and "-d" in rest[1:]:
            return "deleting a tag is irreversible without confirmation"
        if rest and rest[0] == "branch" and any(a in ("-d", "-D", "--delete") for a in rest[1:]):
            return "deleting a branch is irreversible without confirmation"
        return None

    if first == "gh":
        if rest and rest[0] == "api":
            return "gh api is irreversible without confirmation"
        if rest and rest[0] == "release" and len(rest) >= 2 and rest[1] in _GH_RELEASE_VERBS:
            return f"gh release {rest[1]} is irreversible without confirmation"
        if rest and rest[0] == "pr" and len(rest) >= 2 and rest[1] == "merge":
            return "gh pr merge is irreversible without confirmation"
        return None

    return None


def _checked_out_to_main(segments: tuple[tuple[str, ...], ...]) -> bool:
    for seg in segments:
        if len(seg) >= 3 and seg[0] == "git" and seg[1] in ("checkout", "switch") and "main" in seg[2:]:
            return True
    return False


def decide(cmd: str, cwd: str) -> Decision:
    """Return ask for irreversible operations, otherwise no decision.

    Never returns allow: a non-ask result passes through to the normal
    permission rules. Fails safe to ask on any internal error.
    """
    try:
        if "`" in cmd or "$(" in cmd:
            return _ask("command substitution is an obfuscation risk")

        parsed = cmdparse.split(cmd)
        if not parsed.segments:
            return _ask("command could not be parsed, failing safe")

        merged_to_main = _checked_out_to_main(parsed.segments)

        for seg in parsed.segments:
            if not seg:
                continue
            reason = _segment_asks(seg)
            if reason is not None:
                return _ask(reason)
            if seg[0] == "git" and len(seg) >= 2 and seg[1] == "merge":
                if merged_to_main:
                    return _ask("merging into main requires confirmation")
                try:
                    branch = _current_branch(cwd)
                except Exception:
                    return _ask("could not confirm current branch, failing safe")
                if branch == "main":
                    return _ask("merging into main requires confirmation")

        return _NO_DECISION
    except Exception as exc:  # noqa: BLE001 - guard must never crash, fail safe to ask
        return _ask(f"guard error, asking by default: {exc}")
