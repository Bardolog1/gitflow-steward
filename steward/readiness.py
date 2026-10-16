"""Readiness report: go/no-go decision for promoting one open release/* branch."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from steward import gh
from steward.config import Config
from steward.git import RepoState
from steward.model import Finding, Severity

_RC_SUFFIX = "-rc."


def _ancestors(sha, commits):
    seen, stack = set(), [sha]
    while stack:
        s = stack.pop()
        if s in seen or s not in commits:
            continue
        seen.add(s)
        stack.extend(commits[s].parents)
    return seen


def _open_bugfix_branches(state: RepoState, release_name: str, release_sha: str) -> tuple[str, ...]:
    release_ancestors = _ancestors(release_sha, state.commits)
    unmerged = []
    for b in state.branches:
        if not b.name.startswith("bugfix/"):
            continue
        if b.sha in release_ancestors:
            continue
        unmerged.append(b.name)
    return tuple(unmerged)


def _rc_tags(state: RepoState, release_name: str) -> list:
    version = release_name.removeprefix("release/")
    prefix = f"v{version}{_RC_SUFFIX}"
    return [t for t in state.tags if t.name.startswith(prefix)]


def _latest_rc(rc_tags: list):
    if not rc_tags:
        return None
    return max(rc_tags, key=lambda t: t.tagger_date or "")


@dataclass(frozen=True)
class Readiness:
    decision: str  # "go" | "no-go"
    findings: tuple[Finding, ...]

    def blockers(self) -> tuple[Finding, ...]:
        return tuple(f for f in self.findings if f.severity == Severity.FAIL)

    def to_dict(self) -> dict:
        return {
            "decision": self.decision,
            "blockers": [f.rule for f in self.blockers()],
            "findings": [
                {"rule": f.rule, "severity": str(f.severity), "subject": f.subject, "message": f.message}
                for f in self.findings
            ],
        }


def check(
    state: RepoState,
    config: Config,
    release_name: str,
    *,
    now: datetime | None = None,
    gh_run_json=gh.run_json,
) -> Readiness:
    """Build a readiness report for an open `release/*` branch."""
    now = now or datetime.now(timezone.utc)
    branch = next((b for b in state.branches if b.name == release_name), None)
    findings: list[Finding] = []

    if branch is None:
        findings.append(Finding(
            rule="readiness.unknown-release",
            severity=Severity.FAIL,
            subject=release_name,
            message=f"{release_name} is not an open release branch",
        ))
        return Readiness(decision="no-go", findings=tuple(findings))

    unmerged = _open_bugfix_branches(state, release_name, branch.sha)
    for name in unmerged:
        findings.append(Finding(
            rule="readiness.unmerged-bugfix",
            severity=Severity.FAIL,
            subject=name,
            message=f"{name} targets {release_name} and is not yet merged",
        ))

    if gh.is_available():
        try:
            findings.extend(_blocker_issues(release_name, gh_run_json))
        except gh.GhError:
            pass
        try:
            findings.extend(_ci_status(release_name, branch, gh_run_json))
        except gh.GhError:
            pass
    else:
        findings.append(Finding(
            rule="readiness.ci-unknown",
            severity=Severity.INFO,
            subject=release_name,
            message="gh CLI not available; CI status is unknown and not a blocker",
        ))

    rc_tags = _rc_tags(state, release_name)
    rc_count = len(rc_tags)
    findings.append(Finding(
        rule="readiness.rc-count",
        severity=Severity.INFO,
        subject=release_name,
        message=f"{rc_count} release candidate(s) cut",
        evidence={"rc_count": str(rc_count)},
    ))
    if rc_count < config.rc_minimum:
        findings.append(Finding(
            rule="readiness.rc-minimum",
            severity=Severity.FAIL,
            subject=release_name,
            message=f"only {rc_count} RC tag(s); rc_minimum is {config.rc_minimum}",
        ))

    latest_rc = _latest_rc(rc_tags)
    if latest_rc is not None and latest_rc.tagger_date:
        soaked_since = datetime.fromisoformat(latest_rc.tagger_date)
        elapsed = now - soaked_since
        required = timedelta(days=config.soak_days)
        findings.append(Finding(
            rule="readiness.soak-time",
            severity=Severity.INFO,
            subject=release_name,
            message=f"{elapsed.days} day(s) since {latest_rc.name}",
            evidence={"days_since_latest_rc": str(elapsed.days)},
        ))
        if config.soak_days > 0:
            if elapsed < required:
                findings.append(Finding(
                    rule="readiness.soak-time-insufficient",
                    severity=Severity.FAIL,
                    subject=release_name,
                    message=f"soak time since {latest_rc.name} is below the configured {config.soak_days} day(s)",
                ))
        else:
            # ponytail: no real threshold at the default; still nudge the
            # operator rather than staying silent, per the spec's advisory case.
            findings.append(Finding(
                rule="readiness.soak-time-insufficient",
                severity=Severity.WARN,
                subject=release_name,
                message=f"no soak_days configured; {elapsed.days} day(s) since {latest_rc.name}",
            ))

    decision = "no-go" if any(f.severity == Severity.FAIL for f in findings) else "go"
    return Readiness(decision=decision, findings=tuple(findings))


def _blocker_issues(release_name: str, gh_run_json) -> list[Finding]:
    issues = gh_run_json(
        "issue", "list", "--label", "blocker", "--state", "open",
        "--search", release_name.removeprefix("release/"), "--json", "number,title",
    )
    findings = []
    for issue in issues or []:
        findings.append(Finding(
            rule="readiness.blocker-issue",
            severity=Severity.FAIL,
            subject=f"#{issue.get('number')}",
            message=f"open blocker issue: {issue.get('title')}",
        ))
    return findings


def _ci_status(release_name: str, branch, gh_run_json) -> list[Finding]:
    result = gh_run_json(
        "run", "list", "--branch", release_name, "--limit", "1",
        "--json", "status,conclusion",
    )
    runs = result or []
    if not runs:
        return [Finding(
            rule="readiness.ci-unknown",
            severity=Severity.INFO,
            subject=release_name,
            message="no CI run found for this branch; CI status is unknown",
        )]
    run = runs[0]
    if run.get("status") == "completed" and run.get("conclusion") not in ("success", None):
        return [Finding(
            rule="readiness.ci-failing",
            severity=Severity.FAIL,
            subject=release_name,
            message=f"CI is {run.get('conclusion')} on {release_name}'s latest commit",
        )]
    return []


def render_text(report: Readiness) -> str:
    lines = [f"decision: {report.decision}"]
    for f in report.findings:
        lines.append(f"[{f.severity}] {f.rule} ({f.subject}): {f.message}")
    return "\n".join(lines)
