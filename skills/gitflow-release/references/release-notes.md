# Release notes

Three modes: manual, guided, automatic.

## Mode confirmation (always, every release)

Before writing anything, state which mode applies — the `.gitflow.toml`
`notes_mode` default, or the engine default if none is set — and ask the
developer to confirm it or pick another mode. Never draft under a
configured default without this confirmation.

Example: "This project is set to automatic notes. Keep that, or switch to
guided or manual for this release?"

## Automatic mode

```
bash "{{STEWARD_HOME}}/bin/steward" notes draft --mode automatic --from <prev-tag> --to <release-rev>
```

Drafts from Conventional Commits between the previous tag and the release
commit, grouped by type (Breaking, Features, Fixes, Performance, Other).
No questions asked.

## Guided mode

Fetch the fixed question set:

```
bash "{{STEWARD_HOME}}/bin/steward" notes questions --json
```

Ask exactly these eight questions, in this order:

1. One-sentence summary: what is this release, in one sentence?
2. Are there breaking changes? If yes, describe them and the upgrade steps
   a user must take.
3. What was added?
4. What changed (non-breaking behavior changes)?
5. What was deprecated?
6. What was removed?
7. What was fixed, including any security fixes?
8. Are there known issues to carry forward into this release's notes?

An empty answer to questions 3-8 omits that section from the draft (it
does not render an empty section). Questions 1 and 2 always render — an
empty answer to question 2 still renders a Breaking Changes section.

Submit the answers as JSON on stdin, keyed by the `slot` field from
`notes questions`:

```
bash "{{STEWARD_HOME}}/bin/steward" notes draft --mode guided --answers -
```

## Manual mode

The developer writes the notes directly. Run them through `notes check
--file <path>` for structural validation and through `lint` for prose
standards before review.

## Review before publishing

Show the finished draft to the developer. Do not publish through `gh
release` without their approval — that push is also gated by `push_guard`
independently.

```
bash "{{STEWARD_HOME}}/bin/steward" notes check --file <path>
```

If `gh` is unavailable, the notes are written to a file in the repository
for manual publishing instead of being attached to a release automatically.
