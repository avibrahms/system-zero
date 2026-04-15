#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
VENV_DIR = REPO_ROOT / "tmp" / "phase26-mcp-venv"
VENV_PYTHON = VENV_DIR / "bin" / "python"
SERVERS = {
    "memory": REPO_ROOT / "core" / "system" / "mcp" / "memory_server.py",
    "bus": REPO_ROOT / "core" / "system" / "mcp" / "bus_server.py",
    "control": REPO_ROOT / "core" / "system" / "mcp" / "control_server.py",
}


def _has_mcp(python_bin: Path) -> bool:
    if not python_bin.exists():
        return False
    return subprocess.run([str(python_bin), "-c", "import mcp"], capture_output=True, check=False).returncode == 0


def ensure_runtime() -> Path:
    if _has_mcp(VENV_PYTHON):
        return VENV_PYTHON
    if not VENV_PYTHON.exists():
        subprocess.run([sys.executable, "-m", "venv", str(VENV_DIR)], cwd=REPO_ROOT, check=True)
    subprocess.run([str(VENV_PYTHON), "-m", "pip", "install", "mcp"], cwd=REPO_ROOT, check=True)
    return VENV_PYTHON


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Launch a local MCP server through the managed phase-26 virtualenv."
    )
    parser.add_argument("server", nargs="?", choices=sorted(SERVERS), help="Server slug to launch")
    parser.add_argument("server_args", nargs=argparse.REMAINDER, help="Arguments forwarded to the target server")
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    if not args.server:
        parser.print_help()
        return 0
    python_bin = ensure_runtime()
    target = SERVERS[args.server]
    os.execv(str(python_bin), [str(python_bin), str(target), *args.server_args])


if __name__ == "__main__":
    raise SystemExit(main())
