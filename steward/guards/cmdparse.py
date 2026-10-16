import shlex
from dataclasses import dataclass

_OPERATORS = {";", "&&", "||", "|", "&", ">", ">>", "<", "<<"}


@dataclass(frozen=True)
class SplitResult:
    segments: tuple[tuple[str, ...], ...]
    has_control_operator: bool


def split(cmd: str) -> SplitResult:
    """Quote-aware split of a shell command string into segments.

    Segments are separated at shell control operators. Any control
    operator present (including an embedded newline, backtick, or
    `$(` command substitution) sets `has_control_operator`. Malformed
    quoting fails safe: no segments, flagged as having an operator.
    """
    if "\n" in cmd or "`" in cmd or "$(" in cmd:
        has_control = True
    else:
        has_control = False

    lexer = shlex.shlex(cmd, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    try:
        tokens = list(lexer)
    except ValueError:
        return SplitResult(segments=(), has_control_operator=True)

    segments: list[tuple[str, ...]] = []
    current: list[str] = []
    for token in tokens:
        if token in _OPERATORS:
            has_control = True
            segments.append(tuple(current))
            current = []
        else:
            current.append(token)
    segments.append(tuple(current))
    segments = tuple(seg for seg in segments if seg)

    return SplitResult(segments=segments, has_control_operator=has_control)
