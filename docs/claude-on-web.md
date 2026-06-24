# Claude Code on the web

This document describes how to configure a [Claude Code on the web](https://code.claude.com/docs/en/claude-code-on-the-web)
cloud environment so the agent can build the stack, run a real Postgres, and run
`make check` against it — without waiting on CI for the feedback loop.

## What runs in the sandbox, and what doesn't

The cloud sandbox is meant for a fast, mostly-hermetic feedback loop, not a
byte-for-byte CI clone. We run the main gate, `make check`
(`test-backend test-frontend lint typecheck build` + schema/format/secret
checks), and leave the **Playwright e2e** suite (`make test-e2e`) to CI:

- `make check` never invokes Playwright, so skipping it costs nothing here and
  removes the single slowest install (the Chromium download + system deps).
- The backend half of `make check` **does** include real Clerk integration
  tests (`backend/tests/auth/test_clerk_auth.py`), so the sandbox is given a
  Clerk secret key and outbound access to `api.clerk.com` (see below).

## How the environment is configured

Configuration lives in two places — committed scripts in this repo, and a few
fields in the environment's settings dialog at claude.ai/code (network access,
env vars, and the setup-script command are UI-only).

### Committed to the repo

- `scripts/web-setup.sh` — one-time provisioning, run at environment creation.
- `scripts/web-session-start.sh` — per-session bootstrap (starts/migrates the DB,
  self-heals deps). Wired in via the `SessionStart` hook in `.claude/settings.json`
  and gated on `CLAUDE_CODE_REMOTE=true`, so it is a no-op on a local checkout.

### Set in the web UI (per environment)

**Setup script:**

```bash
bash scripts/web-setup.sh
```

**Network access:** select **Custom**, keep *"include default list of common
package managers"* checked (npm/PyPI/Go/Docker/GitHub), and add:

```
api.clerk.com
```

That single domain covers the backend Clerk tests, which mint tokens purely
through Clerk's Backend API. Only add more if you later widen scope:
`*.clerk.accounts.dev` (frontend sign-in, needed for e2e) and `openrouter.ai`
(real assistant calls — `make check` doesn't make any).

**Environment variables:** the backend reads `PYSTACK_*` straight from the
process environment (`backend/src/pystack_api/core/config.py`), so these are all
that's needed. Reuse your existing Clerk **dev** instance keys. Note: this field
is visible to anyone who can edit the environment — it is not a sealed secret
store, so keep it to dev/throwaway credentials.

```
PYSTACK_CLERK_SECRET_KEY=sk_test_...      # backend auth + Clerk integration tests
CLERK_TEST_USER_USERNAME=...              # the dev-instance test user (unprefixed)
VITE_CLERK_PUBLISHABLE_KEY=pk_test_...    # baked into the frontend build
PYSTACK_OPENROUTER_API_KEY=test-openrouter-key  # dummy: app startup only validates presence
```

The database URLs are omitted on purpose — the config defaults and the Makefile
already point at the local `pystack_dev` / `pystack_test` databases on
`localhost:5432`.

## The ~5-minute setup budget

The setup script is cached but must finish within roughly five minutes. Two
choices keep it well under that:

- **dbmate and gitleaks are downloaded as prebuilt binaries**, not compiled with
  `go install` as CI does — compilation alone can eat a couple of minutes.
- **Independent installs run in parallel** (`make backend-sync`,
  `make frontend-install`, `docker compose pull`), so wall-clock collapses toward
  the slowest single step rather than their sum. Expect ~1–2 minutes total.

If the environment ever fails to provision, check the setup log for a failed
download (e.g. a changed gitleaks release-asset name — there's a `go install`
fallback for that one) or a step that pushed past the cache budget.

## Running checks

Once an environment exists, ask the agent to run the gate:

```bash
make check          # the full hermetic + Clerk-backed gate
```

or target a faster subset during a tight loop, e.g. `make test-backend`,
`make test-frontend`, `make lint`, `make typecheck`.
