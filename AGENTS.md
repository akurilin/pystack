# Repository Instructions

## Commits

- Keep commits focused around one coherent theme.
- Before every commit, inspect the complete staged file list and staged diff.
- Confirm each staged file belongs in Git and remove accidental local, secret,
  cache, build, coverage, dependency, or generated artifacts before committing.
- Commit lockfiles and intentionally versioned generated artifacts, including the
  frontend API client, when their source inputs change.

## Frontend

- The frontend uses shadcn/ui, but only the components needed so far live under
  `frontend/src/components/ui/`. Assume the full registry is still available:
  pull any additional component on demand with `npx shadcn add <component>`
  rather than hand-writing one or assuming it is missing.
