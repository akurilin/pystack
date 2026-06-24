#!/usr/bin/env bash
#
# Per-session bootstrap for the Claude Code on the web sandbox, wired in via the
# SessionStart hook in .claude/settings.json.
#
# Handles the things that do NOT survive between cloud sessions: Node defaults
# back to the image's v22, the Docker daemon may be stopped, the Postgres
# container is recreated empty (no volume persistence), and dependency layers
# may not carry over from the cached setup script. It is a no-op locally, where
# the developer manages their own toolchain and database.

set -euo pipefail

# Cloud only. CLAUDE_CODE_REMOTE is "true" inside the web sandbox, unset locally.
[ "${CLAUDE_CODE_REMOTE:-}" = "true" ] || exit 0

cd "$(dirname "$0")/.."

# Node 24 for this session (the image defaults to 22, which trips our >=24.16
# engine check). Setting nvm's default alias makes every shell the agent later
# spawns pick up 24.16 too.
export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
if [ -s "$NVM_DIR/nvm.sh" ]; then
  set +u
  # shellcheck disable=SC1091
  . "$NVM_DIR/nvm.sh"
  set -u
  nvm install 24.16.0
  nvm alias default 24.16.0
  nvm use 24.16.0
fi

# The Docker daemon is not always running at session start.
service docker start 2>/dev/null || sudo service docker start 2>/dev/null || true

# Self-heal dependencies if the setup-script cache layer didn't reach this
# session (e.g. a different session user). `backend-sync` is fast and idempotent
# and re-fetches the managed Python if needed; only guard the expensive `npm ci`.
make backend-sync
[ -d frontend/node_modules ] || make frontend-install

# Bring up Postgres and migrate dev + test from scratch — the container is fresh
# every session, so its schema has to be rebuilt each time. This is also where
# the Postgres image is first pulled, since Docker is unavailable during setup.
make db-up
make db-migrate

echo "web-session-start complete."
