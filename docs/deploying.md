# Render Deployment

This document covers the hosted deployment details that were trimmed from the
main README. For the core bootstrap flow, see the README's
[Render Infrastructure](../README.md#render-infrastructure) section.

## Manual bootstrap

There is one manual bootstrap step because Render's CLI validates Blueprints but
does not create the initial Blueprint connection:

1. In the Render Dashboard, create a Blueprint from this repository, the `main`
   branch, and `infra/render.yaml`. Render will ask for the env vars marked
   `sync: false` — `PYSTACK_OPENROUTER_API_KEY`, `PYSTACK_CLERK_SECRET_KEY`, the
   frontend's `VITE_CLERK_PUBLISHABLE_KEY`, and the optional Sentry DSNs
   (`PYSTACK_SENTRY_DSN`, `VITE_SENTRY_DSN`). Paste the production OpenRouter key
   and your Clerk production instance keys there; leave the Sentry DSNs blank to
   keep error monitoring off. Then wait for provisioning to finish.
2. Reconcile post-creation settings and run non-mutating health checks:

   ```bash
   render login
   make infra
   ```

3. Configure the repository secrets GitHub Actions needs:

   - `PYSTACK_CLERK_SECRET_KEY`, `VITE_CLERK_PUBLISHABLE_KEY`,
     `CLERK_TEST_USER_USERNAME`, and `CLERK_TEST_USER_PASSWORD` — used by CI and
     e2e tests.

   `RENDER_API_KEY` is optional for local `make infra` and production DB
   commands. `DBMATE_PROD_DATABASE_URL` can bypass Render discovery.

4. Validate the hosted wiring:

   ```bash
   make doctor-services
   ```

## `make infra` reconciliation

`make infra` is the repeatable reconciliation step. It validates the Blueprint,
discovers the deployed Render service URLs, syncs derived runtime values such as
`PYSTACK_CORS_ORIGINS`, `PYSTACK_CLERK_AUTHORIZED_PARTIES`, and `VITE_API_URL`,
deploys services whose env vars changed, and runs non-mutating health checks.
Re-running it is safe: unchanged env vars are left alone and no deploy is
triggered unless a service configuration value changes. It intentionally does
not set `PYSTACK_OPENROUTER_API_KEY`, so a local personal key cannot overwrite
the production key entered in Render.

## Production migrations

The Pystack Render services and database were removed in October 2026, so CI
does not run production migrations. Before you create a new deployment, add a
migration step that runs before each deploy. `make db-migrate-prod` remains
available for manual use after a production database exists.

The intended paid Render setup is simpler: move DBmate into the backend service's
Render `preDeployCommand`, keep Render's auto-deploy trigger as the deployment
source of truth, and let Render block the deploy if migrations fail before the
new service starts. Use that path after upgrading the backend service and
Postgres database to plans that support pre-deploy commands and durable
production backups.

## Custom domains

If you serve the frontend from a custom domain, set `FRONTEND_CUSTOM_ORIGIN` in
`scripts/render_infra.py` so `make infra` allows it for both CORS and Clerk
authorized parties, and point that domain at the Render static site. A Clerk
**production** instance additionally serves its Frontend API from a custom
subdomain (e.g. `clerk.yourdomain.com`); add the CNAME records Clerk lists under
its dashboard's Domains section, or sign-in fails to load in production because
the Clerk endpoints do not resolve.

## Production database commands

Production database commands use Render discovery. `make db-status-prod`,
`make db-migrate-prod`, and `make psql-prod` resolve the external Render Postgres
URL at runtime from the Render API, then pass it to DBmate or psql without
writing it to a local file. Set `DBMATE_PROD_DATABASE_URL` in the shell only if
you need to override Render discovery.

The Render services set `rootDir` to `backend` and `frontend`. A database-only
commit under `db/` does not force an application deploy.
