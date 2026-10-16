"""Builds a Doc (lines, paragraphs, words, code comments) for the prose linter."""
import re
from dataclasses import dataclass

_COMMENT_RE = re.compile(r"^\s*(?:#|//|\*)\s*(.*)$")
_FENCE_RE = re.compile(r"```[^\n]*\n(.*?)```", re.DOTALL)
_MARKDOWN_EXTENSIONS = (".md", ".markdown")


@dataclass(frozen=True)
class Doc:
    path: str
    text: str
    lines: tuple[str, ...]
    paragraphs: tuple[str, ...]
    words: tuple[str, ...]
    comments: tuple[str, ...]


def _split_paragraphs(text: str) -> tuple[str, ...]:
    blocks = re.split(r"\n\s*\n", text)
    return tuple(" ".join(b.split()) for b in blocks if b.strip())


def _extract_comments(text: str, is_markdown: bool) -> tuple[str, ...]:
    code_text = "\n".join(_FENCE_RE.findall(text)) if is_markdown else text
    comments = []
    for line in code_text.splitlines():
        match = _COMMENT_RE.match(line)
        if match and match.group(1).strip():
            comments.append(match.group(1).strip())
    return tuple(comments)


def build_doc(path: str, text: str) -> Doc:
    is_markdown = path.lower().endswith(_MARKDOWN_EXTENSIONS)
    return Doc(
        path=path,
        text=text,
        lines=tuple(text.splitlines()),
        paragraphs=_split_paragraphs(text),
        words=tuple(re.findall(r"[A-Za-z']+", text)),
        comments=_extract_comments(text, is_markdown),
    )
