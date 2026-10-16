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

    def _agree(self, entry_id):
        entry = _entries()[entry_id]
        fixture_dir = _FIXTURES_ROOT / entry.id
        return registry.agree(entry, lambda glob: (fixture_dir / glob).read_text(encoding="utf-8"))

    def test_cmake_entry_reads_numeric_version(self):
        self.assertEqual(self._agree("cmake").release, (1, 4, 0))

    def test_cargo_entry_resolves_workspace_inheritance(self):
        self.assertEqual(self._agree("cargo").release, (1, 4, 0))

    def test_go_entry_is_tag_derived_not_file_based(self):
        entry = _entries()["go"]
        fixture_dir = _FIXTURES_ROOT / entry.id
        is_tag_derived = registry.is_tag_derived(
            entry, lambda glob: (fixture_dir / glob).read_text(encoding="utf-8")
        )
        self.assertTrue(is_tag_derived)
        self.assertEqual(entry.files, ())

    def test_dotnet_entry_resolves_directory_build_props_inheritance(self):
        self.assertEqual(self._agree("dotnet").release, (1, 4, 0))

    def test_ruby_entry_reads_version_rb_and_normalizes_pre(self):
        version = self._agree("ruby")
        self.assertEqual(version.release, (1, 4, 0))
        self.assertEqual(version.pre[0], "pre")

    def test_composer_entry_is_tag_derived(self):
        entry = _entries()["composer"]
        fixture_dir = _FIXTURES_ROOT / entry.id
        self.assertTrue(
            registry.is_tag_derived(entry, lambda glob: (fixture_dir / glob).read_text(encoding="utf-8"))
        )

    def test_elixir_entry_reads_mix_exs(self):
        self.assertEqual(self._agree("elixir").release, (1, 4, 0))

    def test_ocaml_entry_reads_opam_version(self):
        self.assertEqual(self._agree("ocaml").release, (1, 4, 0))

    def test_haskell_entry_reads_cabal_version(self):
        self.assertEqual(self._agree("haskell").release, (1, 4, 0))

    def test_apple_entry_reads_cfbundleversion(self):
        self.assertEqual(self._agree("apple").release, (1, 4, 0))

    def test_android_entry_reads_gradle_version_name(self):
        self.assertEqual(self._agree("android").release, (1, 4, 0))

    def test_tauri_entry_reads_json_version(self):
        self.assertEqual(self._agree("tauri").release, (1, 4, 0))

    def test_helm_entry_reads_chart_yaml_version(self):
        self.assertEqual(self._agree("helm").release, (1, 4, 0))

    def test_dart_entry_reads_pubspec_version(self):
        self.assertEqual(self._agree("dart").release, (1, 4, 0))

    def test_provisional_entries_gate_fail_to_warn(self):
        from steward.model import Severity

        for entry_id in ("dotnet", "elixir", "ocaml", "haskell", "android", "helm"):
            entry = _entries()[entry_id]
            self.assertEqual(entry.status, "provisional")
            self.assertEqual(registry.gate(entry, Severity.FAIL), Severity.WARN)

    def test_verified_entries_pass_fail_through(self):
        from steward.model import Severity

        for entry_id in ("cmake", "cargo", "go", "ruby", "composer", "apple", "tauri", "dart"):
            entry = _entries()[entry_id]
            self.assertEqual(entry.status, "verified")
            self.assertEqual(registry.gate(entry, Severity.FAIL), Severity.FAIL)


if __name__ == "__main__":
    unittest.main()
