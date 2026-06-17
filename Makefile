SHELL := /bin/bash
.DEFAULT_GOAL := help

COMPOSE := docker compose
DBMATE := PATH="$(CURDIR)/bin:$$PATH" dbmate
BACKEND_DIR := backend
FRONTEND_DIR := frontend
DEV_DATABASE_URL := postgresql://pystack:pystack@localhost:5432/pystack_dev
TEST_DATABASE_URL := postgresql://pystack:pystack@localhost:5432/pystack_test
DBMATE_DEV_DATABASE_URL := postgres://pystack:pystack@localhost:5432/pystack_dev?sslmode=disable
DBMATE_TEST_DATABASE_URL := postgres://pystack:pystack@localhost:5432/pystack_test?sslmode=disable
PROD_DATABASE_URL_CMD := uv run --project $(BACKEND_DIR) python scripts/render_database_url.py

.PHONY: help check-tools setup backend-sync frontend-install db-up db-down \
	db-migrate db-migrate-dev db-migrate-test db-reset db-reset-dev \
	db-reset-test db-status db-status-prod db-migrate-prod psql-prod db-dump-schema db-seed \
	infra \
	generate-api api frontend dev \
	test test-backend test-frontend test-e2e lint format check-format typecheck build \
	check-generated check-db-schema check-secrets pre-commit-install pre-commit check

help: ## Show available commands
	@awk 'BEGIN {FS = ":.*## "; printf "Usage: make <target>\n\nTargets:\n"} /^[a-zA-Z0-9_-]+:.*## / {printf "  %-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

check-tools: ## Verify required machine-level tools are installed
	@for tool in uv node npm docker dbmate gitleaks; do \
		command -v $$tool >/dev/null || { echo "Missing required tool: $$tool"; exit 1; }; \
	done
	@node -e 'const [major, minor] = process.versions.node.split(".").map(Number); if (major < 24 || (major === 24 && minor < 16)) { console.error(`Node 24.16+ is required; found $${process.versions.node}`); process.exit(1); }'
	@$(COMPOSE) version >/dev/null

setup: check-tools backend-sync frontend-install pre-commit-install db-up db-migrate db-seed generate-api ## Set up a new development checkout
	@echo "Setup complete. Run 'make dev' to start the application."

backend-sync: ## Install the managed Python runtime and backend dependencies
	uv python install 3.14
	cd $(BACKEND_DIR) && uv sync --all-groups

frontend-install: ## Install locked frontend dependencies
	cd $(FRONTEND_DIR) && npm ci

db-up: ## Start PostgreSQL and wait until it is healthy
	$(COMPOSE) up -d --wait db

db-down: ## Stop local services without deleting data
	$(COMPOSE) down

db-migrate: db-migrate-dev db-migrate-test ## Migrate development and test databases

db-migrate-dev: db-up ## Migrate the development database
	$(DBMATE) --url "$(DBMATE_DEV_DATABASE_URL)" --wait up --strict

db-migrate-test: db-up ## Migrate the test database
	$(DBMATE) --url "$(DBMATE_TEST_DATABASE_URL)" --wait --no-dump-schema up --strict

db-reset: db-reset-dev db-reset-test ## Destructively reset, migrate, and seed local databases

db-reset-dev: db-up ## Destructively reset, migrate, and seed the development database
	$(COMPOSE) exec -T db psql -U pystack -d postgres -v ON_ERROR_STOP=1 \
		-c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'pystack_dev' AND pid <> pg_backend_pid();" \
		-c "DROP DATABASE IF EXISTS pystack_dev;" \
		-c "CREATE DATABASE pystack_dev OWNER pystack;"
	$(MAKE) db-migrate-dev
	$(MAKE) db-seed

db-reset-test: db-up ## Destructively reset and migrate the test database
	$(COMPOSE) exec -T db psql -U pystack -d postgres -v ON_ERROR_STOP=1 \
		-c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'pystack_test' AND pid <> pg_backend_pid();" \
		-c "DROP DATABASE IF EXISTS pystack_test;" \
		-c "CREATE DATABASE pystack_test OWNER pystack;"
	$(MAKE) db-migrate-test

db-status: db-up ## Show migration status for development and test databases
	@echo "Development database:"
	@$(DBMATE) --url "$(DBMATE_DEV_DATABASE_URL)" status
	@echo
	@echo "Test database:"
	@$(DBMATE) --url "$(DBMATE_TEST_DATABASE_URL)" --no-dump-schema status

# Production migrations resolve the Render Postgres URL at runtime, so generated
# database credentials do not need to be copied into a local env file. There is
# intentionally no prod reset/drop target: the destructive db-reset-* flow can
# never reach prod. --no-dump-schema keeps a prod run from rewriting schema.sql.
db-status-prod: ## Show migration status for the production database
	@DATABASE_URL="$$($(PROD_DATABASE_URL_CMD))" && \
		export DATABASE_URL && \
		$(DBMATE) --env DATABASE_URL --no-dump-schema status

db-migrate-prod: ## Apply pending migrations to the production database
	@DATABASE_URL="$$($(PROD_DATABASE_URL_CMD))" && \
		export DATABASE_URL && \
		$(DBMATE) --env DATABASE_URL --wait --no-dump-schema up --strict

# Connects out to prod through the dockerized psql client (bin/psql), so db-up
# is required to have the db container running as the client's host.
psql-prod: db-up ## Open an interactive psql session on the production database
	@DATABASE_URL="$$($(PROD_DATABASE_URL_CMD))" && \
		PATH="$(CURDIR)/bin:$$PATH" psql "$$DATABASE_URL"

db-dump-schema: db-up ## Refresh db/schema.sql from the development database
	$(DBMATE) --url "$(DBMATE_DEV_DATABASE_URL)" dump

db-seed: db-up ## Add repeatable sample data to the development database
	cd $(BACKEND_DIR) && PYSTACK_DATABASE_URL="$(DEV_DATABASE_URL)" uv run python -m pystack_api.commands.seed

infra: ## Validate Render Blueprint, sync secret env vars, deploy changes, and health-check Render
	uv run --project $(BACKEND_DIR) python scripts/render_infra.py

generate-api: ## Export OpenAPI and regenerate the typed frontend API client
	cd $(BACKEND_DIR) && uv run python -m pystack_api.commands.export_openapi
	cd $(FRONTEND_DIR) && npm run generate-api

check-generated: generate-api ## Confirm the committed frontend API client is current
	git diff --exit-code -- $(FRONTEND_DIR)/src/api/generated

check-db-schema: db-migrate-dev db-dump-schema ## Confirm the committed database schema snapshot is current
	git diff --exit-code -- db/schema.sql

api: ## Run the FastAPI development server
	cd $(BACKEND_DIR) && uv run uvicorn pystack_api.main:app --reload

frontend: ## Run the Vite development server
	cd $(FRONTEND_DIR) && npm run dev

dev: ## Run backend and frontend development servers
	$(MAKE) -j2 api frontend

test: test-backend test-frontend ## Run all tests

test-backend: db-reset-test ## Run backend integration tests
	cd $(BACKEND_DIR) && PYSTACK_TEST_DATABASE_URL="$(TEST_DATABASE_URL)" uv run pytest

test-frontend: ## Run frontend tests
	cd $(FRONTEND_DIR) && npm test -- --run

test-e2e: db-migrate-dev ## Run Playwright end-to-end tests against the dev stack
	cd $(FRONTEND_DIR) && npm run e2e

lint: ## Run backend and frontend linters
	cd $(BACKEND_DIR) && uv run ruff check .
	cd $(FRONTEND_DIR) && npm run lint

format: ## Format backend and frontend source
	cd $(BACKEND_DIR) && uv run ruff format .
	cd $(FRONTEND_DIR) && npm run format

check-format: ## Confirm backend and frontend source formatting
	cd $(BACKEND_DIR) && uv run ruff format --check .
	cd $(FRONTEND_DIR) && npm run format:check

typecheck: ## Run backend and frontend type checks
	cd $(BACKEND_DIR) && uv run mypy src tests
	cd $(FRONTEND_DIR) && npm run typecheck

build: ## Build the production frontend
	cd $(FRONTEND_DIR) && npm run build

check-secrets: ## Scan the complete Git history for secrets
	gitleaks git --redact --verbose .

pre-commit-install: backend-sync ## Install the repository Git pre-commit hook
	uv run --project $(BACKEND_DIR) pre-commit install

pre-commit: ## Run every pre-commit hook against all tracked files
	uv run --project $(BACKEND_DIR) pre-commit run --all-files

check: check-generated check-db-schema check-format lint typecheck test build check-secrets ## Run the complete local verification suite
