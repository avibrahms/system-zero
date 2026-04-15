#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="${SZ_REPO_ROOT:-$(pwd)}"
found=""
if command -v grep >/dev/null && grep -lr --include='*.yaml' --include='*.yml' -E '^\s*on_tick:\s*' "$REPO_ROOT" 2>/dev/null | head -n1 | grep -q .; then
  found="yaml-on_tick"
fi
if [ -z "$found" ] && crontab -l 2>/dev/null | grep -Fq "$REPO_ROOT"; then
  found="cron-in-this-repo"
fi
if [ -z "$found" ]; then
  if ls "$HOME/Library/LaunchAgents" 2>/dev/null | xargs -I{} grep -l "$REPO_ROOT" "$HOME/Library/LaunchAgents/{}" 2>/dev/null | head -n1 | grep -q .; then
    found="launchd-plist"
  fi
fi
if [ -z "$found" ] && [ -d "$HOME/.config/systemd/user" ]; then
  if grep -lr "$REPO_ROOT" "$HOME/.config/systemd/user" 2>/dev/null | head -n1 | grep -q .; then
    found="systemd-unit"
  fi
fi
[ -n "$found" ] && echo "unknown" || exit 1
