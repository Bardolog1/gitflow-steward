from dataclasses import dataclass, field
from enum import StrEnum


class Severity(StrEnum):
    FAIL = "FAIL"
    WARN = "WARN"
    INFO = "INFO"


@dataclass(frozen=True)
class Finding:
    rule: str
    severity: Severity
    subject: str
    message: str
    fix: str | None = None
    evidence: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Report:
    findings: tuple[Finding, ...] = ()

    def summary(self) -> dict[str, int]:
        counts = {"fail": 0, "warn": 0, "info": 0}
        for finding in self.findings:
            counts[finding.severity.lower()] += 1
        return counts

    def has_fail(self) -> bool:
        return any(finding.severity == Severity.FAIL for finding in self.findings)
