#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="${SZ_REPO_ROOT:-$(pwd)}"
HOOK="$REPO_ROOT/.git/hooks/post-commit"
MARKER_BEGIN="# >>> sz-generic >>>"
MARKER_END="# <<< sz-generic <<<"

if [ -f "$HOOK" ]; then
  python3 - "$HOOK" "$MARKER_BEGIN" "$MARKER_END" <<'PY'
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
begin = sys.argv[2]
end = sys.argv[3]
lines = path.read_text().splitlines()
out = []
skipping = False
for line in lines:
    if line == begin:
        skipping = True
        continue
    if line == end:
        skipping = False
        continue
    if not skipping:
        out.append(line)
path.write_text("\n".join(out).rstrip() + ("\n" if out else ""))
PY
fi

TMP_CRON="$(mktemp)"
if [ -n "${SZ_CRONTAB_FILE:-}" ]; then
  touch "$SZ_CRONTAB_FILE"
  grep -Fv "$REPO_ROOT/.sz/heartbeat.log" "$SZ_CRONTAB_FILE" | grep -Fv "cd '$REPO_ROOT' && sz tick --reason cron" > "$TMP_CRON" || :
  mv "$TMP_CRON" "$SZ_CRONTAB_FILE"
  TMP_CRON=""
else
  crontab -l 2>/dev/null > "$TMP_CRON" || : > "$TMP_CRON"
  FILTERED="$(mktemp)"
  grep -Fv "$REPO_ROOT/.sz/heartbeat.log" "$TMP_CRON" | grep -Fv "cd '$REPO_ROOT' && sz tick --reason cron" > "$FILTERED" || :
  crontab "$FILTERED" 2>/dev/null || :
  rm -f "$FILTERED"
fi
rm -f "$TMP_CRON"
echo "generic adapter uninstalled"
