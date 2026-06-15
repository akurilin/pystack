SHELL := /bin/bash
.DEFAULT_GOAL := help

COMPOSE := docker compose
BACKEND_DIR := backend
FRONTEND_DIR := frontend
DEV_DATABASE_URL := postgresql+psycopg://pystack:pystack@localhost:5432/pystack_dev
TEST_DATABASE_URL := postgresql+psycopg://pystack:pystack@localhost:5432/pystack_test

.PHONY: help check-tools setup backend-sync frontend-install db-up db-down \
	db-migrate db-migrate-dev db-migrate-test db-reset db-reset-dev \
	db-reset-test db-seed generate-api api frontend dev test test-backend \
	test-frontend lint format typecheck build check-generated check

help: ## Show available commands
	@awk 'BEGIN {FS = ":.*## "; printf "Usage: make <target>\n\nTargets:\n"} /^[a-zA-Z0-9_-]+:.*## / {printf "  %-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

check-tools: ## Verify required machine-level tools are installed
	@for tool in uv node npm docker; do \
		command -v $$tool >/dev/null || { echo "Missing required tool: $$tool"; exit 1; }; \
	done
	@node -e 'const [major, minor] = process.versions.node.split(".").map(Number); if (major < 22 || (major === 22 && minor < 18)) { console.error(`Node 22.18+ is required; found $${process.versions.node}`); process.exit(1); }'
	@$(COMPOSE) version >/dev/null

setup: check-tools backend-sync frontend-install db-up db-migrate db-seed generate-api ## Set up a new development checkout
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
	cd $(BACKEND_DIR) && PYSTACK_DATABASE_URL="$(DEV_DATABASE_URL)" uv run alembic upgrade head

db-migrate-test: db-up ## Migrate the test database
	cd $(BACKEND_DIR) && PYSTACK_DATABASE_URL="$(TEST_DATABASE_URL)" uv run alembic upgrade head

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

db-seed: db-up ## Add repeatable sample data to the development database
	cd $(BACKEND_DIR) && PYSTACK_DATABASE_URL="$(DEV_DATABASE_URL)" uv run python -m pystack_api.commands.seed

generate-api: ## Export OpenAPI and regenerate the typed frontend API client
	cd $(BACKEND_DIR) && uv run python -m pystack_api.commands.export_openapi
	cd $(FRONTEND_DIR) && npm run generate-api

check-generated: generate-api ## Confirm the committed frontend API client is current
	git diff --exit-code -- $(FRONTEND_DIR)/src/api/generated

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

lint: ## Run backend and frontend linters
	cd $(BACKEND_DIR) && uv run ruff check .
	cd $(FRONTEND_DIR) && npm run lint

format: ## Format backend and frontend source
	cd $(BACKEND_DIR) && uv run ruff format .
	cd $(FRONTEND_DIR) && npm run format

typecheck: ## Run backend and frontend type checks
	cd $(BACKEND_DIR) && uv run mypy src tests
	cd $(FRONTEND_DIR) && npm run typecheck

build: ## Build the production frontend
	cd $(FRONTEND_DIR) && npm run build

check: check-generated lint typecheck test build ## Run the complete local verification suite
