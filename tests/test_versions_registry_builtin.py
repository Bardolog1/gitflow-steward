"""Validates the representative built-in registry subset (task 3.5) against its fixtures."""
import unittest
from pathlib import Path

from steward.versions import registry
from steward.versions.schema import validate_fixtures

_REPO_ROOT = Path(__file__).parent.parent
_FIXTURES_ROOT = Path(__file__).parent / "fixtures" / "versions"


def _entries() -> dict[str, "Entry"]:
    return {entry.id: entry for entry in registry.load(str(_REPO_ROOT))}


class BuiltinRegistryTests(unittest.TestCase):
    def test_every_entry_has_a_fixture_directory(self):
        validate_fixtures(tuple(_entries().values()), _FIXTURES_ROOT)

    def test_npm_entry_reads_its_fixture(self):
        entry = _entries()["npm"]
        fixture_dir = _FIXTURES_ROOT / entry.id
        version = registry.agree(entry, lambda glob: (fixture_dir / glob).read_text(encoding="utf-8"))
        self.assertEqual(version.release, (1, 4, 0))

    def test_python_entry_reads_its_fixture_and_normalizes_rc(self):
        entry = _entries()["python"]
        fixture_dir = _FIXTURES_ROOT / entry.id
        version = registry.agree(entry, lambda glob: (fixture_dir / glob).read_text(encoding="utf-8"))
        self.assertEqual(version.release, (1, 4, 0))
        self.assertEqual(version.pre, ("rc", 2))

    def test_maven_entry_resolves_revision_inheritance_from_its_fixture(self):
        entry = _entries()["maven"]
        fixture_dir = _FIXTURES_ROOT / entry.id
        version = registry.agree(entry, lambda glob: (fixture_dir / glob).read_text(encoding="utf-8"))
        self.assertEqual(version.release, (1, 4, 0))
        self.assertTrue(version.dev)


if __name__ == "__main__":
    unittest.main()
