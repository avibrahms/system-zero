from __future__ import annotations

import stat

from sz.interfaces import lifecycle

from tests.interfaces.helpers import make_runtime_root


def test_lifecycle_run_hook_executes_with_runtime_env(tmp_path) -> None:
    root = make_runtime_root(tmp_path)
    module_dir = root / ".sz" / "hello-module"
    module_dir.mkdir()
    hook_path = module_dir / "install.sh"
    hook_path.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "printf '%s\\n' \"$SZ_MODULE_ID\" > \"$SZ_REPO_ROOT/hook-output.txt\"\n",
        encoding="utf-8",
    )
    hook_path.chmod(hook_path.stat().st_mode | stat.S_IEXEC)
    (module_dir / "module.yaml").write_text(
        "id: hello-module\n"
        "version: 0.1.0\n"
        "category: testing\n"
        "description: hook test\n"
        "entry:\n"
        "  type: bash\n"
        "  command: install.sh\n"
        "triggers:\n"
        "  - on: tick\n"
        "hooks:\n"
        "  install: install.sh\n",
        encoding="utf-8",
    )

    result = lifecycle.run_hook(root, "hello-module", "install")

    assert result is not None
    assert result.returncode == 0
    assert (root / "hook-output.txt").read_text(encoding="utf-8").strip() == "hello-module"
