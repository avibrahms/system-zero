#!/usr/bin/env bash
set -euo pipefail

install_local_sz_shim() {
  local repo_root="$1"
  local shim_dir="$2"
  local user_base="${PYTHONUSERBASE:-}"
  if [ -z "$user_base" ]; then
    user_base="$(python3 -m site --user-base 2>/dev/null || true)"
  fi
  mkdir -p "$shim_dir"
  cat > "$shim_dir/sz" <<SH
#!/usr/bin/env bash
set -euo pipefail
export PYTHONPATH="$repo_root:\${PYTHONPATH:-}"
export PYTHONUSERBASE="$user_base"
exec python3 -m sz.commands.cli "\$@"
SH
  chmod +x "$shim_dir/sz"
}
