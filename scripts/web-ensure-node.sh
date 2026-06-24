# Shared helper, sourced by web-setup.sh and web-session-start.sh.
#
# Makes Node 24.16 the active `node`. The sandbox image ships an older Node (v22)
# through a version manager that sits ahead of /usr/bin on PATH, and that
# manager's location varies between images — so we search the known nvm spots
# (including the devcontainer-style shared dir) rather than assume ~/.nvm, and
# fall back to NodeSource only if no nvm is found. Prints before/after versions
# so the setup log shows exactly what happened.

ensure_node_24() {
  echo "ensure_node_24: before = $(node --version 2>/dev/null || echo none) ($(command -v node || echo 'no node on PATH'))" >&2

  local candidate nvm_sh=""
  for candidate in \
    "${NVM_DIR:-}/nvm.sh" \
    /usr/local/share/nvm/nvm.sh \
    /usr/local/nvm/nvm.sh \
    /opt/nvm/nvm.sh \
    "$HOME/.nvm/nvm.sh" \
    /root/.nvm/nvm.sh; do
    if [ -s "$candidate" ]; then nvm_sh="$candidate"; break; fi
  done

  if [ -n "$nvm_sh" ]; then
    echo "ensure_node_24: using nvm at $nvm_sh" >&2
    export NVM_DIR
    NVM_DIR="$(dirname "$nvm_sh")"
    # nvm.sh references unset vars internally, so relax nounset around it.
    set +u
    # shellcheck disable=SC1091
    . "$nvm_sh"
    set -u
    nvm install 24.16.0
    nvm alias default 24.16.0
    nvm use 24.16.0
  else
    echo "ensure_node_24: no nvm found; installing Node 24 from NodeSource." >&2
    curl -fsSL https://deb.nodesource.com/setup_24.x | bash -
    apt-get install -y nodejs
  fi

  echo "ensure_node_24: after = $(node --version 2>/dev/null || echo none) ($(command -v node || echo 'no node on PATH'))" >&2
}
