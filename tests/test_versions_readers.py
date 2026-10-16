import unittest

from steward.versions.readers import AmbiguousMatchError, KeyNotFoundError, ReadError, read
from steward.versions.schema import FileSpec


class JsonReaderTests(unittest.TestCase):
    def test_reads_dotted_key(self):
        spec = FileSpec(glob="package.json", kind="json", key="version")
        self.assertEqual(read(spec, '{"version": "1.2.3"}'), "1.2.3")

    def test_missing_key_raises(self):
        spec = FileSpec(glob="package.json", kind="json", key="version")
        with self.assertRaises(KeyNotFoundError):
            read(spec, "{}")


class TomlReaderTests(unittest.TestCase):
    def test_reads_nested_key(self):
        spec = FileSpec(glob="pyproject.toml", kind="toml", key="project.version")
        self.assertEqual(read(spec, "[project]\nversion = \"2.0.0\"\n"), "2.0.0")


class XmlReaderTests(unittest.TestCase):
    def test_reads_element_text_ignoring_default_namespace(self):
        spec = FileSpec(glob="pom.xml", kind="xml", key="./version")
        xml = (
            '<project xmlns="http://maven.apache.org/POM/4.0.0">'
            "<version>1.3.0</version></project>"
        )
        self.assertEqual(read(spec, xml), "1.3.0")

    def test_refuses_doctype(self):
        spec = FileSpec(glob="pom.xml", kind="xml", key="./version")
        xml = '<!DOCTYPE project><project><version>1.0.0</version></project>'
        with self.assertRaises(ReadError):
            read(spec, xml)


class RegexReaderTests(unittest.TestCase):
    def test_reads_single_capture(self):
        spec = FileSpec(glob="CMakeLists.txt", kind="regex", pattern=r"^project\(\w+ VERSION (\S+)\)$")
        self.assertEqual(read(spec, "project(demo VERSION 1.4.0)"), "1.4.0")

    def test_strips_hash_comments_before_matching(self):
        spec = FileSpec(
            glob="f.txt", kind="regex", pattern=r"^version\s*=\s*(\S+)$", strip_comments="hash"
        )
        content = "# version = 9.9.9 (decoy)\nversion = 1.0.0\n"
        self.assertEqual(read(spec, content), "1.0.0")

    def test_multiple_distinct_matches_raise_ambiguous(self):
        spec = FileSpec(glob="f.txt", kind="regex", pattern=r"^version\s*=\s*(\S+)$")
        content = "version = 1.0.0\nversion = 2.0.0\n"
        with self.assertRaises(AmbiguousMatchError):
            read(spec, content)

    def test_identical_matches_are_not_ambiguous(self):
        spec = FileSpec(glob="f.txt", kind="regex", pattern=r"^version\s*=\s*(\S+)$")
        content = "version = 1.0.0\nversion = 1.0.0\n"
        self.assertEqual(read(spec, content), "1.0.0")


class TextReaderTests(unittest.TestCase):
    def test_reads_stripped_whole_file(self):
        spec = FileSpec(glob="VERSION", kind="text", key=None)
        self.assertEqual(read(spec, "1.2.3\n"), "1.2.3")


if __name__ == "__main__":
    unittest.main()
