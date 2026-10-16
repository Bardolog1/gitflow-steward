# gitflow-steward

A Git Flow release manager for [Claude Code](https://claude.com/claude-code). It audits a repository's branches, tags, and version files against the Git Flow model, reports release readiness, routes bugs to the right branch type, drafts release notes, and lints release-notes prose — all read-only by default, with every irreversible git or `gh` operation held for explicit approval.

## Why

GitHub Free private repositories have no server-side branch or tag protection. An agent (or a developer) can branch `bugfix/*` from `develop` instead of an open `release/*`, commit directly onto a release branch, skip a back-merge, or tag the wrong branch, and nothing stops it. gitflow-steward is the check that runs before those mistakes reach `main`.

## What it does

- **Audit** (`steward audit`): branch origins and merge rules, tag and version-registry consistency, drift between `develop` and the last release, stale branches (reported, never deleted).
- **Readiness** (`steward readiness`): go/no-go for promoting a release from open bugfix branches, blocker-labeled issues, CI status (via `gh`, when available), RC count, and soak time.
- **Route** (`steward route`): applies five criteria to decide whether a bug is critical, and if so whether it needs a hotfix from `main` or a bugfix against the open release candidate.
- **Notes** (`steward notes`): manual, guided (eight questions), or automatic (from Conventional Commits) release notes.
- **Lint** (`steward lint`): a prose linter for release notes with a fixed FAIL list (emoji, hype words, AI attribution) and heuristic WARN checks, backed by an editable rules file.
- **Guards**: two PreToolUse hooks. `readonly_guard` keeps the auditor agent to read-only commands; `push_guard` intercepts pushes, tag pushes, merges into `main`, branch deletion, and `gh release`/`gh pr merge`, and turns them into an explicit confirmation.

The engine (`steward/`) is stdlib-only Python, no third-party dependencies. It talks to git by shelling out, never by parsing output speculatively, and reads GitHub state through `gh` only when `gh` is on the PATH.

## Install

```
python install.py
```

This copies the agents, skill, and engine into `$CLAUDE_CONFIG_DIR` (or `~/.claude` if unset), rewriting the `{{STEWARD_HOME}}` placeholder in every installed Markdown file to the install's absolute path. Use `--project <path>` to install into a project's `.claude` directory instead of the user-level one.

Other flags:

- `--dry-run` — print the install plan, write nothing.
- `--force` — overwrite files that were edited since the last install (without it, a conflicting file is reported and left untouched).
- `--uninstall` — remove only the files recorded in the install manifest whose content still matches what was installed; edited files are skipped unless `--force` is also given.

After installing, two agents are available in Claude Code: `release-auditor` (read-only) and `release-operator` (plans and, on approval, executes release steps).

## Requirements

- Python 3.11 or later, stdlib only.
- `git`.
- `gh` (optional; readiness checks and some operator steps degrade gracefully without it).
- Claude Code, for the agents and PreToolUse hooks. The hook launcher (`bin/steward`) runs under Git Bash on Windows.

## Configuration

An optional `.gitflow.toml` at the repository root tunes defaults: minimum release-candidate count before promotion, soak days, the notes mode, and `core_tasks` used by the critical-bug test. See `specs/configuration/spec.md` for the full schema.

## Testing

```
python -m unittest discover -s tests -v
```

Tests build real git repositories in temporary directories (including paths with spaces) and feed real PreToolUse JSON into the hook launcher — no mocked git plumbing.

## License

MIT. See [LICENSE](LICENSE).
