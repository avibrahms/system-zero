from __future__ import annotations

import os
import site
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SZ_COMMAND = [sys.executable, "-m", "sz.commands.cli"]


def with_repo_pythonpath(env: dict[str, str] | None = None) -> dict[str, str]:
    result = dict(os.environ if env is None else env)
    current = result.get("PYTHONPATH")
    result["PYTHONPATH"] = f"{REPO_ROOT}:{current}" if current else str(REPO_ROOT)
    result.setdefault("PYTHONUSERBASE", site.getuserbase())
    return result


def install_sz_shim(shim_dir: Path, env: dict[str, str]) -> None:
    shim_dir.mkdir(parents=True, exist_ok=True)
    user_base = env.get("PYTHONUSERBASE") or site.getuserbase()
    shim = shim_dir / "sz"
    shim.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        f"export PYTHONPATH={str(REPO_ROOT)!r}:\"${{PYTHONPATH:-}}\"\n"
        f"export PYTHONUSERBASE={user_base!r}\n"
        f"exec {sys.executable!r} -m sz.commands.cli \"$@\"\n"
    )
    shim.chmod(0o755)
    env["PATH"] = f"{shim_dir}:{env.get('PATH', '')}"
    env["PYTHONPATH"] = f"{REPO_ROOT}:{env.get('PYTHONPATH', '')}" if env.get("PYTHONPATH") else str(REPO_ROOT)
    env["PYTHONUSERBASE"] = user_base
