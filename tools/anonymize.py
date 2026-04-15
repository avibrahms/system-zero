#!/usr/bin/env python3
"""Scan a module directory and reject if operator-identifying tokens appear."""
import re, sys, pathlib

SKIP_PARTS = {".git", "__pycache__", "node_modules", ".venv", "venv"}

PATTERNS = [
    (re.compile(r"\b[Aa]vi\b"), "operator first name"),
    (re.compile(r"\bavi[-_](products|voice)\b", re.I), "operator identifier"),
    (re.compile(r"\b[aA]vi[- _]?[bB]elhassen\b"), "operator name"),
    (re.compile(r"/Users/avi/"), "operator home path"),
    (re.compile(r"/home/avi/"), "operator home path"),
    (re.compile(r"\bavi[a-z0-9_-]*@[a-z0-9.-]+\.[a-z]+"), "operator email"),
    (re.compile(r"\bviralepic\b", re.I), "operator product"),
    (re.compile(r"\bcomplianceiq\b", re.I), "operator product"),
    (re.compile(r"\bdebt[_-]?radar\b", re.I), "operator product"),
    (re.compile(r"\bagent[_-]?bill\b", re.I), "operator product"),
    (re.compile(r"\bbreakpoint[_-]?ai\b", re.I), "operator product"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "AWS key"),
    (re.compile(r"sk-[A-Za-z0-9]{40,}"), "provider secret"),
    (re.compile(r"pk_live_[A-Za-z0-9]{20,}"), "stripe publishable live"),
    (re.compile(r"sk_live_[A-Za-z0-9]{20,}"), "stripe secret live"),
    (re.compile(r"whsec_[A-Za-z0-9]{20,}"), "stripe webhook"),
    (re.compile(r"heartbeat-beacon"), "personal beacon endpoint"),
    (re.compile(r"avi[a-z0-9]*\.(com|net|io|dev|app)\b", re.I), "operator domain"),
]

def scan(module_dir: pathlib.Path) -> list[tuple[pathlib.Path, str, str]]:
    hits = []
    for p in module_dir.rglob("*"):
        if any(part in SKIP_PARTS for part in p.parts):
            continue
        if not p.is_file(): continue
        try: text = p.read_text(errors="ignore")
        except Exception: continue
        for rx, label in PATTERNS:
            for m in rx.finditer(text):
                hits.append((p, label, m.group(0)[:60]))
    return hits

def main():
    if len(sys.argv) != 2:
        print("usage: anonymize.py <module-dir>"); sys.exit(2)
    d = pathlib.Path(sys.argv[1])
    hits = scan(d)
    for p, label, sample in hits:
        print(f"HIT {label}: {p.relative_to(d)} :: {sample}")
    sys.exit(1 if hits else 0)

if __name__ == "__main__":
    main()
