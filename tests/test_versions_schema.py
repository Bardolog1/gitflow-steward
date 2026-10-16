import tempfile
import unittest
from pathlib import Path

from steward.versions.schema import Entry, FileSpec, Inherit, SchemaError, validate_fixtures


def _entry(**overrides) -> Entry:
    base = dict(
        id="npm",
        name="npm",
        status="verified",
        docs="https://docs.npmjs.com/cli/v10/configuring-npm/package-json#version",
        detect=("package.json",),
        files=(FileSpec(glob="package.json", kind="json", key="version"),),
        scheme="semver",
    )
    base.update(overrides)
    return Entry(**base)


class FileSpecTests(unittest.TestCase):
    def test_rejects_unknown_kind(self):
        with self.assertRaises(SchemaError):
            FileSpec(glob="f", kind="yaml", key="version")

    def test_json_kind_requires_key(self):
        with self.assertRaises(SchemaError):
            FileSpec(glob="f.json", kind="json")

    def test_regex_pattern_must_be_anchored(self):
        with self.assertRaises(SchemaError):
            FileSpec(glob="f", kind="regex", pattern=r"(\d+)")

    def test_regex_pattern_must_have_one_capture_group(self):
        with self.assertRaises(SchemaError):
            FileSpec(glob="f", kind="regex", pattern=r"^(\d+)\.(\d+)$")

    def test_text_kind_does_not_require_key(self):
        spec = FileSpec(glob="VERSION", kind="text")
        self.assertIsNone(spec.key)

    def test_valid_regex_spec_accepted(self):
        spec = FileSpec(glob="f", kind="regex", pattern=r"^version\s*=\s*(\S+)$")
        self.assertEqual(spec.pattern, r"^version\s*=\s*(\S+)$")

    def test_inherit_wraps_a_nested_filespec(self):
        source = FileSpec(glob="pom.xml", kind="xml", key="./properties/revision")
        inherit = Inherit(when=r"^\$\{revision\}$", source=source)
        self.assertIs(inherit.source, source)


class EntryTests(unittest.TestCase):
    def test_rejects_non_https_docs(self):
        with self.assertRaises(SchemaError):
            _entry(docs="http://example.invalid/docs")

    def test_rejects_invalid_status(self):
        with self.assertRaises(SchemaError):
            _entry(status="draft")

    def test_rejects_invalid_scheme(self):
        with self.assertRaises(SchemaError):
            _entry(scheme="calver")

    def test_requires_files_or_tag_derived(self):
        with self.assertRaises(SchemaError):
            _entry(files=())

    def test_tag_derived_alone_is_sufficient(self):
        marker = FileSpec(glob="go.mod", kind="regex", pattern=r"^version\s+(\S+)$", optional=True)
        entry = _entry(files=(), tag_derived=(marker,))
        self.assertEqual(entry.tag_derived, (marker,))

    def test_valid_entry_accepted(self):
        entry = _entry()
        self.assertEqual(entry.id, "npm")


class ValidateFixturesTests(unittest.TestCase):
    def test_raises_on_duplicate_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(SchemaError):
                validate_fixtures((_entry(), _entry()), Path(tmp))

    def test_raises_on_missing_fixture_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(SchemaError):
                validate_fixtures((_entry(),), Path(tmp))

    def test_passes_when_fixture_directory_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "npm").mkdir()
            validate_fixtures((_entry(),), Path(tmp))


if __name__ == "__main__":
    unittest.main()
