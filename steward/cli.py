import argparse
import json
import os
import sys
from io import TextIOBase
from pathlib import Path

from steward import branches, config as config_module, git, readiness as readiness_module, routing, tags
from steward.guards import push_guard, readonly_guard
from steward.model import Finding, Report, Severity
from steward.notes import conventional as conventional_module, render as render_module

_STEWARD_HOME = str(Path(__file__).resolve().parent.parent)

SCHEMA = 1

_ROUTE_SEVERITY = {
    "critical": routing.CRITICAL,
    "non-critical": routing.NON_CRITICAL,
    "unsure": routing.UNDETERMINED,
}
_ROUTE_STAGE = {"final": "released", "rc": "rc"}


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


def _error_envelope(command: str, message: str) -> dict:
    return {
        "schema": SCHEMA,
        "command": command,
        "repo": None,
        "head": None,
        "config_source": None,
        "findings": [],
        "summary": {"fail": 0, "warn": 0, "info": 0},
        "error": message,
    }


def _collect(root: str):
    """Load config and git state together; raises GitError/ConfigError."""
    cfg = config_module.load(root)
    state = git.collect(root)
    return state, cfg


def _run_audit(args, out) -> int:
    root = os.getcwd()
    try:
        state, cfg = _collect(root)
    except (git.GitError, config_module.ConfigError) as exc:
        print(json.dumps(_error_envelope("audit", str(exc))), file=out)
        return 2
    findings = tuple(branches.check(state, cfg)) + tuple(tags.check(state, cfg))
    report = Report(findings=findings)
    payload = _envelope("audit", report, repo=root, head=state.head, config_source=cfg.source)
    print(json.dumps(payload), file=out)
    return 1 if report.has_fail() else 0


def _run_readiness(args, out) -> int:
    root = os.getcwd()
    try:
        state, cfg = _collect(root)
    except (git.GitError, config_module.ConfigError) as exc:
        print(json.dumps(_error_envelope("readiness", str(exc))), file=out)
        return 2
    result = readiness_module.check(state, cfg, args.release)
    report = Report(findings=result.findings)
    payload = _envelope(
        "readiness", report, repo=root, head=state.head, config_source=cfg.source,
        decision=result.decision, blockers=[f.rule for f in result.blockers()],
    )
    print(json.dumps(payload), file=out)
    return 0 if result.decision == "go" else 1


def _open_release(state) -> str | None:
    by_name = {b.name: b for b in state.branches}
    main = by_name.get("main")
    if main is None:
        return None
    main_ancestors = set()
    stack = [main.sha]
    while stack:
        sha = stack.pop()
        if sha in main_ancestors or sha not in state.commits:
            continue
        main_ancestors.add(sha)
        stack.extend(state.commits[sha].parents)
    open_releases = [b.name for b in state.branches if b.name.startswith("release/") and b.sha not in main_ancestors]
    return open_releases[0] if len(open_releases) == 1 else None


def _run_route(args, out) -> int:
    severity = _ROUTE_SEVERITY[args.severity]
    stage = _ROUTE_STAGE[args.stage]
    open_release = None
    if stage == "rc":
        try:
            state = git.collect(os.getcwd())
        except git.GitError:
            state = None
        if state is not None:
            open_release = _open_release(state)

    try:
        plan = routing.route(severity, stage, open_release=open_release)
    except routing.RoutingError as exc:
        findings = (Finding(
            rule="route.undetermined", severity=Severity.INFO,
            subject=args.severity, message=str(exc),
        ),)
    else:
        findings = (Finding(
            rule="route.plan", severity=Severity.INFO, subject=args.severity,
            message=f"route to {plan.branch_type}/* from {plan.from_branch}",
            evidence={"branch_type": plan.branch_type, "from_branch": plan.from_branch},
        ),)
    print(json.dumps(_envelope("route", Report(findings=findings))), file=out)
    return 0


def _run_notes_questions(out) -> int:
    questions = render_module.load_questions()
    report = Report()
    print(json.dumps(_envelope("notes", report, questions=list(questions))), file=out)
    return 0


def _run_notes_draft(args, stdin, out) -> int:
    if args.mode == "automatic":
        if not args.from_rev or not args.to_rev:
            print(json.dumps(_error_envelope("notes", "--from and --to are required for automatic mode")), file=out)
            return 2
        try:
            commits = git.commit_subjects_between(os.getcwd(), args.from_rev, args.to_rev)
        except git.GitError as exc:
            print(json.dumps(_error_envelope("notes", str(exc))), file=out)
            return 2
        draft = render_module.render_automatic(conventional_module.group_commits(commits))
    elif args.mode == "guided":
        text = stdin.read() if args.answers == "-" else ""
        try:
            answers = json.loads(text) if text else {}
        except json.JSONDecodeError as exc:
            print(json.dumps(_error_envelope("notes", str(exc))), file=out)
            return 2
        draft = render_module.render_guided(answers)
    else:
        draft = ""
    report = Report()
    print(json.dumps(_envelope("notes", report, draft=draft)), file=out)
    return 1 if report.has_fail() else 0


def _run_notes_check(args, out) -> int:
    try:
        with open(args.file, "r", encoding="utf-8") as handle:
            text = handle.read()
    except OSError as exc:
        print(json.dumps(_error_envelope("notes", str(exc))), file=out)
        return 2
    findings = ()
    if not text.strip():
        findings = (Finding(
            rule="notes.empty", severity=Severity.FAIL, subject=args.file,
            message="release notes file is empty",
        ),)
    report = Report(findings=findings)
    print(json.dumps(_envelope("notes", report)), file=out)
    return 1 if report.has_fail() else 0


def _run_notes(args, stdin, out) -> int:
    if args.notes_command == "questions":
        return _run_notes_questions(out)
    if args.notes_command == "draft":
        return _run_notes_draft(args, stdin, out)
    return _run_notes_check(args, out)


def _run_lint(args, out) -> int:
    report = Report()
    print(json.dumps(_envelope("lint", report)), file=out)
    return 1 if report.has_fail() else 0


def _hook_payload(decision: str | None, reason: str | None) -> dict:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": reason,
        }
    }


def _run_hook(args, stdin, out) -> int:
    try:
        payload_in = json.load(stdin)
        if not isinstance(payload_in, dict):
            payload_in = {}
    except (json.JSONDecodeError, ValueError):
        payload_in = {}

    tool_input = payload_in.get("tool_input")
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    cwd = payload_in.get("cwd") or os.getcwd()

    if not isinstance(command, str):
        decision, reason = "deny", "no command found in tool_input"
    elif args.kind == "readonly":
        result = readonly_guard.decide(command, _STEWARD_HOME)
        decision = "allow" if result.allow else "deny"
        reason = result.reason
    else:
        result = push_guard.decide(command, cwd)
        decision, reason = result.decision, result.reason

    print(json.dumps(_hook_payload(decision, reason)), file=out)
    return 0


_HANDLERS = {
    "audit": _run_audit,
    "readiness": _run_readiness,
    "route": _run_route,
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
    if args.command == "notes":
        return _run_notes(args, stdin if stdin is not None else sys.stdin, out)

    handler = _HANDLERS[args.command]
    return handler(args, out)
