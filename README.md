# Pystack

[![CI](https://github.com/akurilin/pystack/actions/workflows/ci.yml/badge.svg)](https://github.com/akurilin/pystack/actions/workflows/ci.yml)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/akurilin/pystack)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.14](https://img.shields.io/badge/Python-3.14-3776AB?logo=python&logoColor=white)](https://www.python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React 19](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)](https://react.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?logo=typescript&logoColor=white)](https://www.typescriptlang.org)
[![PostgreSQL 18](https://img.shields.io/badge/PostgreSQL-18-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org)
[![lint: ruff](https://img.shields.io/badge/lint-ruff-D7FF64?logo=ruff&logoColor=black)](https://docs.astral.sh/ruff/)
[![style: prettier](https://img.shields.io/badge/style-prettier-ff69b4.svg)](https://prettier.io)
[![lint: eslint](https://img.shields.io/badge/lint-eslint-4B32C3.svg)](https://eslint.org)

Pystack is an opinionated scaffold for a modern Python and TypeScript web
application. It ships a FastAPI backend, a React frontend with a generated,
fully typed API client, a PostgreSQL database with plain-SQL migrations, and a
single Makefile that wires everything together for local development.

It is meant to be cloned and built on. The included Trello-style board is **not**
the point of the project — it is just an example of a small end-to-end app built
on the scaffold, a smoke test that exercises the full request path from a React
component through a typed client to a SQL-backed endpoint. Treat it as
disposable and replace it with your own application. Authentication is handled by
[Clerk](https://clerk.com), with every board private to its signed-in user;
hosted deployment is declared for Render with a versioned Blueprint and a Make
target that reconciles post-creation settings.

## Stack

**Backend**

- [FastAPI](https://fastapi.tiangolo.com/) and [Pydantic](https://docs.pydantic.dev/) — HTTP layer and request/response models
- [Psycopg 3](https://www.psycopg.org/psycopg3/) — PostgreSQL access through dedicated query modules instead of an ORM
- [DBmate](https://github.com/amacneil/dbmate) — schema migrations as plain SQL, with a committed `db/schema.sql` snapshot
- [uv](https://docs.astral.sh/uv/) — manages the Python runtime and dependencies
- [Ruff](https://docs.astral.sh/ruff/) and [mypy](https://mypy-lang.org/) — linting, formatting, and strict type checking
- [pytest](https://docs.pytest.org/) — integration tests that plan every registered query against a migrated test database
- [Clerk](https://clerk.com/) — authentication; the backend verifies session tokens and scopes every request to the signed-in user
- [Sentry](https://sentry.io/) — optional error monitoring, initialized only when a DSN is configured

**Frontend**

- [Vite](https://vite.dev/), [React 19](https://react.dev/), and [TypeScript](https://www.typescriptlang.org/)
- [Tailwind CSS v4](https://tailwindcss.com/) — utility-first styling through the official Vite plugin
- [shadcn/ui](https://ui.shadcn.com/) — Radix UI-based components vendored into `frontend/src/components/ui/`; only the components in use are kept, pull more with `npx shadcn add`
- [Lucide](https://lucide.dev/) — icon set
- [Clerk](https://clerk.com/) — authentication UI and session management via `@clerk/react`
- [Sentry](https://sentry.io/) — optional browser error monitoring via `@sentry/react`, enabled only when a DSN is configured
- [assistant-ui](https://www.assistant-ui.com/) — chat primitives for the Assistant pane
- [Hey API](https://heyapi.dev/) — generates the typed client from the backend's exported OpenAPI schema
- [TanStack Query](https://tanstack.com/query) — server-state management
- [Vitest](https://vitest.dev/) and [Testing Library](https://testing-library.com/) — component tests
- [Playwright](https://playwright.dev/) — end-to-end tests
- [ESLint](https://eslint.org/) and [Prettier](https://prettier.io/) — linting and formatting

**Tooling**

- [Docker Compose](https://docs.docker.com/compose/) — runs local PostgreSQL 18
- [Gitleaks](https://github.com/gitleaks/gitleaks) — secret scanning
- [pre-commit](https://pre-commit.com/) — Git hook for local checks
- [Render Blueprints](https://render.com/docs/infrastructure-as-code) — declared production infrastructure
- A repository doctor script — read-only checks for local tools, local database
  state, GitHub secrets, Render settings, and deployed service health
- A root `Makefile` — the single entry point for every common task

## Repository Layout

```text
backend/   FastAPI application and integration tests
bin/       Repository adapters for machine-level tools
db/        DBmate SQL migrations, schema snapshot, and local DB bootstrap
frontend/  React application, generated API client, and component tests
```

DBmate owns schema migrations as plain SQL. The backend uses dedicated Psycopg
query modules instead of an ORM, and backend tests ask PostgreSQL to plan every
registered query against the migrated test database. DBmate refreshes the
committed `db/schema.sql` snapshot after development migrations. Its `pg_dump`
calls are transparently delegated to the PostgreSQL 18 Compose container,
ensuring the client and server versions match.

## Prerequisites

Install these machine-level tools:

- [uv](https://docs.astral.sh/uv/)
- [DBmate](https://github.com/amacneil/dbmate)
- [Gitleaks](https://github.com/gitleaks/gitleaks)
- Node.js 24.16.0 (LTS; see `.node-version`) and npm
- Docker with Docker Compose
- Make

Hosted-service checks additionally use:

- [GitHub CLI](https://cli.github.com/) (`gh auth login`)
- [Render CLI](https://render.com/docs/cli) (`render login`)

Python itself does not need to be installed globally. `uv` installs a managed
Python 3.14 runtime and creates `backend/.venv`. npm dependencies stay in
`frontend/node_modules`.

## Quick Start

Clone the repository, then from its root run:

```bash
make setup
make doctor-dev
make dev
```

`make setup` installs backend and frontend dependencies, starts PostgreSQL,
migrates the development and test databases, generates the frontend API client,
and installs the repository pre-commit hook. Re-running it is safe and does not
delete development data.

`make doctor-dev` validates that the local toolchain, `.env`, dependencies,
Docker daemon, local PostgreSQL container, and DBmate migration state are ready
for development. It is read-only and exits nonzero only for failures; warnings
call out optional setup that affects narrower workflows such as Playwright e2e.

Boards are per-user, so there is no seed data: each account starts with an empty
board on first sign-in.

`make dev` starts both development servers:

- API at `http://localhost:8000` (interactive docs at `http://localhost:8000/docs`)
- Frontend at `http://localhost:5173`

The single PostgreSQL container hosts `pystack_dev` and `pystack_test` on the
same port. Tests never touch the development database.

## Doctor Checks

The repository includes lightweight doctor checks for the two common failure
surfaces: local development setup and hosted deployment wiring.

```bash
make doctor-dev       # local tools, env, dependencies, Docker, local DB, migrations
make doctor-services  # GitHub auth/secrets, Render config/env vars, deployed health
make doctor           # both
```

The service doctor is intentionally read-only: it validates the Render Blueprint,
live Render service settings, GitHub Actions secrets, backend database URL
wiring, CORS, and public health checks, but it does not deploy, mutate env vars,
or run database migrations. Output is colorized on interactive terminals and
respects `NO_COLOR`; pass `--color always` or `--color never` to
`scripts/doctor.py` for explicit control.

## Fork Checklist

Use this checklist when turning the scaffold into a product repository:

1. Rename the project surface:
   - Update the GitHub repository name, README badges, package names, page title,
     Render service names, database names, and any user-facing `Pystack` copy.
   - Update `app_name` in `backend/src/pystack_api/core/config.py` and decide
     whether to rename the Python package itself or keep the scaffold structure.
2. Replace the example app:
   - Treat the board and assistant as disposable examples unless they are part of
     the product.
   - Remove or rewrite the example routes, schemas, queries, migrations, tests,
     and generated frontend client paths that no longer match the product.
3. Create fresh vendor projects:
   - Clerk: create separate development and production instances, configure
     allowed origins, and create the dedicated Playwright test user without MFA.
   - Render: create the first Blueprint from `infra/render.yaml`, then use
     `make infra` for repeatable reconciliation after provisioning.
   - Sentry: create new frontend and backend projects if error reporting should
     be enabled; leave DSNs blank to keep it disabled.
   - OpenRouter: replace the smoke-test assistant model/key if the product keeps
     the assistant.
4. Set environment and secret values:
   - Update `.env.example` and `.env.prod.example` when the product's required
     configuration changes.
   - Store real secrets only in ignored `.env` files, GitHub Actions secrets, and
     Render environment variables marked `sync: false`.
   - Configure GitHub Actions secrets for CI and deployment checks:
     `PYSTACK_CLERK_SECRET_KEY`, `VITE_CLERK_PUBLISHABLE_KEY`,
     `CLERK_TEST_USER_USERNAME`, `CLERK_TEST_USER_PASSWORD`, and
     `RENDER_API_KEY`.
   - Re-check `PYSTACK_CORS_ORIGINS`, `PYSTACK_CLERK_AUTHORIZED_PARTIES`, and
     `VITE_API_URL` for every deployed origin.
5. Rework the database baseline:
   - Replace example migrations only while the product has no real deployed data.
     After production exists, use forward-only migrations.
   - Run `make db-migrate`, inspect `db/schema.sql`, and keep the schema snapshot
     committed with intentional migration changes.
6. Regenerate typed API clients after backend contract changes:
   - Run `make generate-api`.
   - Commit the generated files under `frontend/src/api/generated/` with the
     backend change that produced them.
7. Remove verification-only routes before launch:
   - Delete `/api/v1/sentry-test`, `/sentry-test`, and `/boundary-error-test`
     once Sentry and the app error boundary have been verified.
8. Re-run the full local gate:
   - `make setup` for a fresh machine or after tool changes.
   - `make doctor-dev` before starting local work on a new machine.
   - `make doctor-services` after hosted infrastructure or secret changes.
   - `make check` before pushing substantial scaffold changes.
   - `make test-e2e` when auth, routing, frontend state, or deployment wiring
     changes.
9. Update product documentation:
   - Replace scaffold-specific README text with product-specific setup notes.
   - Document any new vendors, manual bootstrap steps, operational runbooks, and
     data/privacy expectations.

## Authentication

The app uses [Clerk](https://clerk.com) for authentication. The only page a
signed-out visitor can reach is the public landing at `/`, which is just a login
box; the board lives at `/board` and is gated, so signed-out visitors are
redirected back to the landing. Each signed-in user gets their own private board:
tasks are owned by the Clerk user id (the JWT `sub` claim), and every API request
is scoped to the authenticated user.

To run locally, create a Clerk dev instance at
[dashboard.clerk.com](https://dashboard.clerk.com) and set its keys in `.env`
(both the backend and Vite read this single repo-root file):

```bash
PYSTACK_CLERK_SECRET_KEY=sk_test_...   # backend: verifies session tokens
VITE_CLERK_PUBLISHABLE_KEY=pk_test_... # frontend: initializes Clerk
```

The API validates the Clerk secret key during startup and refuses to boot
without it. `CLERK_SECRET_KEY` is also accepted. The backend also rejects session
tokens minted for an unexpected origin via `PYSTACK_CLERK_AUTHORIZED_PARTIES`,
which defaults to the local frontend and is reconciled to the deployed origins by
`make infra`.

The Playwright end-to-end suite signs in through Clerk, so it needs the keys
above plus a dedicated test user. Set its credentials in `.env`:

```bash
CLERK_TEST_USER_USERNAME=...
CLERK_TEST_USER_PASSWORD=...
```

Configure that user **without** multi-factor or device ("client trust")
verification so a scripted password sign-in completes in one step; otherwise the
sign-in stops at a second factor and the suite cannot proceed. `make test-e2e`
fails fast and lists any missing variables. In CI the same four values come from
repository secrets of the same names.

## Assistant

The board includes an Assistant chat pane that can inspect and mutate tasks
through backend tool calls. `.env.example` is the versioned template with safe
defaults; copy those values into ignored `.env` for local settings and secrets.

The API validates assistant configuration during startup and refuses to boot
without an OpenRouter API key, set in `.env`:

```bash
PYSTACK_OPENROUTER_API_KEY=...
```

`OPENROUTER_API_KEY` is also accepted. `PYSTACK_ASSISTANT_MODEL` is a public
default shown in `.env.example`; `OPENROUTER_MODEL` can override it locally. The
default model is intended for local smoke testing, not production quality.

## Render Infrastructure

Render is the default hosted deployment target for this scaffold. The
`infra/render.yaml` Blueprint declares the production infrastructure: the FastAPI
backend service, Vite frontend static site, and Render Postgres database. The
Blueprint wires Render-managed values such as `PYSTACK_DATABASE_URL` directly
from the database, while keeping external secrets out of Git.

There is one manual bootstrap step because Render's CLI validates Blueprints but
does not create the initial Blueprint connection:

1. In the Render Dashboard, create a Blueprint from this repository, the `main`
   branch, and `infra/render.yaml`. Render will ask for
   the env vars marked `sync: false` — `PYSTACK_OPENROUTER_API_KEY`,
   `PYSTACK_CLERK_SECRET_KEY`, the frontend's `VITE_CLERK_PUBLISHABLE_KEY`, and
   the optional Sentry DSNs (`PYSTACK_SENTRY_DSN`, `VITE_SENTRY_DSN`). Paste the
   production OpenRouter key and your Clerk production instance keys there; leave
   the Sentry DSNs blank to keep error monitoring off. Then wait for provisioning
   to finish.
2. Reconcile post-creation settings and run non-mutating health checks:

```bash
render login
make infra
```

3. Configure the repository secrets GitHub Actions needs:

   - `RENDER_API_KEY` — lets CI discover the Render Postgres connection string
     and run DBmate against production before Render deploys.
   - `PYSTACK_CLERK_SECRET_KEY`, `VITE_CLERK_PUBLISHABLE_KEY`,
     `CLERK_TEST_USER_USERNAME`, and `CLERK_TEST_USER_PASSWORD` — used by CI and
     e2e tests.
   - `DBMATE_PROD_DATABASE_URL` is optional. Set it only if you need CI or local
     production DBmate commands to bypass Render discovery.

4. Validate the hosted wiring:

```bash
make doctor-services
```

`make infra` is the repeatable reconciliation step. It validates the Blueprint,
discovers the deployed Render service URLs, syncs derived runtime values such as
`PYSTACK_CORS_ORIGINS`, `PYSTACK_CLERK_AUTHORIZED_PARTIES`, and `VITE_API_URL`,
deploys services whose env vars changed, and runs non-mutating health checks.
Re-running it is safe: unchanged env vars are left alone and no deploy is
triggered unless a service configuration value changes. It intentionally does not
set `PYSTACK_OPENROUTER_API_KEY`, so a local personal key cannot overwrite the
production key entered in Render.

Production migrations are automated through GitHub Actions while the scaffold is
compatible with Render's free tier. On each push to `main`, the
`Production DB Migrations` workflow job waits for the normal `check` and `e2e`
jobs, then runs `make db-migrate-prod`. The Render services use
`autoDeployTrigger: checksPass`, so Render deploys only after GitHub checks,
including the production migration job, have passed. `make db-migrate-prod`
remains available as a manual recovery/admin command, but it is not the normal
release path.

The intended paid Render setup is simpler: move DBmate into the backend service's
Render `preDeployCommand`, keep Render's auto-deploy trigger as the deployment
source of truth, and let Render block the deploy if migrations fail before the
new service starts. Use that path after upgrading the backend service and
Postgres database to plans that support pre-deploy commands and durable
production backups.

If you serve the frontend from a custom domain, set `FRONTEND_CUSTOM_ORIGIN` in
`scripts/render_infra.py` so `make infra` allows it for both CORS and Clerk
authorized parties, and point that domain at the Render static site. A Clerk
**production** instance additionally serves its Frontend API from a custom
subdomain (e.g. `clerk.yourdomain.com`); add the CNAME records Clerk lists under
its dashboard's Domains section, or sign-in fails to load in production because
the Clerk endpoints do not resolve.

Production database commands also use Render discovery. `make db-status-prod`,
`make db-migrate-prod`, and `make psql-prod` resolve the external Render
Postgres URL at runtime from the Render API, then pass it to DBmate or psql
without writing it to a local file. Set `DBMATE_PROD_DATABASE_URL` in the shell
only if you need to override Render discovery.

Note that the Render services set `rootDir` to `backend` and `frontend`, so a
database-only commit under `db/` runs the GitHub migration workflow but does not
force an application deploy. Include an app change when a migration must be
released with new application code.

## Make Commands

A root `Makefile` is the single entry point for common tasks. The essentials to
get started, run the app, and manage the database:

```bash
make setup       # set up a fresh checkout end to end
make doctor-dev  # verify local tools, env, Docker, and DB migration state
make dev         # run the backend and frontend dev servers together
make db-migrate  # migrate the development and test databases
make doctor      # verify local setup plus GitHub/Render deployment wiring
make check       # run the full verification gate before pushing
```

Run `make help` for the complete, grouped list, or read the `Makefile` directly.

## License

[MIT](LICENSE)
