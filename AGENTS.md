# Repository Instructions

## Ephemeral files

- When dev tooling produces ephemeral, low-value output — logs, test results,
  traces, scratch files — write it under the OS temp directory rather than the
  repo. Prefer configuring a tool's output path (e.g. Playwright's `outputDir`)
  over adding the directory to `.gitignore`.

## Commits

- Keep commits focused around one coherent theme.
- Before every commit, inspect the complete staged file list and staged diff.
- Confirm each staged file belongs in Git and remove accidental local, secret,
  cache, build, coverage, dependency, or generated artifacts before committing.
- Commit lockfiles and intentionally versioned generated artifacts, including the
  frontend API client, when their source inputs change.
