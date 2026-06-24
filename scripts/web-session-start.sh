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

# Node 24 for this session (the image default is older, which trips our >=24.16
# engine check). ensure_node_24 sets nvm's default alias, so every shell the
# agent later spawns picks up 24.16 too.
# shellcheck source=scripts/web-ensure-node.sh
. scripts/web-ensure-node.sh
ensure_node_24

# The Docker daemon is not always running at session start, and this image ships
# no working `service docker` unit — so try the service manager, then fall back
# to launching dockerd directly, and poll until the daemon actually accepts
# connections. Everything below (db-up, db-migrate) needs a live daemon; racing
# ahead while it is still down was silently aborting the rest of this hook under
# `set -e`, which is why sessions came up with Docker stopped and DBs unmigrated.
ensure_docker() {
  docker info >/dev/null 2>&1 && return 0

  service docker start 2>/dev/null || sudo service docker start 2>/dev/null || true
  local i
  for i in $(seq 1 5); do docker info >/dev/null 2>&1 && return 0; sleep 1; done

  # No working service unit: start the daemon directly and wait for it.
  sudo dockerd >/tmp/dockerd.log 2>&1 &
  for i in $(seq 1 20); do docker info >/dev/null 2>&1 && return 0; sleep 1; done

  echo "ensure_docker: Docker daemon did not become ready; see /tmp/dockerd.log" >&2
  return 1
}
ensure_docker

# Keep uv current before it provisions the pinned Python. An image-bundled uv can
# lag behind the .python-version release and otherwise resolve a prerelease (see
# web-setup.sh). Non-fatal here; backend-sync fails loudly if the pin is unmet.
uv self update || true

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
