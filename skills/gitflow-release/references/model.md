# Git Flow model

- `main` holds released versions only. Every commit on `main` is reachable
  from a final tag.
- `develop` is the integration branch. `feature/*` branches from and
  merges back into `develop`.
- `release/*` branches from `develop` when a release is being prepared.
  It takes RC tags (`v<version>-rc.<n>`, annotated only) and, once
  promoted, a final tag (`v<version>`) on `main`. At most one `release/*`
  branch is open at a time.
- `bugfix/*` branches only from an open `release/*` branch, to fix a
  critical bug found in an RC, and merges back into that release branch.
- `hotfix/*` branches from `main`, for a critical bug found in a released
  version. It merges into `main` (with a new patch tag) and, if a
  `release/*` branch happens to be open, also into that release branch —
  never directly into `develop`.
- All merges into `develop`, `release/*`, and `main` are non-fast-forward
  (`--no-ff`), so history preserves the branch structure.
- After a promotion, `main` is back-merged into `develop` so develop never
  falls behind a shipped release.
- Tags are annotated, never reused, never moved or deleted once pushed.
  MINOR increments by one at a time pre-1.0.
