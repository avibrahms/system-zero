import os, json, shutil, subprocess
from pathlib import Path
import pytest

HERE = Path(__file__).resolve().parents[3]
CACHE = Path.home() / ".sz" / "cache" / "test-fixtures" / "absorb"


@pytest.mark.skipif(shutil.which("sz") is None, reason="sz missing")
@pytest.mark.skipif(not (CACHE / "p-limit").exists(), reason="p-limit missing")
def test_absorb_three_features(tmp_path, stub_absorb_llm):
    cwd = Path.cwd()
    repo = tmp_path / "repo"
    repo.mkdir()
    env = os.environ.copy()
    test_home = tmp_path / "home"
    test_home.mkdir()
    env["HOME"] = str(test_home)
    env["SZ_LLM_PROVIDER"] = "mock"
    env["SZ_ABSORB_CANNED"] = str(HERE / "tests" / "e2e" / "absorb" / "canned")
    source_cache = Path(env.get("SZ_ABSORB_SOURCE_CACHE", str(CACHE)))
    os.chdir(repo)
    try:
        subprocess.run(["git", "init", "-q"], check=True, env=env)
        subprocess.run(["git", "config", "user.email", "t@t"], check=True, env=env)
        subprocess.run(["git", "config", "user.name",  "t"], check=True, env=env)
        subprocess.run(["git", "config", "commit.gpgsign", "false"], check=True, env=env)
        Path("README.md").write_text("init\n")
        subprocess.run(["git", "add", "README.md"], check=True, env=env)
        subprocess.run(["git", "commit", "-qm", "init"], check=True, env=env)
        subprocess.run(["sz", "init", "--host", "generic", "--no-genesis"], check=True, env=env)
        for m in ["heartbeat","immune","subconscious","metabolism"]:
            subprocess.run(["sz", "install", m, "--source", str(HERE/"modules"/m)], check=True, env=env)

        initial_bus = len(bus_tail(env))
        initial_snapshot = snapshot_count(env)

        before = reaction_counts(env)
        absorb(source_cache / "p-limit", "concurrency limiter", env)
        Path("anomaly-1.md").write_text("FIXME absorb one reaction\n")
        subprocess.run(["sz", "tick", "--reason", "pytest-absorb-1"], check=True, env=env)
        limiter = bus_tail(env, "limiter.metric")[-1]["payload"]
        assert limiter["peak"] <= 4
        assert_reaction_grew(before, reaction_counts(env))

        before = reaction_counts(env)
        absorb(source_cache / "changed-files", "changed file detector", env)
        Path("anomaly-2.md").write_text("FIXME absorb two reaction\n")
        subprocess.run(["git", "add", "-A"], check=True, env=env)
        subprocess.run(["git", "commit", "-qm", "baseline before changed-files check"], check=True, env=env)
        Path("a.txt").write_text("x\n")
        Path("b.txt").write_text("y\n")
        subprocess.run(["git", "add", "a.txt", "b.txt"], check=True, env=env)
        subprocess.run(["git", "commit", "-qm", "two"], check=True, env=env)
        sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, env=env).strip()
        subprocess.run(["sz", "bus", "emit", "host.commit.made", json.dumps({"sha": sha})], check=True, env=env)
        subprocess.run(["sz", "tick", "--reason", "pytest-absorb-2"], check=True, env=env)
        changed = sorted(bus_tail(env, "changed.files")[-1]["payload"]["files"])
        assert changed == ["a.txt", "b.txt"]
        assert_reaction_grew(before, reaction_counts(env))

        before = reaction_counts(env)
        absorb(source_cache / "llm", "llm provider bridge", env)
        Path("anomaly-3.md").write_text("FIXME absorb three reaction\n")
        subprocess.run(["sz", "bus", "emit", "ask.llm", '{"prompt":"hi"}'], check=True, env=env)
        subprocess.run(["sz", "tick", "--reason", "pytest-absorb-3"], check=True, env=env)
        invoked = bus_tail(env, "llm.invoked")[-1]["payload"]
        assert invoked["text"]
        assert_reaction_grew(before, reaction_counts(env))

        reg = json.loads((repo/".sz"/"registry.json").read_text())
        assert {"concurrency-limiter","changed-file-detector","llm-provider-bridge"}.issubset(set(reg["modules"]))
        assert len(bus_tail(env)) > initial_bus
        assert snapshot_count(env) > initial_snapshot
        subprocess.run(["sz","reconcile"], check=True, env=env)
        a = json.loads((repo/".sz"/"registry.json").read_text()); a.pop("generated_at",None)
        subprocess.run(["sz","reconcile"], check=True, env=env)
        b = json.loads((repo/".sz"/"registry.json").read_text()); b.pop("generated_at",None)
        assert a == b
    finally:
        os.chdir(cwd)


def absorb(source: Path, feature: str, env: dict[str, str]) -> None:
    result = subprocess.run(
        ["sz", "absorb", str(source), "--feature", feature],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0, result.stderr


def bus_tail(env: dict[str, str], pattern: str | None = None) -> list[dict[str, object]]:
    command = ["sz", "bus", "tail"]
    if pattern:
        command.extend(["--filter", pattern])
    result = subprocess.run(command, check=True, capture_output=True, text=True, env=env)
    return json.loads(result.stdout)


def memory_get(key: str, env: dict[str, str]):
    result = subprocess.run(["sz", "memory", "get", key], check=True, capture_output=True, text=True, env=env)
    return json.loads(result.stdout)


def snapshot_count(env: dict[str, str]) -> int:
    snapshot = memory_get("subconscious.snapshot", env)
    if not isinstance(snapshot, dict):
        return 0
    return int(snapshot.get("anomaly_count") or 0)


def reaction_counts(env: dict[str, str]) -> tuple[int, int, int]:
    return (
        len(bus_tail(env)),
        len(bus_tail(env, "pulse.tick")),
        snapshot_count(env),
    )


def assert_reaction_grew(before: tuple[int, int, int], after: tuple[int, int, int]) -> None:
    assert after[0] > before[0], (before, after)
    assert after[1] > before[1], (before, after)
    assert after[2] > before[2], (before, after)
