#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="${SZ_REPO_ROOT:-$(pwd)}"
HOOK="$REPO_ROOT/.git/hooks/post-commit"
MARKER_BEGIN="# >>> sz-generic >>>"
MARKER_END="# <<< sz-generic <<<"

if [ -d "$REPO_ROOT/.git" ]; then
  mkdir -p "$REPO_ROOT/.git/hooks"
  if [ -f "$HOOK" ] && grep -q "$MARKER_BEGIN" "$HOOK"; then
    :
  else
    {
      [ -f "$HOOK" ] && cat "$HOOK"
      echo ""
      echo "$MARKER_BEGIN"
      echo "sz bus emit host.commit.made \"\$(jq -nc --arg sha \"\$(git rev-parse HEAD)\" '{sha:\$sha}')\"  || true"
      echo "$MARKER_END"
    } > "$HOOK.tmp"
    mv "$HOOK.tmp" "$HOOK"
    chmod +x "$HOOK"
  fi
fi

CRON_LINE="*/5 * * * *  cd '$REPO_ROOT' && sz tick --reason cron >> '$REPO_ROOT/.sz/heartbeat.log' 2>&1"
TMP_CRON="$(mktemp)"
if [ -n "${SZ_CRONTAB_FILE:-}" ]; then
  touch "$SZ_CRONTAB_FILE"
  cp "$SZ_CRONTAB_FILE" "$TMP_CRON"
  if grep -Fq "sz tick --reason cron" "$TMP_CRON"; then
    :
  else
    echo "$CRON_LINE" >> "$TMP_CRON"
    mv "$TMP_CRON" "$SZ_CRONTAB_FILE"
    TMP_CRON=""
  fi
else
  crontab -l 2>/dev/null > "$TMP_CRON" || : > "$TMP_CRON"
  if grep -Fq "sz tick --reason cron" "$TMP_CRON"; then
    :
  else
    echo "$CRON_LINE" >> "$TMP_CRON"
    crontab "$TMP_CRON" 2>/dev/null || echo "warning: crontab install failed; sz tick must be invoked manually."
  fi
fi
rm -f "$TMP_CRON"
echo "generic adapter installed (Install mode)"
