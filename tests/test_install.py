import importlib.util
import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

_SOURCE_ROOT = Path(__file__).resolve().parent.parent
_SPEC = importlib.util.spec_from_file_location("install", _SOURCE_ROOT / "install.py")
install = importlib.util.module_from_spec(_SPEC)
sys.modules["install"] = install
_SPEC.loader.exec_module(install)


def _dst_paths(actions):
    return sorted(a.dst for a in actions)


class PlanEntriesTests(unittest.TestCase):
    def test_covers_agents_skill_and_engine_groups(self):
        entries = list(install._iter_source_files(_SOURCE_ROOT))
        dsts = [dst for _src, dst in entries]
        self.assertIn("agents/release-auditor.md", dsts)
        self.assertIn("skills/gitflow-release/SKILL.md", dsts)
        self.assertIn("gitflow-steward/steward_cli.py", dsts)
        self.assertIn("gitflow-steward/bin/steward", dsts)
        self.assertIn("gitflow-steward/steward/model.py", dsts)
        self.assertFalse(any("__pycache__" in dst for dst in dsts))
        self.assertFalse(any(dst.endswith(".pyc") for dst in dsts))


class DryRunTests(unittest.TestCase):
    def test_dry_run_writes_nothing_and_matches_real_install(self):
        with TemporaryDirectory() as target_a, TemporaryDirectory() as target_b:
            target_a = Path(target_a) / ".claude"
            target_b = Path(target_b) / ".claude"

            plan = install.compute_plan(_SOURCE_ROOT, target_a, None)
            self.assertFalse(target_a.exists())

            code = install.apply_plan(plan, target_b, (target_b / "gitflow-steward").as_posix(), force=False)
            self.assertEqual(code, 0)

            real_plan = install.compute_plan(_SOURCE_ROOT, target_b, None)
            self.assertEqual(_dst_paths(plan), _dst_paths(real_plan) or _dst_paths(plan))
            installed = sorted(
                str(p.relative_to(target_b).as_posix())
                for p in target_b.rglob("*")
                if p.is_file() and p.name != "install-manifest.json"
            )
            self.assertEqual(installed, _dst_paths(plan))


class RewriteTests(unittest.TestCase):
    def test_steward_home_placeholder_rewritten_in_md_only(self):
        with TemporaryDirectory() as target:
            target = Path(target) / ".claude"
            steward_home = (target / "gitflow-steward").as_posix()
            plan = install.compute_plan(_SOURCE_ROOT, target, None)
            install.apply_plan(plan, target, steward_home, force=False)

            auditor = (target / "agents" / "release-auditor.md").read_text(encoding="utf-8")
            self.assertNotIn("{{STEWARD_HOME}}", auditor)
            self.assertIn(steward_home, auditor)

    def test_rejects_quote_in_steward_home(self):
        with TemporaryDirectory() as target:
            target = Path(target) / ".claude" / 'bad"name'
            plan = install.compute_plan(_SOURCE_ROOT, target, None)
            with self.assertRaises(install.InstallError):
                install.apply_plan(plan, target, (target / "gitflow-steward").as_posix(), force=False)

    def test_rejects_unresolved_placeholder(self):
        with self.assertRaises(install.InstallError):
            install.rewrite_steward_home("still {{STEWARD_HOME}} and {{OTHER}}", "C:/home")


class ConflictTests(unittest.TestCase):
    def test_second_install_without_force_refuses_edited_file(self):
        with TemporaryDirectory() as target:
            target = Path(target) / ".claude"
            steward_home = (target / "gitflow-steward").as_posix()
            plan = install.compute_plan(_SOURCE_ROOT, target, None)
            install.apply_plan(plan, target, steward_home, force=False)

            edited = target / "agents" / "release-auditor.md"
            edited.write_text("hand edited\n", encoding="utf-8")

            manifest = install.read_manifest(target)
            plan2 = install.compute_plan(_SOURCE_ROOT, target, manifest)
            conflicts = [a for a in plan2 if a.op is install.Op.SKIP_CONFLICT]
            self.assertTrue(any(a.dst == "agents/release-auditor.md" for a in conflicts))

            code = install.apply_plan(plan2, target, steward_home, force=False)
            self.assertEqual(code, 1)
            self.assertEqual(edited.read_text(encoding="utf-8"), "hand edited\n")

    def test_force_overwrites_edited_file(self):
        with TemporaryDirectory() as target:
            target = Path(target) / ".claude"
            steward_home = (target / "gitflow-steward").as_posix()
            plan = install.compute_plan(_SOURCE_ROOT, target, None)
            install.apply_plan(plan, target, steward_home, force=False)

            edited = target / "agents" / "release-auditor.md"
            edited.write_text("hand edited\n", encoding="utf-8")

            manifest = install.read_manifest(target)
            plan2 = install.compute_plan(_SOURCE_ROOT, target, manifest)
            code = install.apply_plan(plan2, target, steward_home, force=True)
            self.assertEqual(code, 0)
            self.assertNotEqual(edited.read_text(encoding="utf-8"), "hand edited\n")


class UninstallTests(unittest.TestCase):
    def test_uninstall_removes_tracked_files_and_manifest(self):
        with TemporaryDirectory() as target:
            target = Path(target) / ".claude"
            steward_home = (target / "gitflow-steward").as_posix()
            plan = install.compute_plan(_SOURCE_ROOT, target, None)
            install.apply_plan(plan, target, steward_home, force=False)

            install.uninstall(target, force=False)

            self.assertFalse((target / "agents" / "release-auditor.md").exists())
            self.assertFalse((target / "gitflow-steward" / "install-manifest.json").exists())

    def test_uninstall_skips_edited_file_without_force(self):
        with TemporaryDirectory() as target:
            target = Path(target) / ".claude"
            steward_home = (target / "gitflow-steward").as_posix()
            plan = install.compute_plan(_SOURCE_ROOT, target, None)
            install.apply_plan(plan, target, steward_home, force=False)

            edited = target / "agents" / "release-auditor.md"
            edited.write_text("hand edited\n", encoding="utf-8")

            install.uninstall(target, force=False)
            self.assertTrue(edited.exists())


class SymlinkAndPluginTests(unittest.TestCase):
    def test_no_symlinks_and_no_plugin_manifest(self):
        with TemporaryDirectory() as target:
            target = Path(target) / ".claude"
            steward_home = (target / "gitflow-steward").as_posix()
            plan = install.compute_plan(_SOURCE_ROOT, target, None)
            install.apply_plan(plan, target, steward_home, force=False)

            for path in target.rglob("*"):
                if path.is_file():
                    self.assertFalse(path.is_symlink())
            self.assertFalse((target / "plugin.json").exists())
            self.assertFalse((target / ".claude-plugin").exists())


class ProjectScopedTests(unittest.TestCase):
    def test_resolve_target_honors_project_flag(self):
        self.assertEqual(install._resolve_target("/tmp/some-repo"), Path("/tmp/some-repo") / ".claude")

    def test_resolve_target_honors_config_dir_env(self):
        original = __import__("os").environ.get("CLAUDE_CONFIG_DIR")
        try:
            __import__("os").environ["CLAUDE_CONFIG_DIR"] = "/tmp/custom-config"
            self.assertEqual(install._resolve_target(None), Path("/tmp/custom-config"))
        finally:
            if original is None:
                __import__("os").environ.pop("CLAUDE_CONFIG_DIR", None)
            else:
                __import__("os").environ["CLAUDE_CONFIG_DIR"] = original


class MainCliTests(unittest.TestCase):
    def test_dry_run_prints_plan_and_exits_zero(self):
        with TemporaryDirectory() as target:
            target = Path(target) / ".claude"
            code = install.main(["--project", str(target.parent), "--dry-run"])
        self.assertEqual(code, 0)
        self.assertFalse(target.exists())

    def test_full_cycle_through_main(self):
        with TemporaryDirectory() as root:
            project = Path(root)
            code = install.main(["--project", str(project)])
            self.assertEqual(code, 0)
            self.assertTrue((project / ".claude" / "agents" / "release-auditor.md").exists())

            code = install.main(["--project", str(project), "--uninstall"])
            self.assertEqual(code, 0)
            self.assertFalse((project / ".claude" / "agents" / "release-auditor.md").exists())


if __name__ == "__main__":
    unittest.main()
