# Environment Variables

A single reference for every environment variable in PyStack: what it does, where
it's read, and which environments it must be set in.

## How configuration is loaded

- **Backend** uses Pydantic settings (`backend/src/pystack_api/core/config.py`).
  Variables use the `PYSTACK_` prefix, with `.env` (repo root or `backend/`) read
  first, then real environment variables, then the Render dashboard in production.
  Several settings also accept their conventional un-prefixed name (e.g.
  `CLERK_SECRET_KEY`) via `AliasChoices`.
- **Frontend** uses Vite. Only `VITE_*` variables reach the browser, and they are
  **baked into the bundle at build time** — changing one requires a rebuild.
- **Local `.env`** is gitignored. `.env.example` and `.env.prod.example` are
  committed as templates. Only set values in `.env` that differ from the defaults
  below; the defaults are what you get when a variable is unset.

Legend for the "Set in" column:
**Local** = your `.env` / shell · **CI** = GitHub Actions · **Render** = Render
dashboard / blueprint · **—** = relies on the default.

## Backend (`PYSTACK_` settings)

| Variable | Aliases | Default | Required? | Set in | Purpose |
|---|---|---|---|---|---|
| `PYSTACK_DATABASE_URL` | — | `postgresql://pystack:pystack@localhost:5432/pystack_dev` | Yes (prod) | Local (default), Render (`fromDatabase`) | Primary database connection string. |
| `PYSTACK_TEST_DATABASE_URL` | — | `postgresql://pystack:pystack@localhost:5432/pystack_test` | For tests | Local (default), CI (service DB) | Database used by the test suite. |
| `PYSTACK_CORS_ORIGINS` | — | `["http://localhost:5173"]` | Yes (prod) | Local (default), Render (value) | JSON list of origins allowed to call the API. |
| `PYSTACK_CLERK_AUTHORIZED_PARTIES` | — | `["http://localhost:5173"]` | Yes (prod) | Local (default), Render (value) | JSON list of origins permitted to present Clerk session tokens. Fails closed; `["*"]` disables the check (used by auth tests). |
| `PYSTACK_OPENROUTER_API_KEY` | `OPENROUTER_API_KEY` | _none_ | Yes | Local, Render (`sync: false`) | OpenRouter key powering the assistant. App raises at startup if missing. |
| `PYSTACK_ASSISTANT_MODEL` | `OPENROUTER_MODEL` | `openai/gpt-oss-20b:free` | No | — (default everywhere) | Model id for the assistant. Not declared in Render, so prod runs the free default unless overridden. |
| `PYSTACK_CLERK_SECRET_KEY` | `CLERK_SECRET_KEY` | _none_ | Yes | Local, CI (secret), Render (`sync: false`) | Clerk backend key; verifies session tokens server-side. |
| `PYSTACK_SENTRY_DSN` | `SENTRY_DSN` | _none_ | No | Local (optional), Render (`sync: false`) | Backend Sentry DSN. Unset = Sentry stays a no-op. |
| `PYSTACK_ENVIRONMENT` | — | `development` | No | Render (`production`) | Tags Sentry events by environment. Only consumed by Sentry. |

`app_name` and `api_prefix` are also Pydantic settings but are effectively
constants — there's no reason to override them via the environment.

## Frontend (`VITE_*`, build-time)

| Variable | Default | Required? | Set in | Purpose |
|---|---|---|---|---|
| `VITE_CLERK_PUBLISHABLE_KEY` | _none_ | Yes | Local, CI (secret), Render (`sync: false`) | Clerk publishable key. Safe to expose in the bundle. Use the `pk_live_` key in prod. |
| `VITE_API_URL` | _empty_ (dev uses the Vite proxy) | Prod only | Render (value) | Backend base URL the SPA calls in production. |
| `VITE_SENTRY_DSN` | _none_ | No | Local (optional), Render (`sync: false`) | Frontend Sentry DSN. Write-only; shipped in the bundle. |

## End-to-end tests (Playwright)

| Variable | Required? | Set in | Purpose |
|---|---|---|---|
| `CLERK_TEST_USER_USERNAME` | For e2e | Local (optional), CI (secret) | Test user email for scripted Clerk sign-in. |
| `CLERK_TEST_USER_PASSWORD` | For e2e | Local (optional), CI (secret) | Test user password. Configure the user without MFA. |
| `CI` | Auto | CI (provided by runner) | Read by `playwright.config.ts` to adjust retries/reuse. Not something you set manually. |

## Deployment & database tooling

| Variable | Required? | Set in | Purpose |
|---|---|---|---|
| `RENDER_API_KEY` | For infra/migrations | CI (secret), Local (optional) | Authenticates `scripts/render_infra.py` and Render-API database discovery. |
| `DBMATE_PROD_DATABASE_URL` | No (override) | CI (optional), Local (optional) | Bypasses Render-API discovery for prod DBmate commands. Normally unneeded. |
| `RENDER_CLI_CONFIG_PATH` | No (override) | Local (optional) | Overrides the Render CLI config path (default `~/.render/cli.yaml`). |
| `PORT` | Auto | Render (provided) | Port uvicorn binds to in the Render start command. |
| `POSTGRES_PORT` | No | Local (optional) | Host port for the local Postgres container (`compose.yaml`, default `5432`). |

`DBMATE_DEV_DATABASE_URL` and `DBMATE_TEST_DATABASE_URL` are **hardcoded in the
`Makefile`**, not environment-configurable — they exist only to drive the dbmate
CLI against the local dev/test databases.

## Secrets that must be set manually in Render

These use `sync: false` in `infra/render.yaml`, so the blueprint does **not** sync
them. Set each in the Render dashboard (this keeps forks from inheriting secrets):

- `PYSTACK_OPENROUTER_API_KEY`
- `PYSTACK_CLERK_SECRET_KEY`
- `PYSTACK_SENTRY_DSN`
- `VITE_CLERK_PUBLISHABLE_KEY`
- `VITE_SENTRY_DSN`

## Minimum to run locally

Everything else falls back to a sensible default, so a working local `.env` needs
only the values that have no default:

```dotenv
PYSTACK_OPENROUTER_API_KEY=...
VITE_CLERK_PUBLISHABLE_KEY=pk_test_...
PYSTACK_CLERK_SECRET_KEY=sk_test_...
# Optional — only for the Playwright e2e suite (make test-e2e):
CLERK_TEST_USER_USERNAME=...
CLERK_TEST_USER_PASSWORD=...
# Optional — enable Sentry in dev:
PYSTACK_SENTRY_DSN=
VITE_SENTRY_DSN=
```

Run `make doctor` (or `make doctor-dev` / `make doctor-services`) to check whether
the required variables are present for your target environment.
