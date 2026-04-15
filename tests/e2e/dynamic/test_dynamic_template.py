import os, json, shutil, subprocess, time
from pathlib import Path
import pytest

HERE = Path(__file__).resolve().parents[3]


@pytest.mark.skipif(shutil.which("sz") is None, reason="s0 missing")
def test_dynamic_template_adopts(tmp_path):
    previous_pythonpath = os.environ.get("PYTHONPATH", "")
    os.environ["PYTHONPATH"] = f"{HERE}:{previous_pythonpath}" if previous_pythonpath else str(HERE)
    repo = tmp_path / "repo"
    shutil.copytree(HERE / "tests" / "templates" / "mini-hermes", repo)
    cwd = Path.cwd()
    os.chdir(repo)
    try:
        subprocess.run(["git", "init", "-q"], check=True)
        subprocess.run(["git", "config", "user.email", "t@t"], check=True)
        subprocess.run(["git", "config", "user.name",  "t"], check=True)
        subprocess.run(["git", "add", "-A"], check=True)
        subprocess.run(["git", "commit", "-qm", "init"], check=True)

        env = os.environ.copy()
        env["PYTHONPATH"] = f"{HERE}:{env.get('PYTHONPATH', '')}" if env.get("PYTHONPATH") else str(HERE)
        env["SZ_LLM_PROVIDER"] = "mock"
        env["SZ_FORCE_GENESIS_PROFILE"] = json.dumps({
            "purpose":"keep pulse.log growing forever",
            "language":"shell",
            "frameworks":["mini-hermes"],
            "existing_heartbeat":"hermes",
            "goals":["append a heartbeat line to pulse.log every interval"],
            "recommended_modules":[
                {"id":"immune","reason":"detect anomalies"},
                {"id":"subconscious","reason":"aggregate health"},
                {"id":"prediction","reason":"predict"},
                {"id":"goal-runner","reason":"verify daemon output"}
            ],
            "risk_flags":[]
        })
        subprocess.run(["sz", "init", "--yes"], env=env, check=True)

        cfg = (repo / ".sz.yaml").read_text()
        assert "host: hermes" in cfg
        assert "host_mode: adopt" in cfg
        assert not (repo / ".sz" / "heartbeat.pid").exists()

        reg = json.loads((repo / ".sz" / "registry.json").read_text())
        assert "heartbeat" not in reg["modules"]
        assert {"immune","subconscious","prediction","goal-runner"}.issubset(set(reg["modules"]))

        # Verify the hermes config patch.
        import yaml
        h = yaml.safe_load((repo / ".hermes" / "config.yaml").read_text())
        assert "sz tick --reason hermes" in (h.get("hooks", {}).get("on_tick") or [])

        # Run the existing daemon briefly; collect bus events.
        proc = subprocess.Popen(["bash", "bin/mini-hermes.sh"])
        time.sleep(20)
        proc.terminate(); proc.wait(timeout=5)

        with open(repo / ".sz" / "bus.jsonl") as f:
            types = [json.loads(line)["type"] for line in f]
        assert types.count("tick") >= 2
        assert types.count("health.snapshot") >= 1
        # The daemon's own goal continued.
        assert (repo / "pulse.log").read_text().count("alive") >= 3
    finally:
        os.chdir(cwd)
        if previous_pythonpath:
            os.environ["PYTHONPATH"] = previous_pythonpath
        else:
            os.environ.pop("PYTHONPATH", None)
