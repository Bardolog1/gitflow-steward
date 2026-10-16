"""Optional gh CLI reader. Absence is an INFO finding, never an exception."""
import json
import os
import shutil
import subprocess

from steward.model import Finding, Severity

GH_MISSING = Finding(
    rule="gh.unavailable",
    severity=Severity.INFO,
    subject="gh",
    message="gh CLI not found; CI status and issue checks are skipped.",
)


class GhError(RuntimeError):
    pass


def is_available() -> bool:
    return shutil.which("gh") is not None


def run_json(*args: str) -> object | None:
    """Run a gh command and parse its JSON stdout. None when gh is missing."""
    if not is_available():
        return None
    env = dict(os.environ)
    env["GIT_TERMINAL_PROMPT"] = "0"
    result = subprocess.run(["gh", *args], capture_output=True, text=True, env=env)
    if result.returncode != 0:
        raise GhError(result.stderr.strip())
    return json.loads(result.stdout) if result.stdout.strip() else None
