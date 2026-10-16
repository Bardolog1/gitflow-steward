"""Bug routing: the five critical-bug criteria, the UX typical-user test, and branch assignment."""
from dataclasses import dataclass

UNDETERMINED = "undetermined"
CRITICAL = "critical"
NON_CRITICAL = "non-critical"

# Qualifying UX signals (spec: "Qualifying signals include...").
_UX_CRITICAL_SIGNALS = frozenset({
    "unreadable-main-flow",
    "unresponsive-controls",
    "misleading-state",
    "crash-in-main-flow",
    "accessibility-barrier",
    "hides-essential-content",
})

# Signals the spec explicitly excludes from critical (misalignment, log-only, minor delay).
_UX_NON_CRITICAL_SIGNALS = frozenset({
    "cosmetic-misalignment",
    "log-only-warning",
    "minor-delay",
})


@dataclass(frozen=True)
class BugReport:
    data_loss: bool = False
    security: bool = False
    core_function_unusable: bool = False
    breaks_install_or_release: bool = False
    ux_signal: str | None = None
    task: str | None = None


def classify(report: BugReport, core_tasks: tuple[str, ...] = ()) -> str:
    """Classify a bug as "critical", "non-critical", or "undetermined" (never guess)."""
    if report.data_loss or report.security or report.core_function_unusable or report.breaks_install_or_release:
        return CRITICAL

    if report.ux_signal is None:
        return NON_CRITICAL

    if report.ux_signal in _UX_NON_CRITICAL_SIGNALS:
        return NON_CRITICAL

    if report.ux_signal not in _UX_CRITICAL_SIGNALS:
        return UNDETERMINED

    # A qualifying UX signal is only critical when it hits a declared core task.
    if not core_tasks or report.task is None:
        return UNDETERMINED
    return CRITICAL if report.task in core_tasks else NON_CRITICAL


@dataclass(frozen=True)
class RoutingPlan:
    branch_type: str  # "hotfix" | "bugfix" | "feature"
    from_branch: str


class RoutingError(RuntimeError):
    pass


def route(severity: str, stage: str, *, open_release: str | None = None) -> RoutingPlan:
    """Assign a branch plan for a classified bug. `stage` is "released" or "rc"."""
    if severity == UNDETERMINED:
        raise RoutingError("severity is undetermined; ask the developer before routing")

    if severity == CRITICAL:
        if stage == "released":
            return RoutingPlan(branch_type="hotfix", from_branch="main")
        if stage == "rc":
            if not open_release:
                raise RoutingError("a critical bug in an RC needs the open release branch name")
            return RoutingPlan(branch_type="bugfix", from_branch=open_release)
        raise RoutingError(f"unknown stage: {stage!r}")

    if severity == NON_CRITICAL:
        return RoutingPlan(branch_type="feature", from_branch="develop")

    raise RoutingError(f"unknown severity: {severity!r}")
