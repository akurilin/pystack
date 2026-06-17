# Pystack

Pystack is an opinionated scaffold for a modern Python and TypeScript web
application. It ships a FastAPI backend, a React frontend with a generated,
fully typed API client, a PostgreSQL database with plain-SQL migrations, and a
single Makefile that wires everything together for local development.

It is meant to be cloned and built on. The included Trello-style board is **not**
the point of the project — it is just an example of a small end-to-end app built
on the scaffold, a smoke test that exercises the full request path from a React
component through a typed client to a SQL-backed endpoint. Treat it as
disposable and replace it with your own application. Authentication and hosted
deployment are intentionally left out.

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
- Node.js 22.18+ and npm
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
migrates the development and test databases, seeds development data, generates
the frontend API client, and installs the repository pre-commit hook. Re-running
it is safe and does not delete development data.

`make dev` starts both development servers:

- API at `http://localhost:8000` (interactive docs at `http://localhost:8000/docs`)
- Frontend at `http://localhost:5173`

The single PostgreSQL container hosts `pystack_dev` and `pystack_test` on the
same port. Tests never touch the development database.

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
make db-seed        # add repeatable sample data to the dev database
make db-reset       # destructively reset, migrate, and seed local databases
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
