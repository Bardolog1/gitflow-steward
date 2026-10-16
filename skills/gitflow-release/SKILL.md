---
name: gitflow-release
description: Git Flow model, bug routing, writing standards, and question sequencing for release work with the gitflow-steward agents.
---

# gitflow-release

Loaded by `release-auditor` and `release-operator`. This skill holds the
shared knowledge both agents act on; it does not run commands itself.

## References

- `references/model.md` — the Git Flow branch model both agents audit
  against and operate within.
- `references/bug-routing.md` — the five critical-bug criteria, the
  typical-user UX test, and the routing rules.
- `references/writing.md` — prose standards for anything either agent
  writes (release notes, PR descriptions, commit messages).
- `references/release-notes.md` — the three notes modes, the eight guided
  questions, and when to confirm the mode.

## Question sequencing (main-thread responsibility)

Subagents cannot hold an interactive dialogue with the developer — only
the main thread asks questions. When `release-operator` or
`release-auditor` reaches a point that needs developer input, it returns
control to the main thread with the question; it does not block waiting
for an answer itself.

Three places this happens:

1. **Notes mode confirmation.** At every release, before writing any
   notes, state the mode that applies (configured default or engine
   default) and ask the developer to confirm or change it. Never assume
   the configured default without this confirmation.
2. **The eight guided questions**, asked in the fixed order documented in
   `references/release-notes.md`, only when guided mode is confirmed.
3. **Ambiguous bug severity.** When a bug does not clearly meet or fail the
   five critical-bug criteria from `references/bug-routing.md` given the
   project's declared `core_tasks`, ask the developer to classify it. Never
   default an ambiguous bug to critical or non-critical.
