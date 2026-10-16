"""Readers: extract a raw version string from file content given a FileSpec."""
import configparser
import json
import plistlib
import re
import tomllib
from xml.etree import ElementTree

from steward.versions.schema import FileSpec

_XMLNS_RE = re.compile(r'\sxmlns(:(\w+))?="[^"]*"')
_DOCTYPE_RE = re.compile(r"<!DOCTYPE", re.IGNORECASE)
_HASH_COMMENT_RE = re.compile(r"#.*$", re.MULTILINE)
_SLASH_LINE_COMMENT_RE = re.compile(r"//.*$", re.MULTILINE)
_SLASH_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
_XML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


class ReadError(RuntimeError):
    pass


class KeyNotFoundError(ReadError):
    pass


class AmbiguousMatchError(ReadError):
    pass


def read(spec: FileSpec, content: str) -> str | None:
    """Extract the raw version string per spec.kind. None if optional and absent."""
    try:
        return _READERS[spec.kind](spec, content)
    except KeyNotFoundError:
        if spec.optional:
            return None
        raise


def _dotted_get(data: dict, key: str) -> object:
    node = data
    for part in key.split("."):
        if not isinstance(node, dict) or part not in node:
            raise KeyNotFoundError(f"key not found: {key!r}")
        node = node[part]
    return node


def _read_json(spec: FileSpec, content: str) -> str:
    return str(_dotted_get(json.loads(content), spec.key))


def _read_toml(spec: FileSpec, content: str) -> str:
    return str(_dotted_get(tomllib.loads(content), spec.key))


def _read_xml(spec: FileSpec, content: str) -> str:
    if _DOCTYPE_RE.search(content):
        raise ReadError("XML DOCTYPE is refused")
    prefixes = [m.group(2) for m in _XMLNS_RE.finditer(content) if m.group(2)]
    stripped = _XMLNS_RE.sub("", content)
    for prefix in prefixes:
        stripped = re.sub(rf'\s{re.escape(prefix)}:\w+="[^"]*"', "", stripped)
    root = ElementTree.fromstring(stripped)
    node = root.find(spec.key)
    if node is None or node.text is None:
        raise KeyNotFoundError(f"xml path not found: {spec.key!r}")
    return node.text


def _read_ini(spec: FileSpec, content: str) -> str:
    parser = configparser.ConfigParser()
    parser.read_string(content)
    section, _, option = spec.key.partition(".")
    try:
        return parser.get(section, option)
    except (configparser.NoSectionError, configparser.NoOptionError) as exc:
        raise KeyNotFoundError(f"ini key not found: {spec.key!r}") from exc


def _read_plist(spec: FileSpec, content: str) -> str:
    return str(_dotted_get(plistlib.loads(content.encode("utf-8")), spec.key))


def _strip_comments(content: str, mode: str | None) -> str:
    if mode == "hash":
        return _HASH_COMMENT_RE.sub("", content)
    if mode == "slash":
        return _SLASH_BLOCK_COMMENT_RE.sub("", _SLASH_LINE_COMMENT_RE.sub("", content))
    if mode == "xml":
        return _XML_COMMENT_RE.sub("", content)
    return content


def _read_regex(spec: FileSpec, content: str) -> str:
    text = _strip_comments(content, spec.strip_comments)
    matches = {m.group(1) for m in re.finditer(spec.pattern, text, re.MULTILINE)}
    if not matches:
        raise KeyNotFoundError(f"pattern not found: {spec.pattern!r}")
    if len(matches) > 1:
        raise AmbiguousMatchError(f"ambiguous matches for {spec.pattern!r}: {sorted(matches)}")
    return next(iter(matches))


def _read_text(spec: FileSpec, content: str) -> str:
    return content.strip()


_READERS = {
    "json": _read_json,
    "toml": _read_toml,
    "xml": _read_xml,
    "ini": _read_ini,
    "plist": _read_plist,
    "regex": _read_regex,
    "text": _read_text,
}
