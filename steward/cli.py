import argparse
import json
import sys
from io import TextIOBase

from steward.model import Report

SCHEMA = 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="steward")
    sub = parser.add_subparsers(dest="command")

    audit = sub.add_parser("audit")
    audit.add_argument("--rev")
    audit.add_argument("--json", action="store_true")

    readiness = sub.add_parser("readiness")
    readiness.add_argument("--release", required=True)
    readiness.add_argument("--json", action="store_true")

    route = sub.add_parser("route")
    route.add_argument("--severity", required=True, choices=["critical", "non-critical", "unsure"])
    route.add_argument("--stage", required=True, choices=["final", "rc"])

    notes = sub.add_parser("notes")
    notes_sub = notes.add_subparsers(dest="notes_command", required=True)
    questions = notes_sub.add_parser("questions")
    questions.add_argument("--json", action="store_true")
    draft = notes_sub.add_parser("draft")
    draft.add_argument("--mode", required=True, choices=["automatic", "guided", "manual"])
    draft.add_argument("--from", dest="from_rev")
    draft.add_argument("--to", dest="to_rev")
    draft.add_argument("--answers")
    check = notes_sub.add_parser("check")
    check.add_argument("--file", required=True)

    lint = sub.add_parser("lint")
    lint.add_argument("paths", nargs="+")
    lint.add_argument("--json", action="store_true")

    hook = sub.add_parser("hook")
    hook.add_argument("kind", choices=["readonly", "push"])

    return parser


def _envelope(command: str, report: Report, **extra) -> dict:
    payload = {
        "schema": SCHEMA,
        "command": command,
        "repo": None,
        "head": None,
        "config_source": None,
        "findings": [
            {
                "rule": f.rule,
                "severity": str(f.severity),
                "subject": f.subject,
                "message": f.message,
                "fix": f.fix,
                "evidence": f.evidence,
            }
            for f in report.findings
        ],
        "summary": report.summary(),
    }
    payload.update(extra)
    return payload


def _run_audit(args, out) -> int:
    report = Report()
    print(json.dumps(_envelope("audit", report)), file=out)
    return 1 if report.has_fail() else 0


def _run_readiness(args, out) -> int:
    report = Report()
    decision = "go" if not report.has_fail() else "no-go"
    payload = _envelope("readiness", report, decision=decision, blockers=[])
    print(json.dumps(payload), file=out)
    return 0 if decision == "go" else 1


def _run_route(args, out) -> int:
    report = Report()
    print(json.dumps(_envelope("route", report)), file=out)
    return 0


def _run_notes(args, out) -> int:
    report = Report()
    print(json.dumps(_envelope("notes", report)), file=out)
    return 1 if report.has_fail() else 0


def _run_lint(args, out) -> int:
    report = Report()
    print(json.dumps(_envelope("lint", report)), file=out)
    return 1 if report.has_fail() else 0


def _run_hook(args, stdin, out) -> int:
    try:
        json.load(stdin)
    except (json.JSONDecodeError, ValueError):
        pass
    payload = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": None,
            "permissionDecisionReason": None,
        }
    }
    print(json.dumps(payload), file=out)
    return 0


_HANDLERS = {
    "audit": _run_audit,
    "readiness": _run_readiness,
    "route": _run_route,
    "notes": _run_notes,
    "lint": _run_lint,
}


def main(argv: list[str] | None = None, stdin: TextIOBase | None = None, stdout=None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    out = stdout if stdout is not None else sys.stdout

    if args.command is None:
        parser.print_usage(sys.stderr)
        return 2

    if args.command == "hook":
        return _run_hook(args, stdin if stdin is not None else sys.stdin, out)

    handler = _HANDLERS[args.command]
    return handler(args, out)
