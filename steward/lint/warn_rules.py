"""Heuristic checks for WARN findings. None of these ever escalate to FAIL."""
import re

from steward.model import Finding, Severity

_TRIAD_RE = re.compile(r"\b[A-Za-z]+,\s+[A-Za-z]+,\s+and\s+[A-Za-z]+\b")
_NEG_PARALLEL_RE = re.compile(r"\bnot\s+\w+(?:\s+\w+){0,4},?\s+but\s+\w+", re.IGNORECASE)
_LIST_ITEM_RE = re.compile(r"^\s*[-*]\s+(\w+)")


def _check_ai_vocabulary(doc, data):
    if not doc.words:
        return []
    vocab = {w.lower() for w in data.get("ai_vocabulary", ())}
    matches = [w for w in doc.words if w.lower() in vocab]
    if not matches:
        return []
    density = len(matches) / len(doc.words) * 100
    threshold = data.get("ai_vocabulary_threshold_per_100_words", 3)
    if density < threshold:
        return []
    return [Finding(
        rule="lint.warn.ai_vocabulary", severity=Severity.WARN, subject=doc.path,
        message=f"AI-vocabulary density {density:.1f} per 100 words meets threshold {threshold}",
        evidence={"density": f"{density:.2f}", "matches": ",".join(sorted({m.lower() for m in matches}))},
    )]


def _check_paragraph_length(doc, data):
    max_words = data.get("paragraph_max_words", 150)
    findings = []
    for index, paragraph in enumerate(doc.paragraphs):
        word_count = len(paragraph.split())
        if word_count > max_words:
            findings.append(Finding(
                rule="lint.warn.paragraph_length", severity=Severity.WARN, subject=doc.path,
                message=f"paragraph {index + 1} has {word_count} words, exceeds {max_words}",
                evidence={"paragraph_index": str(index), "word_count": str(word_count)},
            ))
    return findings


def _check_triads(doc):
    return [
        Finding(
            rule="lint.warn.triad", severity=Severity.WARN, subject=doc.path,
            message=f'rule-of-three construction: "{match.group()}"',
            evidence={"match": match.group()},
        )
        for match in _TRIAD_RE.finditer(doc.text)
    ]


def _check_negative_parallelism(doc):
    return [
        Finding(
            rule="lint.warn.negative_parallelism", severity=Severity.WARN, subject=doc.path,
            message=f'negative-parallelism construction: "{match.group()}"',
            evidence={"match": match.group()},
        )
        for match in _NEG_PARALLEL_RE.finditer(doc.text)
    ]


def _check_vague_attribution(doc, data):
    lower = doc.text.lower()
    return [
        Finding(
            rule="lint.warn.vague_attribution", severity=Severity.WARN, subject=doc.path,
            message=f'vague attribution: "{phrase}"',
            evidence={"phrase": phrase},
        )
        for phrase in data.get("vague_attribution", ())
        if phrase.lower() in lower
    ]


def _has_mixed_forms(words):
    if len(words) < 2:
        return False
    gerund = [w.lower().endswith("ing") for w in words]
    return any(gerund) and not all(gerund)


def _check_non_parallel_lists(doc):
    findings = []
    current: list[str] = []
    for line in doc.lines:
        match = _LIST_ITEM_RE.match(line)
        if match:
            current.append(match.group(1))
            continue
        if current:
            if _has_mixed_forms(current):
                findings.append(_non_parallel_finding(doc, current))
            current = []
    if current and _has_mixed_forms(current):
        findings.append(_non_parallel_finding(doc, current))
    return findings


def _non_parallel_finding(doc, words):
    return Finding(
        rule="lint.warn.non_parallel_list", severity=Severity.WARN, subject=doc.path,
        message="list items do not share a parallel grammatical form",
        evidence={"first_words": ",".join(words)},
    )


def _check_em_dash(doc):
    if "—" in doc.text:
        return [Finding(
            rule="lint.warn.em_dash", severity=Severity.WARN, subject=doc.path,
            message="em dash found", evidence={},
        )]
    return []


_RULES = (
    ("ai_vocabulary", _check_ai_vocabulary),
    ("paragraph_length", _check_paragraph_length),
    ("triad", lambda doc, data: _check_triads(doc)),
    ("negative_parallelism", lambda doc, data: _check_negative_parallelism(doc)),
    ("vague_attribution", _check_vague_attribution),
    ("non_parallel_list", lambda doc, data: _check_non_parallel_lists(doc)),
)


def check(doc, rules) -> list[Finding]:
    data = rules.get("warn", {})
    disabled = rules.get("_disabled_warn_rules", set())
    findings = []
    for rule_id, fn in _RULES:
        if rule_id in disabled:
            continue
        findings.extend(fn(doc, data))
    if "em_dash" not in disabled and data.get("em_dash_enabled", False):
        findings.extend(_check_em_dash(doc))
    return findings
