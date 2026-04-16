#!/usr/bin/env python3
"""Exercise executable behavior contracts for absorbed System Zero modules."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def run(command: list[str], *, cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise AssertionError(
            "command failed\n"
            f"cwd: {cwd}\n"
            f"cmd: {' '.join(command)}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    return result


def cli(env: dict[str, str], cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return run([sys.executable, "-m", "sz.commands.cli", *args], cwd=cwd, env=env)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def result_for(repo: Path, module_id: str, task_id: str = "bootstrap") -> dict[str, Any]:
    return load_json(repo / ".sz" / "shared" / "absorbed" / module_id / "results" / f"{task_id}.json")


def assert_status(result: dict[str, Any], expected: str, *, module_id: str) -> dict[str, Any]:
    execution = result.get("execution", {})
    actual = execution.get("status")
    if actual != expected:
        raise AssertionError(f"{module_id}: expected execution status {expected!r}, got {actual!r}: {result}")
    return execution


def make_fixtures(fixtures: Path) -> dict[str, Path]:
    py_cli = fixtures / "py-cli"
    write(py_cli / "README.md", "# Python CLI\n\nRun with `python3 app.py`.\n")
    write(
        py_cli / "app.py",
        "from pathlib import Path\n"
        "import os\n"
        "Path('result.txt').write_text('python ok ' + os.environ.get('S0_TASK_ID', 'missing') + '\\n')\n"
        "print('python-behavior-ran')\n",
    )

    node_cli = fixtures / "node-cli"
    write(node_cli / "README.md", "# Node CLI\n\nRun with `npm run test` or `npm run build`.\n")
    write(
        node_cli / "package.json",
        json.dumps(
            {
                "scripts": {
                    "test": "node index.js test",
                    "build": "node index.js build",
                }
            },
            indent=2,
        )
        + "\n",
    )
    write(
        node_cli / "index.js",
        "const fs = require('fs');\n"
        "const mode = process.argv[2] || 'unknown';\n"
        "fs.writeFileSync(`${mode}-result.txt`, `node ${mode} ok\\n`);\n"
        "console.log(`node-${mode}-behavior-ran`);\n",
    )

    fail_cli = fixtures / "fail-cli"
    write(fail_cli / "README.md", "# Failing CLI\n\nRun with `python3 app.py`.\n")
    write(fail_cli / "app.py", "print('failing deliberately')\nraise SystemExit(7)\n")

    timeout_cli = fixtures / "timeout-cli"
    write(timeout_cli / "README.md", "# Timeout CLI\n\nRun with `python3 app.py`.\n")
    write(timeout_cli / "app.py", "import time\nprint('sleeping')\ntime.sleep(10)\n")

    inspect_only = fixtures / "inspect-only"
    write(inspect_only / "README.md", "# Inspect Only\n\nThis fixture has no safe executable command.\n")

    return {
        "behavior-py": py_cli,
        "behavior-node": node_cli,
        "behavior-fail": fail_cli,
        "behavior-timeout": timeout_cli,
        "behavior-inspect": inspect_only,
    }


def absorb(env: dict[str, str], repo: Path, fixture: Path, module_id: str, feature: str) -> None:
    cli(
        env,
        repo,
        "absorb",
        str(fixture),
        "--feature",
        feature,
        "--id",
        module_id,
        "--auto-rollback",
        "--force",
    )


def verify_contract_shape(repo: Path, modules: list[str]) -> None:
    for module_id in modules:
        module_dir = repo / ".sz" / module_id
        manifest = load_json(module_dir / "source_manifest.json")
        contract = manifest.get("behavior_contract", {})
        actions = contract.get("actions", [])
        if manifest.get("adapter") != "system-zero-protocol-absorb-v2":
            raise AssertionError(f"{module_id}: adapter was not upgraded: {manifest.get('adapter')}")
        if not (module_dir / "source_repo").is_dir():
            raise AssertionError(f"{module_id}: missing executable source_repo")
        if contract.get("version") != "system-zero-behavior-contract-v1" or not actions:
            raise AssertionError(f"{module_id}: missing behavior contract actions")
        for action in actions:
            if not isinstance(action.get("command"), list) or not action["command"]:
                raise AssertionError(f"{module_id}: invalid behavior command: {action}")


def verify_behavior(repo: Path) -> dict[str, Any]:
    summary: dict[str, Any] = {}

    py_execution = assert_status(result_for(repo, "behavior-py"), "completed", module_id="behavior-py")
    py_outputs = {item.get("path") for item in py_execution.get("outputs", [])}
    if "result.txt" not in py_outputs:
        raise AssertionError(f"behavior-py: result.txt was not captured: {py_execution}")
    summary["python_success"] = {"action": py_execution.get("action"), "outputs": sorted(py_outputs)}

    node_execution = assert_status(result_for(repo, "behavior-node"), "completed", module_id="behavior-node")
    node_outputs = {item.get("path") for item in node_execution.get("outputs", [])}
    if node_execution.get("action") != "root_build" or "build-result.txt" not in node_outputs:
        raise AssertionError(f"behavior-node: action override did not run root_build: {node_execution}")
    summary["action_override"] = {"action": node_execution.get("action"), "outputs": sorted(node_outputs)}

    fail_execution = assert_status(result_for(repo, "behavior-fail"), "failed", module_id="behavior-fail")
    if fail_execution.get("returncode") != 7:
        raise AssertionError(f"behavior-fail: wrong returncode: {fail_execution}")
    summary["failure_recording"] = {"action": fail_execution.get("action"), "returncode": fail_execution.get("returncode")}

    timeout_execution = assert_status(result_for(repo, "behavior-timeout"), "timeout", module_id="behavior-timeout")
    summary["timeout_recording"] = {
        "action": timeout_execution.get("action"),
        "duration_seconds": timeout_execution.get("duration_seconds"),
    }

    inspect_execution = assert_status(result_for(repo, "behavior-inspect"), "completed", module_id="behavior-inspect")
    if inspect_execution.get("action") != "inspect":
        raise AssertionError(f"behavior-inspect: fallback action did not run inspect: {inspect_execution}")
    summary["fallback_inspect"] = {"action": inspect_execution.get("action")}

    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--keep", action="store_true", help="Keep the temporary verification repo.")
    args = parser.parse_args()

    npm_available = shutil.which("npm") is not None and shutil.which("node") is not None
    with tempfile.TemporaryDirectory(prefix="s0-absorb-behavior-") as temp:
        temp_root = Path(temp)
        fixtures = make_fixtures(temp_root / "fixtures")
        repo = temp_root / "repo"
        repo.mkdir()
        env = dict(os.environ)
        env.update(
            {
                "PYTHONPATH": f"{REPO_ROOT}{os.pathsep}{env.get('PYTHONPATH', '')}",
                "SZ_LLM_PROVIDER": "mock",
                "SZ_COMMAND": f"{sys.executable} -m sz.commands.cli",
                "SZ_TELEMETRY_JOIN_SECONDS": "0",
            }
        )

        cli(env, repo, "init", "--host", "generic", "--host-mode", "install", "--yes", "--no-genesis")
        modules = ["behavior-py", "behavior-fail", "behavior-timeout", "behavior-inspect"]
        absorb(env, repo, fixtures["behavior-py"], "behavior-py", "python behavior writes a result file")
        before_execute = result_for(repo, "behavior-py")
        assert_status(before_execute, "waiting_for_execute", module_id="behavior-py observe smoke")

        if npm_available:
            modules.append("behavior-node")
            absorb(env, repo, fixtures["behavior-node"], "behavior-node", "node test behavior with alternate build command")
        absorb(env, repo, fixtures["behavior-fail"], "behavior-fail", "python behavior exits with an error")
        absorb(env, repo, fixtures["behavior-timeout"], "behavior-timeout", "python behavior times out")
        absorb(env, repo, fixtures["behavior-inspect"], "behavior-inspect", "plain docs without executable behavior")

        verify_contract_shape(repo, modules)

        for module_id in modules:
            cli(env, repo, "setpoint", "set", module_id, "execution_mode", "execute")
        if npm_available:
            cli(env, repo, "setpoint", "set", "behavior-node", "action_name", "root_build")
        cli(env, repo, "setpoint", "set", "behavior-timeout", "command_timeout_seconds", "1")
        cli(env, repo, "tick", "--reason", "verify-absorb-behavior-contract")

        summary = {
            "status": "passed",
            "repo": str(repo),
            "modules": modules,
            "scenarios": verify_behavior(repo),
            "npm_scenario": "passed" if npm_available else "skipped: npm/node unavailable",
        }
        print(json.dumps(summary, indent=2, sort_keys=True))
        if args.keep:
            kept = Path("/tmp") / f"{repo.name}-kept"
            if kept.exists():
                shutil.rmtree(kept)
            shutil.copytree(repo, kept)
            print(json.dumps({"kept_repo": str(kept)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
