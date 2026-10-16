"""Dispatches FAIL and WARN rule sets over paths and honors .gitflow.toml [lint]."""
import tomllib
from pathlib import Path

from steward.lint import fail_rules, warn_rules
from steward.lint.doc import build_doc
from steward.model import Report

_RULES_PATH = Path(__file__).resolve().parent / "prose_rules.toml"


def load_rules(path: Path | None = None) -> dict:
    target = path or _RULES_PATH
    return tomllib.loads(target.read_text(encoding="utf-8"))


def _load_lint_config(root: str) -> dict:
    config_path = Path(root) / ".gitflow.toml"
    if not config_path.exists():
        return {}
    data = tomllib.loads(config_path.read_text(encoding="utf-8"))
    return data.get("lint", {})


def _apply_lint_config(rules: dict, lint_config: dict) -> dict:
    warn = dict(rules.get("warn", {}))
    extra_words = lint_config.get("extra_ai_vocabulary", ())
    if extra_words:
        warn["ai_vocabulary"] = list(warn.get("ai_vocabulary", ())) + list(extra_words)
    merged = dict(rules)
    merged["warn"] = warn
    merged["_disabled_warn_rules"] = set(lint_config.get("disable_warn_rules", ()))
    return merged


def check(paths, root: str = ".", rules_path: Path | None = None) -> Report:
    rules = _apply_lint_config(load_rules(rules_path), _load_lint_config(root))
    findings = []
    for path in paths:
        text = Path(path).read_text(encoding="utf-8")
        doc = build_doc(path, text)
        findings.extend(fail_rules.check(doc, rules["fail"]))
        findings.extend(warn_rules.check(doc, rules))
    return Report(findings=tuple(findings))
