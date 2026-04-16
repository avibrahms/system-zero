#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys

from sz.interfaces import llm


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="Run a tiny live llm.invoke against the selected provider.")
    parser.add_argument("--prompt", default="Reply with exactly OK and nothing else.")
    args = parser.parse_args()

    status = llm.provider_status()
    payload: dict[str, object] = {"provider_status": status}
    if args.live:
        result = llm.invoke(args.prompt, max_tokens=32)
        payload["live_result"] = {
            "provider": result.provider,
            "model": result.model,
            "text": result.text.strip(),
            "tokens_in": result.tokens_in,
            "tokens_out": result.tokens_out,
        }
    json.dump(payload, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
