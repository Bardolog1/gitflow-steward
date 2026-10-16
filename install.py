"""Installs gitflow-steward into a Claude Code config directory. Stdlib only."""
import argparse
import hashlib
import json
import os
import sys
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

_GROUPS = (
    ("agents", "agents"),
    ("skills/gitflow-release", "skills/gitflow-release"),
    ("steward", "gitflow-steward/steward"),
)
_SINGLE_FILES = (
    ("steward_cli.py", "gitflow-steward/steward_cli.py"),
    ("bin/steward", "gitflow-steward/bin/steward"),
)

_MANIFEST_VERSION = 1


class InstallError(RuntimeError):
    pass


class Op(StrEnum):
    WRITE = "WRITE"
    OVERWRITE = "OVERWRITE"
    SKIP_CONFLICT = "SKIP_CONFLICT"


@dataclass(frozen=True)
class Action:
    op: Op
    src: Path
    dst: str


def _iter_source_files(source_root: Path):
    for src_sub, dst_sub in _GROUPS:
        src_dir = source_root / src_sub
        for path in sorted(src_dir.rglob("*")):
            if path.is_dir() or "__pycache__" in path.parts or path.suffix == ".pyc":
                continue
            rel = path.relative_to(src_dir).as_posix()
            yield path, f"{dst_sub}/{rel}"
    for src_sub, dst_sub in _SINGLE_FILES:
        yield source_root / src_sub, dst_sub


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _manifest_path(target: Path) -> Path:
    return target / "gitflow-steward" / "install-manifest.json"


def read_manifest(target: Path) -> dict | None:
    path = _manifest_path(target)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def write_manifest(target: Path, files: list[dict]) -> None:
    path = _manifest_path(target)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"version": _MANIFEST_VERSION, "root": str(target), "files": files}
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def rewrite_steward_home(text: str, steward_home: str) -> str:
    rewritten = text.replace("{{STEWARD_HOME}}", steward_home)
    if "{{" in rewritten:
        raise InstallError(f"unresolved placeholder remains after rewriting: {rewritten!r}")
    return rewritten


def compute_plan(source_root: Path, target: Path, manifest: dict | None) -> list[Action]:
    previous = {f["path"]: f["sha256"] for f in (manifest or {}).get("files", ())}
    actions = []
    for src, dst in _iter_source_files(source_root):
        dest_path = target / dst
        if not dest_path.exists():
            op = Op.WRITE
        elif previous.get(dst) == _sha256_file(dest_path):
            op = Op.OVERWRITE
        else:
            op = Op.SKIP_CONFLICT
        actions.append(Action(op, src, dst))
    return actions


def apply_plan(actions: list[Action], target: Path, steward_home: str, force: bool) -> int:
    if '"' in steward_home:
        raise InstallError(f"STEWARD_HOME path contains a double quote: {steward_home}")

    conflicts = [a for a in actions if a.op is Op.SKIP_CONFLICT]
    if conflicts and not force:
        for action in conflicts:
            print(f"conflict, use --force to overwrite: {target / action.dst}", file=sys.stderr)
        return 1

    manifest_files = []
    for action in actions:
        dest = target / action.dst
        dest.parent.mkdir(parents=True, exist_ok=True)
        if action.src.suffix == ".md":
            content = rewrite_steward_home(action.src.read_text(encoding="utf-8"), steward_home).encode("utf-8")
        else:
            content = action.src.read_bytes()
        dest.write_bytes(content)
        manifest_files.append({"path": action.dst, "sha256": hashlib.sha256(content).hexdigest()})

    write_manifest(target, manifest_files)
    return 0


def _prune_empty_dirs(target: Path) -> None:
    for path in sorted(target.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if path.is_dir() and not any(path.iterdir()):
            path.rmdir()


def uninstall(target: Path, force: bool) -> int:
    manifest = read_manifest(target)
    if manifest is None:
        return 0

    for entry in manifest["files"]:
        path = target / entry["path"]
        if not path.exists():
            continue
        if force or _sha256_file(path) == entry["sha256"]:
            path.unlink()
        else:
            print(f"skipped (edited since install): {path}", file=sys.stderr)

    _manifest_path(target).unlink(missing_ok=True)
    _prune_empty_dirs(target)
    return 0


def _resolve_target(project: str | None) -> Path:
    if project:
        return Path(project) / ".claude"
    config_dir = os.environ.get("CLAUDE_CONFIG_DIR")
    if config_dir:
        return Path(config_dir)
    return Path.home() / ".claude"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="install.py")
    parser.add_argument("--project", help="install under <path>/.claude instead of the user's Claude Code home")
    parser.add_argument("--dry-run", action="store_true", help="print the plan and write nothing")
    parser.add_argument("--force", action="store_true", help="overwrite conflicting files")
    parser.add_argument("--uninstall", action="store_true", help="remove previously installed files")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    target = _resolve_target(args.project)
    source_root = Path(__file__).resolve().parent

    if args.uninstall:
        return uninstall(target, args.force)

    manifest = read_manifest(target)
    actions = compute_plan(source_root, target, manifest)

    if args.dry_run:
        for action in actions:
            print(f"{action.op.value} {action.dst}")
        return 0

    steward_home = (target / "gitflow-steward").as_posix()
    try:
        return apply_plan(actions, target, steward_home, args.force)
    except InstallError as exc:
        print(f"install aborted: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
