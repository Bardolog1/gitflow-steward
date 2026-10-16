import tempfile
import unittest
from pathlib import Path

from steward.model import Severity
from steward.versions import registry
from steward.versions.readers import AmbiguousMatchError
from steward.versions.schema import Entry, FileSpec, Inherit, SchemaError


def _npm_entry(**overrides) -> Entry:
    base = dict(
        id="npm",
        name="npm",
        status="verified",
        docs="https://docs.npmjs.com/cli/v10/configuring-npm/package-json#version",
        detect=("package.json",),
        files=(FileSpec(glob="package.json", kind="json", key="version"),),
        scheme="semver",
        excludes=("package-lock.json",),
    )
    base.update(overrides)
    return Entry(**base)


class LoadTests(unittest.TestCase):
    def test_loads_entries_from_registry_toml_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            registry_dir = Path(tmp)
            (registry_dir / "js.toml").write_text(
                '[[entry]]\n'
                'id = "npm"\n'
                'name = "npm"\n'
                'status = "verified"\n'
                'docs = "https://docs.npmjs.com/cli/v10/configuring-npm/package-json#version"\n'
                'detect = ["package.json"]\n'
                'scheme = "semver"\n'
                'excludes = ["package-lock.json"]\n'
                '\n'
                '[[entry.files]]\n'
                'glob = "package.json"\n'
                'kind = "json"\n'
                'key = "version"\n',
                encoding="utf-8",
            )
            with tempfile.TemporaryDirectory() as root:
                entries = registry.load(root, registry_dir=registry_dir)
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0].id, "npm")
            self.assertEqual(entries[0].files[0].kind, "json")

    def test_extension_entries_from_gitflow_toml_default_to_provisional(self):
        with tempfile.TemporaryDirectory() as tmp:
            registry_dir = Path(tmp)
            with tempfile.TemporaryDirectory() as root:
                (Path(root) / ".gitflow.toml").write_text(
                    '[versions]\n'
                    '[[versions.entry]]\n'
                    'id = "custom"\n'
                    'name = "Custom ecosystem"\n'
                    'docs = "https://example.invalid/custom/docs"\n'
                    'detect = ["custom.ver"]\n'
                    'scheme = "numeric"\n'
                    '\n'
                    '[[versions.entry.files]]\n'
                    'glob = "custom.ver"\n'
                    'kind = "text"\n',
                    encoding="utf-8",
                )
                entries = registry.load(root, registry_dir=registry_dir)
            self.assertEqual(entries[0].id, "custom")
            self.assertEqual(entries[0].status, "provisional")

    def test_duplicate_ids_across_files_raise(self):
        with tempfile.TemporaryDirectory() as tmp:
            registry_dir = Path(tmp)
            entry_toml = (
                '[[entry]]\n'
                'id = "dup"\n'
                'name = "dup"\n'
                'status = "verified"\n'
                'docs = "https://example.invalid/docs"\n'
                'detect = ["f"]\n'
                'scheme = "numeric"\n'
                '\n'
                '[[entry.files]]\n'
                'glob = "f"\n'
                'kind = "text"\n'
            )
            (registry_dir / "a.toml").write_text(entry_toml, encoding="utf-8")
            (registry_dir / "b.toml").write_text(entry_toml, encoding="utf-8")
            with tempfile.TemporaryDirectory() as root:
                with self.assertRaises(SchemaError):
                    registry.load(root, registry_dir=registry_dir)


class DetectTests(unittest.TestCase):
    def test_matches_detect_glob_against_tracked_files(self):
        entry = _npm_entry()
        matches = registry.detect(entry, ("package.json", "README.md"))
        self.assertEqual(matches, ("package.json",))

    def test_excludes_lock_files(self):
        entry = _npm_entry()
        matches = registry.detect(entry, ("package.json", "package-lock.json"))
        self.assertEqual(matches, ("package.json",))

    def test_global_excludes_skip_node_modules(self):
        entry = _npm_entry(detect=("**/package.json",))
        matches = registry.detect(entry, ("node_modules/x/package.json", "package.json"))
        self.assertEqual(matches, ("package.json",))


class ResolveTests(unittest.TestCase):
    def test_resolves_plain_file(self):
        spec = FileSpec(glob="package.json", kind="json", key="version")
        value = registry.resolve(spec, lambda glob: '{"version": "1.0.0"}')
        self.assertEqual(value, "1.0.0")

    def test_follows_one_hop_inheritance(self):
        source = FileSpec(glob="pom.xml", kind="xml", key="./properties/revision")
        spec = FileSpec(
            glob="module/pom.xml",
            kind="xml",
            key="./version",
            inherits=(Inherit(when=r"^\$\{revision\}$", source=source),),
        )

        def read_file(glob: str) -> str:
            if glob == "module/pom.xml":
                return "<project><version>${revision}</version></project>"
            return "<project><properties><revision>2.1.0</revision></properties></project>"

        self.assertEqual(registry.resolve(spec, read_file), "2.1.0")

    def test_unresolved_when_file_missing(self):
        spec = FileSpec(glob="missing.json", kind="json", key="version")
        with self.assertRaises(registry.UnresolvedError):
            registry.resolve(spec, lambda glob: None)


class AgreeTests(unittest.TestCase):
    def test_single_file_entry_agrees_with_itself(self):
        entry = _npm_entry()
        version = registry.agree(entry, lambda glob: '{"version": "1.0.0"}')
        self.assertEqual(version.release, (1, 0, 0))

    def test_extra_agree_file_mismatch_raises_disagreement(self):
        entry = _npm_entry(extra_agree=(FileSpec(glob="VERSION", kind="text"),))

        def read_file(glob: str) -> str:
            return '{"version": "1.0.0"}' if glob == "package.json" else "2.0.0"

        with self.assertRaises(registry.DisagreementError):
            registry.agree(entry, read_file)

    def test_extra_agree_file_match_succeeds(self):
        entry = _npm_entry(extra_agree=(FileSpec(glob="VERSION", kind="text"),))

        def read_file(glob: str) -> str:
            return '{"version": "1.0.0"}' if glob == "package.json" else "1.0.0"

        version = registry.agree(entry, read_file)
        self.assertEqual(version.release, (1, 0, 0))


class GateTests(unittest.TestCase):
    def test_verified_entry_keeps_fail(self):
        entry = _npm_entry(status="verified")
        self.assertEqual(registry.gate(entry, Severity.FAIL), Severity.FAIL)

    def test_provisional_entry_caps_fail_at_warn(self):
        entry = _npm_entry(status="provisional")
        self.assertEqual(registry.gate(entry, Severity.FAIL), Severity.WARN)

    def test_provisional_entry_keeps_info(self):
        entry = _npm_entry(status="provisional")
        self.assertEqual(registry.gate(entry, Severity.INFO), Severity.INFO)


class TagDerivedTests(unittest.TestCase):
    def test_resolvable_marker_means_tag_derived(self):
        marker = FileSpec(glob="go.mod", kind="regex", pattern=r"^module\s+(\S+)$")
        entry = _npm_entry(files=(), tag_derived=(marker,))
        self.assertTrue(registry.is_tag_derived(entry, lambda glob: "module example.com/x"))

    def test_unresolvable_marker_means_not_tag_derived(self):
        marker = FileSpec(glob="go.mod", kind="json", key="version")
        entry = _npm_entry(files=(), tag_derived=(marker,))
        self.assertFalse(registry.is_tag_derived(entry, lambda glob: None))


if __name__ == "__main__":
    unittest.main()
