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
disposable and replace it with your own application. Authentication is
intentionally left out; hosted deployment is declared for Render with a
versioned Blueprint and a Make target that reconciles post-creation settings.

## Stack

**Backend**

- [FastAPI](https://fastapi.tiangolo.com/) and [Pydantic](https://docs.pydantic.dev/) — HTTP layer and request/response models
- [Psycopg 3](https://www.psycopg.org/psycopg3/) — PostgreSQL access through dedicated query modules instead of an ORM
- [DBmate](https://github.com/amacneil/dbmate) — schema migrations as plain SQL, with a committed `db/schema.sql` snapshot
- [uv](https://docs.astral.sh/uv/) — manages the Python runtime and dependencies
- [Ruff](https://docs.astral.sh/ruff/) and [mypy](https://mypy-lang.org/) — linting, formatting, and strict type checking
- [pytest](https://docs.pytest.org/) — integration tests that plan every registered query against a migrated test database

**Frontend**

- [Vite](https://vite.dev/), [React 19](https://react.dev/), and [TypeScript](https://www.typescriptlang.org/)
- [Tailwind CSS v4](https://tailwindcss.com/) — utility-first styling through the official Vite plugin
- [shadcn/ui](https://ui.shadcn.com/) — Radix UI-based components vendored into `frontend/src/components/ui/`; only the components in use are kept, pull more with `npx shadcn add`
- [Lucide](https://lucide.dev/) — icon set
- [assistant-ui](https://www.assistant-ui.com/) — chat primitives for the optional Assistant pane
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

Python itself does not need to be installed globally. `uv` installs a managed
Python 3.14 runtime and creates `backend/.venv`. npm dependencies stay in
`frontend/node_modules`.

## Quick Start

Clone the repository, then from its root run:

```bash
make setup
make dev
```

`make setup` installs backend and frontend dependencies, starts PostgreSQL,
migrates the development and test databases, generates the frontend API client,
and installs the repository pre-commit hook. Re-running it is safe and does not
delete development data.

Boards are per-user, so there is no seed data: each account starts with an empty
board on first sign-in.

`make dev` starts both development servers:

- API at `http://localhost:8000` (interactive docs at `http://localhost:8000/docs`)
- Frontend at `http://localhost:5173`

The single PostgreSQL container hosts `pystack_dev` and `pystack_test` on the
same port. Tests never touch the development database.

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
without it. `CLERK_SECRET_KEY` is also accepted.

## Optional Assistant

The board includes an opt-in Assistant UI chat pane that can inspect and mutate
tasks through backend tool calls. `.env.example` is the versioned template with
safe defaults; copy those values into ignored `.env` for local settings and
secrets.

The API validates assistant configuration during app startup. To run the app
with the assistant enabled, set an OpenRouter API key in `.env`:

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
   `PYSTACK_CLERK_SECRET_KEY`, and the frontend's `VITE_CLERK_PUBLISHABLE_KEY`.
   Paste the production OpenRouter key and your Clerk production instance keys
   there, then wait for provisioning to finish.
2. Reconcile post-creation settings and run non-mutating health checks:

```bash
render login
make infra
```

3. Apply production database migrations:

```bash
make db-migrate-prod
```

`make infra` is the repeatable reconciliation step. It validates the Blueprint,
discovers the deployed Render service URLs, syncs derived runtime values such as
`PYSTACK_CORS_ORIGINS` and `VITE_API_URL`, deploys services whose env vars
changed, and runs non-mutating health checks. Re-running it is safe: unchanged
env vars are left alone and no deploy is triggered unless a service
configuration value changes. It intentionally does not set
`PYSTACK_OPENROUTER_API_KEY`, so a local personal key cannot overwrite the
production key entered in Render.

Production database commands also use Render discovery. `make db-status-prod`,
`make db-migrate-prod`, and `make psql-prod` resolve the external Render
Postgres URL at runtime from the Render API, then pass it to DBmate or psql
without writing it to a local file. Set `DBMATE_PROD_DATABASE_URL` in the shell
only if you need to override Render discovery.

## Make Commands

Run `make help` for the full list. The most useful targets:

**Setup and servers**

```bash
make setup          # set up a fresh checkout end to end
make dev            # run the backend and frontend dev servers together
make api            # run only the FastAPI dev server
make frontend       # run only the Vite dev server
```

**Database**

```bash
make db-up          # start the local PostgreSQL server and wait until healthy
make db-down        # stop local services without deleting data
make db-migrate     # migrate both the dev and test databases
make db-status      # show DBmate migration status
make db-dump-schema # refresh the committed db/schema.sql snapshot
make db-reset       # destructively reset and migrate local databases
```

**Infrastructure**

```bash
make infra          # reconcile Render env vars and health-check the deployment
```

**Code generation**

```bash
make generate-api   # export OpenAPI and regenerate the typed frontend client
```

**Quality checks**

```bash
make test           # run backend and frontend tests
make lint           # run backend and frontend linters
make format         # format backend and frontend source
make typecheck      # run mypy and the TypeScript type checker
make build          # build the production frontend
make check-secrets  # scan the full Git history for secrets
make pre-commit     # run every pre-commit hook against tracked files
make check          # run the complete verification suite
```

`make check` runs the same gate you should pass before pushing: it confirms the
generated client and schema snapshot are current, checks formatting, lints,
type-checks, runs all tests, builds the frontend, and scans for secrets.

## License

[MIT](LICENSE)
