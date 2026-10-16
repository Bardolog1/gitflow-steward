# Bug routing

## Five criteria for a critical bug

In a released version or a release candidate, a bug is critical when it
meets any of:

1. It loses or corrupts user data.
2. It opens a security vulnerability.
3. It makes a core function unusable without a reasonable workaround.
4. It breaks installation, upgrade, or release integrity.
5. It critically affects the user experience, per the UX test below.

Every other bug is non-critical.

## The typical-user UX test

A bug is critical on UX grounds when a typical user cannot complete a core
task of the product, or would reasonably abandon the product or lose trust
in it. Read `core_tasks` from `.gitflow.toml` to know what the product
considers a core task.

Qualifying signals:

- The main screen or flow is unreadable or unusable.
- Main controls are unresponsive or unreachable.
- A misleading state causes the user to act wrongly.
- A crash or failure occurs inside the main flow.
- An accessibility barrier blocks the main task.
- A visual defect hides essential content.

Not critical on UX grounds alone: misalignment or colors that do not block
reading or use, log-only warnings, minor delays.

## When severity is ambiguous

If the five criteria and the declared `core_tasks` do not settle it — ask
the developer. Never default an ambiguous bug to critical or non-critical.
This is the main thread's question to ask, not something either subagent
decides alone.

## Routing

- **Critical, found in a released version** → `hotfix/*` from `main`.
- **Critical, found in a release candidate** → `bugfix/*` targeting the
  open `release/*` branch, not `hotfix/*`.
- **Non-critical** → record it (in the audit/readiness output or a
  referenced issue) and route its fix through `feature/*` from `develop`
  for the next release. Never an immediate hotfix or release-targeted
  bugfix.
