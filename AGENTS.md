# Repository Instructions

- Do not over-engineer, prematurely abstract, prematurely optimize or future-proof.
  Use simple, elegant, maintainable solutions.
- Add comments and documentaiton to solutions that may be non-obvious to future readers.

## Commits

- Keep commits focused around one coherent theme.
- Commit lockfiles and intentionally versioned generated artifacts, including the
  frontend API client, when their source inputs change.

## Frontend

- The frontend uses shadcn/ui, but only the components needed so far live under
  `frontend/src/components/ui/`. Assume the full registry is still available:
  pull any additional component on demand with `npx shadcn add <component>`
  rather than hand-writing one or assuming it is missing.
