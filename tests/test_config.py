import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from steward.config import Config, ConfigError, load


class LoadDefaultsTests(unittest.TestCase):
    def test_no_file_returns_builtin_defaults(self):
        with TemporaryDirectory() as root:
            config = load(root)
        self.assertEqual(config, Config())
        self.assertEqual(config.rc_minimum, 1)
        self.assertEqual(config.soak_days, 0)
        self.assertFalse(config.parallel_releases)
        self.assertEqual(config.core_tasks, ())
        self.assertIsNone(config.source)


class LoadOverridesTests(unittest.TestCase):
    def test_configured_rc_minimum_wins(self):
        with TemporaryDirectory() as root:
            Path(root, ".gitflow.toml").write_text("rc_minimum = 2\n", encoding="utf-8")
            config = load(root)
        self.assertEqual(config.rc_minimum, 2)
        self.assertEqual(config.source, str(Path(root, ".gitflow.toml")))

    def test_core_tasks_and_notes_mode(self):
        with TemporaryDirectory() as root:
            Path(root, ".gitflow.toml").write_text(
                'core_tasks = ["checkout", "login"]\nnotes_mode = "guided"\n', encoding="utf-8"
            )
            config = load(root)
        self.assertEqual(config.core_tasks, ("checkout", "login"))
        self.assertEqual(config.notes_mode, "guided")


class MalformedConfigTests(unittest.TestCase):
    def test_invalid_toml_raises_configerror_naming_file(self):
        with TemporaryDirectory() as root:
            path = Path(root, ".gitflow.toml")
            path.write_text("this is not [valid toml\n", encoding="utf-8")
            with self.assertRaises(ConfigError) as ctx:
                load(root)
        self.assertIn(str(path), str(ctx.exception))


class ValidationTests(unittest.TestCase):
    def test_negative_soak_days_rejected(self):
        with TemporaryDirectory() as root:
            Path(root, ".gitflow.toml").write_text("soak_days = -1\n", encoding="utf-8")
            with self.assertRaises(ConfigError):
                load(root)

    def test_rc_minimum_below_one_rejected(self):
        with TemporaryDirectory() as root:
            Path(root, ".gitflow.toml").write_text("rc_minimum = 0\n", encoding="utf-8")
            with self.assertRaises(ConfigError):
                load(root)

    def test_invalid_notes_mode_rejected(self):
        with TemporaryDirectory() as root:
            Path(root, ".gitflow.toml").write_text('notes_mode = "chaos"\n', encoding="utf-8")
            with self.assertRaises(ConfigError):
                load(root)


class ParallelReleasesTests(unittest.TestCase):
    def test_true_is_forced_false_with_warning(self):
        with TemporaryDirectory() as root:
            Path(root, ".gitflow.toml").write_text("parallel_releases = true\n", encoding="utf-8")
            config = load(root)
        self.assertFalse(config.parallel_releases)
        self.assertTrue(any("parallel_releases" in w for w in config.warnings))


if __name__ == "__main__":
    unittest.main()
