#!/usr/bin/env bash
#
# One-time provisioning for the Claude Code on the web sandbox.
#
# Paste `bash scripts/web-setup.sh` into the environment's "Setup script" field
# (see docs/claude-on-web.md). It runs once as root at environment creation and
# the result is cached, so it must finish inside the ~5-minute cache budget.
#
# Design notes for that budget and for the sandbox's quirks:
#   - Node comes from the image's nvm, whose default (v22) shadows any
#     apt-installed Node on PATH; we install and pin 24.16 through nvm so npm
#     and our >=24.16 engine check both see the right version.
#   - CI compiles dbmate and gitleaks with `go install`; here we download the
#     prebuilt release binaries instead (seconds vs. minutes of compilation).
#   - The Postgres image is NOT pulled here: the Docker daemon is not running at
#     environment-build time. SessionStart starts Docker and pulls/migrates the
#     database per session instead.
#   - Independent, network-bound installs run in parallel and we wait on each
#     PID so a failure still aborts the build (a non-zero setup script fails the
#     environment, which is what we want — half-provisioned is worse than none).
#
# Playwright/e2e is intentionally NOT installed: `make check` never invokes it,
# and the browser e2e suite stays in CI. See docs/claude-on-web.md.

set -euo pipefail

cd "$(dirname "$0")/.."

# --- Node 24 via the image's nvm (default is 22) -----------------------------
# nvm is a shell function, so source it first. Disable nounset around the source
# because nvm.sh references unset variables internally.
export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
set +u
# shellcheck disable=SC1091
. "$NVM_DIR/nvm.sh"
set -u
nvm install 24.16.0
nvm alias default 24.16.0
nvm use 24.16.0

# --- dbmate + gitleaks as prebuilt binaries ----------------------------------
curl -fsSL -o /usr/local/bin/dbmate \
  https://github.com/amacneil/dbmate/releases/download/v2.30.0/dbmate-linux-amd64
chmod +x /usr/local/bin/dbmate

# Fall back to compiling gitleaks if the release asset name ever changes; Go is
# preinstalled, so the fallback is cheap insurance against a broken cached env.
if ! curl -fsSL \
  https://github.com/gitleaks/gitleaks/releases/download/v8.30.0/gitleaks_8.30.0_linux_x64.tar.gz \
  | tar -xz -C /usr/local/bin gitleaks; then
  echo "Prebuilt gitleaks download failed; compiling via go install." >&2
  go install github.com/zricethezav/gitleaks/v8@v8.30.0
  install -m 0755 "$(go env GOPATH)/bin/gitleaks" /usr/local/bin/gitleaks
fi

# --- Project dependencies, in parallel ---------------------------------------
make backend-sync & pid_backend=$!
make frontend-install & pid_frontend=$!

wait "$pid_backend"
wait "$pid_frontend"

echo "web-setup complete."
