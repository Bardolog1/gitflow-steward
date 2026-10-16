import json
import os
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Plain "bash" on Windows can resolve to the WSL stub (System32\bash.exe),
# which is not a real shell and prints a WSL-install message instead of
# running the script. Prefer CLAUDE_CODE_GIT_BASH_PATH, then the standard
# Git for Windows install location, over the bare "bash" lookup.
_GIT_BASH_CANDIDATES = [
    os.environ.get("CLAUDE_CODE_GIT_BASH_PATH"),
    r"C:\Program Files\Git\bin\bash.exe",
    "bash",
]


def _find_real_bash() -> str | None:
    for candidate in _GIT_BASH_CANDIDATES:
        if not candidate:
            continue
        try:
            result = subprocess.run(
                [candidate, "-c", "echo gitflow-steward-bash-check"],
                capture_output=True, text=True, timeout=10,
            )
        except (FileNotFoundError, OSError):
            continue
        if result.returncode == 0 and "gitflow-steward-bash-check" in result.stdout:
            return candidate
    return None


BASH = _find_real_bash()


def _bash_available() -> bool:
    return BASH is not None


@unittest.skipUnless(_bash_available(), "bash not available for the launcher smoke test")
class LauncherSmokeTests(unittest.TestCase):
    def test_hook_readonly_runs_through_the_real_launcher(self):
        result = subprocess.run(
            [BASH, str(REPO_ROOT / "bin" / "steward"), "hook", "readonly"],
            input='{"tool_input": {"command": "pwd"}, "cwd": "."}',
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(
            payload["hookSpecificOutput"]["permissionDecision"], "allow"
        )

    def test_audit_runs_through_the_real_launcher(self):
        result = subprocess.run(
            [BASH, str(REPO_ROOT / "bin" / "steward"), "audit", "--json"],
            cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=30,
        )
        payload = json.loads(result.stdout)
        self.assertEqual(payload["command"], "audit")


if __name__ == "__main__":
    unittest.main()
