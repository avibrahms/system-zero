import os, json, shutil, subprocess
from pathlib import Path
import pytest

HERE = Path(__file__).resolve().parents[3]
CACHE = Path.home() / ".sz" / "cache" / "test-fixtures" / "absorb"


@pytest.mark.skipif(shutil.which("sz") is None, reason="sz missing")
@pytest.mark.skipif(not (CACHE / "p-limit").exists(), reason="p-limit missing")
def test_absorb_three_features(tmp_path, stub_absorb_llm):
    cwd = Path.cwd()
    env = os.environ.copy()
    env["SZ_LLM_PROVIDER"] = "mock"
    env["SZ_ABSORB_CANNED"] = str(HERE / "tests" / "e2e" / "absorb" / "canned")
    os.chdir(tmp_path)
    try:
        subprocess.run(["git", "init", "-q"], check=True, env=env)
        subprocess.run(["git", "config", "user.email", "t@t"], check=True, env=env)
        subprocess.run(["git", "config", "user.name",  "t"], check=True, env=env)
        subprocess.run(["sz", "init", "--host", "generic", "--no-genesis"], check=True, env=env)
        for m in ["heartbeat","immune","subconscious","metabolism"]:
            subprocess.run(["sz", "install", m, "--source", str(HERE/"modules"/m)], check=True, env=env)
        for src in [CACHE/"p-limit", CACHE/"changed-files", CACHE/"llm"]:
            r = subprocess.run(["sz","absorb",str(src),"--feature","auto"], capture_output=True, text=True, env=env)
            assert r.returncode == 0, r.stderr
        reg = json.loads((tmp_path/".sz"/"registry.json").read_text())
        assert {"concurrency-limiter","changed-file-detector","llm-provider-bridge"}.issubset(set(reg["modules"]))
        subprocess.run(["sz","reconcile"], check=True, env=env)
        a = json.loads((tmp_path/".sz"/"registry.json").read_text()); a.pop("generated_at",None)
        subprocess.run(["sz","reconcile"], check=True, env=env)
        b = json.loads((tmp_path/".sz"/"registry.json").read_text()); b.pop("generated_at",None)
        assert a == b
    finally:
        os.chdir(cwd)
