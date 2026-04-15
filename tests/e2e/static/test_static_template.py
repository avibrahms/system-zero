import json
import os
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from tests.e2e.local_sz import SZ_COMMAND as SZ, install_sz_shim, with_repo_pythonpath


HERE = Path(__file__).resolve().parents[3]


def test_static_weatherbot_becomes_alive(tmp_path):
    repo = tmp_path / "repo"
    shutil.copytree(HERE / "tests" / "templates" / "static-weatherbot", repo)
    for stale in (repo / "posts").glob("*.txt"):
        stale.unlink()
    env = with_repo_pythonpath()
    install_sz_shim(tmp_path / "bin", env)
    env["SZ_LLM_PROVIDER"] = "mock"
    env["SZ_FORCE_GENESIS_PROFILE"] = json.dumps(
        {
            "purpose": "post weather to a file daily",
            "language": "python",
            "frameworks": ["weatherbot"],
            "existing_heartbeat": "none",
            "goals": ["produce posts/<date>.txt once per day"],
            "recommended_modules": [
                {"id": "heartbeat", "reason": "required for static repos"},
                {"id": "immune", "reason": "detect leaked secrets"},
                {"id": "subconscious", "reason": "aggregate health"},
                {"id": "goal-runner", "reason": "actually run the project"},
                {"id": "prediction", "reason": "predict next likely event from history"},
            ],
            "risk_flags": [],
        }
    )
    cwd = Path.cwd()
    os.chdir(repo)
    try:
        subprocess.run(["git", "init", "-q"], check=True, env=env)
        subprocess.run(["git", "config", "user.email", "t@t"], check=True, env=env)
        subprocess.run(["git", "config", "user.name", "t"], check=True, env=env)
        subprocess.run(["git", "config", "commit.gpgsign", "false"], check=True, env=env)
        subprocess.run(["git", "add", "-A"], check=True, env=env)
        subprocess.run(["git", "commit", "-qm", "init"], check=True, env=env)

        subprocess.run([*SZ, "init", "--host", "generic", "--yes"], env=env, check=True)

        # Profile written
        profile = json.loads((repo / ".sz" / "repo-profile.json").read_text())
        assert "weather" in profile["purpose"].lower()

        # Modules installed
        reg = json.loads((repo / ".sz" / "registry.json").read_text())
        assert {"heartbeat", "immune", "subconscious", "goal-runner", "prediction"}.issubset(set(reg["modules"]))

        # Heartbeat -> pulses -> goal-runner -> today's file
        subprocess.run([*SZ, "stop"], check=False, env=env)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        (repo / "posts" / f"{today}.txt").unlink(missing_ok=True)
        subprocess.run([*SZ, "start", "--interval", "5"], check=True, env=env)
        time.sleep(30)
        subprocess.run([*SZ, "stop"], check=True, env=env)

        bus = (repo / ".sz" / "bus.jsonl").read_text().splitlines()
        types = [json.loads(l)["type"] for l in bus]
        assert types.count("pulse.tick") >= 3
        assert types.count("goal.executed") >= 1
        assert (repo / "posts" / f"{today}.txt").exists()
    finally:
        os.chdir(cwd)
