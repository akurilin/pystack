#!/usr/bin/env bash
#
# Per-session bootstrap for the Claude Code on the web sandbox, wired in via the
# SessionStart hook in .claude/settings.json.
#
# Handles the things that do NOT survive between cloud sessions: the Postgres
# container is recreated empty (no volume persistence), and dependency layers
# may not carry over from the cached setup script. It is a no-op locally, where
# the developer manages their own database and dependencies.

set -euo pipefail

# Cloud only. CLAUDE_CODE_REMOTE is "true" inside the web sandbox, unset locally.
[ "${CLAUDE_CODE_REMOTE:-}" = "true" ] || exit 0

cd "$(dirname "$0")/.."

# The Docker daemon is not always running at session start.
service docker start 2>/dev/null || true

# Self-heal dependencies if the setup-script cache layer didn't reach this
# session. `backend-sync` is fast and idempotent (and re-fetches the managed
# Python for this session's user if needed); only guard the expensive `npm ci`.
make backend-sync
[ -d frontend/node_modules ] || make frontend-install

# Bring up Postgres and migrate dev + test from scratch — the container is fresh
# every session, so its schema has to be rebuilt each time.
make db-up
make db-migrate

echo "web-session-start complete."
