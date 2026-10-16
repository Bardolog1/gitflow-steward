import re
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SELF_PATH = Path(__file__).resolve().relative_to(REPO_ROOT).as_posix()

ATTRIBUTION_PATTERNS = (
    "Co-Authored-By",
    "Generated with",
    "claude.ai/code",
    "Claude-Session",
    "claude.ai/session",
)

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
EMAIL_ALLOWLIST_DOMAINS = ("example.com", "example.org", "example.invalid", "users.noreply.github.com")

PERSONAL_PATH_PATTERNS = (
    "Libardo y Empresa MytCodex",
    "C:\\Users\\libar",
    "C:/Users/libar",
    "/home/libar",
    "/Users/libar",
)


def tracked_files():
    output = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
    ).stdout
    return [p for p in output.decode("utf-8").split("\0") if p and p != SELF_PATH]


def read_text(path):
    try:
        return (REPO_ROOT / path).read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None


class HygieneTests(unittest.TestCase):
    def test_no_ai_attribution_strings(self):
        offenders = []
        for path in tracked_files():
            text = read_text(path)
            if text is None:
                continue
            for pattern in ATTRIBUTION_PATTERNS:
                if pattern in text:
                    offenders.append((path, pattern))
        self.assertEqual(offenders, [], f"AI attribution strings found: {offenders}")

    def test_no_real_email_addresses(self):
        offenders = []
        for path in tracked_files():
            text = read_text(path)
            if text is None:
                continue
            for match in EMAIL_RE.findall(text):
                if not match.lower().endswith(EMAIL_ALLOWLIST_DOMAINS):
                    offenders.append((path, match))
        self.assertEqual(offenders, [], f"non-allowlisted email addresses found: {offenders}")

    def test_no_personal_filesystem_paths(self):
        offenders = []
        for path in tracked_files():
            text = read_text(path)
            if text is None:
                continue
            for pattern in PERSONAL_PATH_PATTERNS:
                if pattern in text:
                    offenders.append((path, pattern))
        self.assertEqual(offenders, [], f"personal filesystem paths found: {offenders}")


if __name__ == "__main__":
    unittest.main()
