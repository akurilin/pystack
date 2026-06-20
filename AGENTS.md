# Repository Instructions

- Do not over-engineer, prematurely abstract, prematurely optimize or future-proof.
  Use simple, elegant, maintainable solutions.
- Add comments and documentaiton to solutions that may be non-obvious to future readers.

## Commits

- Work in main unless asked otherwise
- Commit or push only when asked to
- Keep commits focused around one coherent theme.
- Commit lockfiles and intentionally versioned generated artifacts, including the
  frontend API client, when their source inputs change.

## Frontend

- The frontend uses shadcn/ui, but only the components needed so far live under
  `frontend/src/components/ui/`. Assume the full registry is still available:
  pull any additional component on demand with `npx shadcn add <component>`
  rather than hand-writing one or assuming it is missing.

## Database

- Our migrations get automatically applied to production at successful CI run
  completion on main

## Testing

- Avoid writing tests that are ceremony rather than signal. More tests is not
  better if you're barely getting value out of them.

## Infrastructure

- The infra should be fully declared in code and not require the user to ever
  manually update it, with exception for the very first blueprint selection
  in the Render UI
