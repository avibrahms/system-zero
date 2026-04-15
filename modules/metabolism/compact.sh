#!/usr/bin/env bash
set -euo pipefail
archive_dir="$SZ_REPO_ROOT/.sz/archive"
mkdir -p "$archive_dir"
decision="$(python3 - <<'PY'
from __future__ import annotations
import os
from pathlib import Path
from time import time

path = Path(os.environ["SZ_BUS_PATH"])
days = float(os.environ.get("SZ_SETPOINT_rotate_after_days", "14"))
mb = float(os.environ.get("SZ_SETPOINT_rotate_after_mb", "50"))
if not path.exists():
    print("no")
else:
    stat = path.stat()
    too_old = (time() - stat.st_mtime) >= days * 86400
    too_large = stat.st_size >= mb * 1024 * 1024
    print("yes" if too_old or too_large else "no")
PY
)"
if [ "$decision" = "yes" ]; then
  stamp="$(date -u +%Y%m%dT%H%M%SZ)"
  archive="$archive_dir/bus-$stamp.jsonl"
  cp "$SZ_BUS_PATH" "$archive"
  mv "$SZ_BUS_PATH" "$archive.tmp"
  : > "$SZ_BUS_PATH"
  rm -f "$archive.tmp"
  sz bus emit bus.rotated "$(jq -nc --arg archive "$archive" '{archive:$archive}')" --module metabolism
fi
sz memory set metabolism.last "$(date -u +%FT%TZ)"
