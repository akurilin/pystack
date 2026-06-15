# Pystack

Pystack is a small Trello-style board used to exercise a modern Python and
TypeScript web stack:

- FastAPI, Pydantic, SQLAlchemy 2.0, DBmate, PostgreSQL, and psycopg 3
- Vite, React 19, TypeScript, Vitest, Hey API, and TanStack Query
- uv, Ruff, mypy, Docker Compose, npm, and a root Makefile

Authentication and hosted deployment are intentionally deferred.

## Repository Layout

```text
backend/   FastAPI application and integration tests
db/        DBmate SQL migrations
frontend/  React application, generated API client, and component tests
docker/    Local PostgreSQL initialization
```

DBmate owns schema migrations as plain SQL independently from the backend's
SQLAlchemy models. Migrations are the schema source of truth; schema snapshots
are disabled so local development does not require a matching `pg_dump` binary.

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
make db-reset       # destructively reset, migrate, and seed local databases
make generate-api   # regenerate the typed frontend client
make test           # run backend and frontend tests
make check          # run the complete verification suite
```

The single PostgreSQL container hosts `pystack_dev` and `pystack_test` on the
same port. Tests never use the development database.
