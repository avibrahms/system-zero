#!/usr/bin/env python3
"""Run sz.core.genesis.genesis() with a canned LLM profile, in-process.

Usage:
  run_genesis_with_profile.py --profile '<json>'

This replaces sz.interfaces.llm.invoke with a function that returns the profile
directly, then calls genesis() and writes the profile to .sz/repo-profile.json.
"""
import argparse
import json
from types import SimpleNamespace


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True)
    a = ap.parse_args()
    profile = json.loads(a.profile)
    from sz.interfaces import llm

    def fake_invoke(prompt, *, schema_path=None, template_id=None, model=None, max_tokens=1024):
        return SimpleNamespace(text=json.dumps(profile), parsed=profile,
                               tokens_in=0, tokens_out=0, model="mock:canned")

    llm.invoke = fake_invoke  # monkeypatch for this process
    from sz.core import genesis as engine
    engine.genesis(auto_yes=True)


if __name__ == "__main__":
    main()
