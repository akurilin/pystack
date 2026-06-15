# Pystack

Pystack is a small Trello-style board used to exercise a modern Python and
TypeScript web stack:

- FastAPI, Pydantic, DBmate, PostgreSQL, and Psycopg 3
- Vite, React 19, TypeScript, Vitest, Hey API, and TanStack Query
- uv, Ruff, mypy, Docker Compose, npm, and a root Makefile

Authentication and hosted deployment are intentionally deferred.

## Repository Layout

```text
backend/   FastAPI application and integration tests
bin/       Repository adapters for machine-level tools
db/        DBmate SQL migrations and schema snapshot
frontend/  React application, generated API client, and component tests
docker/    Local PostgreSQL initialization
```

DBmate owns schema migrations as plain SQL. The backend uses dedicated
Psycopg query modules instead of an ORM, and backend tests ask PostgreSQL to
plan every registered query against the migrated test database. DBmate
refreshes the committed `db/schema.sql` snapshot after development migrations.
Its `pg_dump` calls are transparently delegated to the PostgreSQL 18 Compose
container, ensuring the client and server versions match.

## Prerequisites

Install these machine-level tools:

- [uv](https://docs.astral.sh/uv/)
- [DBmate](https://github.com/amacneil/dbmate)
- Node.js 22.18+ and npm
- Docker with Docker Compose
- Make

Python itself does not need to be installed globally. `uv` installs a managed
Python 3.14 runtime and creates `backend/.venv`. npm dependencies stay in
`frontend/node_modules`.

## First-Time Setup

```bash
make setup
```

This installs dependencies, starts PostgreSQL, migrates the development and test
databases, seeds development data, and generates the frontend API client.
Re-running setup is safe and does not delete development data.

Start both development servers:

```bash
make dev
```

The API runs at `http://localhost:8000`; the frontend runs at
`http://localhost:5173`.

## Common Commands

Run `make help` for the complete command list. Useful targets include:

```bash
make db-up          # start the shared local PostgreSQL server
make db-migrate     # migrate both local databases
make db-status      # show DBmate migration status
make db-dump-schema # refresh the committed schema snapshot
make db-reset       # destructively reset, migrate, and seed local databases
make generate-api   # regenerate the typed frontend client
make test           # run backend and frontend tests
make check          # run the complete verification suite
```

The single PostgreSQL container hosts `pystack_dev` and `pystack_test` on the
same port. Tests never use the development database.
