"""Pure pattern matchers for FAIL findings. FAIL is limited to explicitly forbidden patterns."""
import re

from steward.model import Finding, Severity

_EMOJI_RE = re.compile("[\U0001F300-\U0001FAFF☀-➿\U0001F1E6-\U0001F1FF]")

_NARRATING_PATTERNS = (
    re.compile(r"^this function\b", re.IGNORECASE),
    re.compile(r"^here we\b", re.IGNORECASE),
    re.compile(r"^step \d+:", re.IGNORECASE),
    re.compile(r"^[=\-*#]{3,}$"),
)


def _check_emoji(doc):
    return [
        Finding(
            rule="lint.fail.emoji", severity=Severity.FAIL, subject=doc.path,
            message=f"emoji character found: {match.group()!r}",
            evidence={"char": match.group()},
        )
        for match in _EMOJI_RE.finditer(doc.text)
    ]


def _check_hype_words(doc, data):
    lower = doc.text.lower()
    return [
        Finding(
            rule="lint.fail.hype_word", severity=Severity.FAIL, subject=doc.path,
            message=f'forbidden word "{word}" found',
            evidence={"word": word},
        )
        for word in data.get("hype_words", ())
        if word.lower() in lower
    ]


def _check_phrase_list(doc, data, key, rule_id, label):
    lower = doc.text.lower()
    return [
        Finding(
            rule=rule_id, severity=Severity.FAIL, subject=doc.path,
            message=f'{label}: "{phrase}"',
            evidence={"phrase": phrase},
        )
        for phrase in data.get(key, ())
        if phrase.lower() in lower
    ]


def _check_narrating_comments(doc):
    findings = []
    for comment in doc.comments:
        stripped = comment.strip()
        if any(pattern.match(stripped) for pattern in _NARRATING_PATTERNS):
            findings.append(Finding(
                rule="lint.fail.narrating_comment", severity=Severity.FAIL,
                subject=doc.path, message=f'comment narrates code: "{comment}"',
                evidence={"comment": comment},
            ))
    return findings


def check(doc, data) -> list[Finding]:
    findings = []
    findings.extend(_check_emoji(doc))
    findings.extend(_check_hype_words(doc, data))
    findings.extend(_check_phrase_list(doc, data, "chatbot_residue", "lint.fail.chatbot_residue", "chatbot residue"))
    findings.extend(_check_phrase_list(doc, data, "openers", "lint.fail.opener", "throat-clearing opener"))
    findings.extend(_check_phrase_list(doc, data, "closers", "lint.fail.closer", "recap closer"))
    findings.extend(_check_narrating_comments(doc))
    return findings
