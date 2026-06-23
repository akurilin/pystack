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

## Contents

- [Stack](#stack)
- [Repository Layout](#repository-layout)
- [Example App](#example-app)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Authentication](#authentication)
- [Assistant](#assistant)
- [Doctor Checks](#doctor-checks)
- [Make Commands](#make-commands)
- [Render Infrastructure](#render-infrastructure)
- [Fork Checklist](#fork-checklist)
- [License](#license)

## Stack

**Backend**

- [FastAPI](https://fastapi.tiangolo.com/) and [Pydantic](https://docs.pydantic.dev/) — HTTP layer and request/response models
- [Pydantic AI](https://ai.pydantic.dev/) — assistant agent orchestration, typed tool schemas, and OpenRouter streaming
- [Psycopg 3](https://www.psycopg.org/psycopg3/) — PostgreSQL access through dedicated query modules instead of an ORM
- [DBmate](https://github.com/amacneil/dbmate) — schema migrations as plain SQL, with a committed `db/schema.sql` snapshot
- [uv](https://docs.astral.sh/uv/) — manages the Python runtime and dependencies
- [Ruff](https://docs.astral.sh/ruff/), [mypy](https://mypy-lang.org/), and [Pyright](https://microsoft.github.io/pyright/) — linting, formatting, and strict type checking
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

## Example App

The scaffold ships a small Trello-style board as its end-to-end smoke test.
Signed-in users can create and rearrange tasks through a React UI backed by the
generated typed client and SQL queries. A chat **Assistant** pane (built with
[Pydantic AI](https://ai.pydantic.dev/) and [OpenRouter](https://openrouter.ai/))
can inspect and mutate the signed-in user's tasks through backend tool calls
against the same user-scoped service as the REST API.

The board and assistant are disposable examples — treat them as replaceable when
building a real product on the scaffold.

## Prerequisites

Install these machine-level tools:

- [uv](https://docs.astral.sh/uv/) — Python runtime and dependency management
- [DBmate](https://github.com/amacneil/dbmate) — schema migrations
- [Gitleaks](https://github.com/gitleaks/gitleaks) — secret scanning (run via pre-commit)
- Node.js 24.16.0 (LTS; see `.node-version`) and npm — frontend tooling
- Docker with Docker Compose — local PostgreSQL 18
- Make — entry point for common tasks

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

`make dev` starts both development servers:

- API at `http://localhost:8000` (interactive docs at `http://localhost:8000/docs`)
- Frontend at `http://localhost:5173`

The single PostgreSQL container hosts `pystack_dev` and `pystack_test` on the
same port. Tests never touch the development database.

> **Note:** `make dev` requires Clerk and OpenRouter keys in `.env` or the API
> will refuse to boot. See [Authentication](#authentication) and
> [Assistant](#assistant) for the required values. Boards are per-user, so there
> is no seed data — each account starts with an empty board on first sign-in.

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
through backend tool calls. The backend assistant is built with
[Pydantic AI](https://ai.pydantic.dev/): it defines the agent, validates typed
tool arguments, streams OpenRouter model responses, and runs model-requested
task operations against the same user-scoped task service as the REST API.
`.env.example` is the versioned template with safe defaults; copy those values
into ignored `.env` for local settings and secrets.

The API validates assistant configuration during startup and refuses to boot
without an OpenRouter API key, set in `.env`:

```bash
PYSTACK_OPENROUTER_API_KEY=...
```

`OPENROUTER_API_KEY` is also accepted. `PYSTACK_ASSISTANT_MODEL` is a public
default shown in `.env.example`; `OPENROUTER_MODEL` can override it locally. The
default model is intended for local smoke testing, not production quality.

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

## Render Infrastructure

Render is the default hosted deployment target for this scaffold. The
`infra/render.yaml` Blueprint declares the production infrastructure: the FastAPI
backend service, Vite frontend static site, and Render Postgres database. The
Blueprint wires Render-managed values such as `PYSTACK_DATABASE_URL` directly
from the database, while keeping external secrets out of Git.

The core bootstrap flow is:

1. In the Render Dashboard, create a Blueprint from this repository, the `main`
   branch, and `infra/render.yaml`. Paste the production keys for the env vars
   marked `sync: false` (`PYSTACK_OPENROUTER_API_KEY`,
   `PYSTACK_CLERK_SECRET_KEY`, `VITE_CLERK_PUBLISHABLE_KEY`, and the optional
   `PYSTACK_SENTRY_DSN` / `VITE_SENTRY_DSN`).
2. Reconcile post-creation settings and run non-mutating health checks:

   ```bash
   render login
   make infra
   ```

3. Configure the GitHub Actions secrets listed in
   [docs/deploying.md](docs/deploying.md) (`RENDER_API_KEY` and the Clerk/e2e
   secrets).
4. Validate the hosted wiring:

   ```bash
   make doctor-services
   ```

For the full details — manual bootstrap walkthrough, `make infra` reconciliation
semantics, production migration automation, free vs paid tier paths, custom
domains, and production database commands — see
[docs/deploying.md](docs/deploying.md).

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

## License

[MIT](LICENSE)
