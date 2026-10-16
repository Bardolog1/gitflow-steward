import unittest

from steward.versions.schemes import VersionError, parse


class SemverTests(unittest.TestCase):
    def test_parses_plain_release(self):
        v = parse("semver", "1.2.3")
        self.assertEqual(v.release, (1, 2, 3))
        self.assertIsNone(v.pre)

    def test_strips_build_metadata_from_equality(self):
        a = parse("semver", "1.2.3+build.5")
        b = parse("semver", "1.2.3+build.9")
        self.assertEqual(a, b)

    def test_prerelease_sorts_before_release(self):
        pre = parse("semver", "1.2.3-rc.1")
        final = parse("semver", "1.2.3")
        self.assertLess(pre, final)

    def test_rejects_invalid_string(self):
        with self.assertRaises(VersionError):
            parse("semver", "not-a-version")


class Pep440Tests(unittest.TestCase):
    def test_parses_plain_release(self):
        v = parse("pep440", "1.2.3")
        self.assertEqual(v.release, (1, 2, 3))

    def test_normalizes_prerelease_spelling(self):
        alpha = parse("pep440", "1.2.3alpha1")
        short = parse("pep440", "1.2.3a1")
        self.assertEqual(alpha, short)

    def test_dev_release_sorts_before_final(self):
        dev = parse("pep440", "1.2.3.dev1")
        final = parse("pep440", "1.2.3")
        self.assertLess(dev, final)


class RubygemsTests(unittest.TestCase):
    def test_parses_plain_release(self):
        v = parse("rubygems", "1.4.0")
        self.assertEqual(v.release, (1, 4, 0))

    def test_hyphen_is_read_as_pre(self):
        v = parse("rubygems", "1.4.0-rc.2")
        self.assertEqual(v.pre, ("pre", 0))

    def test_prerelease_sorts_before_release(self):
        pre = parse("rubygems", "1.4.0-rc.2")
        final = parse("rubygems", "1.4.0")
        self.assertLess(pre, final)


class MavenTests(unittest.TestCase):
    def test_parses_plain_release(self):
        v = parse("maven", "1.2.3")
        self.assertEqual(v.release, (1, 2, 3))

    def test_snapshot_marks_dev(self):
        v = parse("maven", "1.2.3-SNAPSHOT")
        self.assertTrue(v.dev)

    def test_snapshot_sorts_before_release(self):
        snapshot = parse("maven", "1.2.3-SNAPSHOT")
        final = parse("maven", "1.2.3")
        self.assertLess(snapshot, final)


class NumericTests(unittest.TestCase):
    def test_parses_two_part_release(self):
        v = parse("numeric", "12.4")
        self.assertEqual(v.release, (12, 4))

    def test_rejects_too_many_parts(self):
        with self.assertRaises(VersionError):
            parse("numeric", "1.2.3.4", numeric_parts=3)

    def test_accepts_within_declared_parts(self):
        v = parse("numeric", "1.2.3", numeric_parts=3)
        self.assertEqual(v.release, (1, 2, 3))


if __name__ == "__main__":
    unittest.main()
