"""Lifecycle helpers for running module hooks in isolated subprocesses."""
from __future__ import annotations

import subprocess
from pathlib import Path

from sz.core import manifest, paths, runtime


def run_hook(
    root: Path,
    mod_id: str,
    hook_name: str,
    env_extra: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str] | None:
    module_dir = paths.module_dir(root, mod_id)
    data = manifest.load(module_dir / "module.yaml")
    relative_path = (data.get("hooks") or {}).get(hook_name)
    if not relative_path:
        return None
    env = runtime.module_environment(root, mod_id, module_dir)
    if env_extra:
        env.update(env_extra)
    command = ["/bin/bash", str((module_dir / relative_path).resolve())]
    return subprocess.run(
        command,
        cwd=module_dir,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
