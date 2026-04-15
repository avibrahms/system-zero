# Phase 09 — Catalog and Distribution Channels

## Goal

Stand up the public catalog (a GitHub repo S0 fetches from) AND ship S0 through every channel the user might use:

1. **PyPI** — `pipx install system-zero`.
2. **npm** — `npm i -g system-zero` (Node wrapper installs and invokes the Python CLI).
3. **curl bootstrap** — `curl -sSL https://systemzero.dev/i | sh`.
4. **Brew tap** — `brew install systemzero-dev/tap/system-zero` (formula scaffolded; tap repo created in phase 15).
5. **Web one-click** — `systemzero.dev` "Install on this repo" page (the page itself is in phase 11; here we ship the install command generator).

The Python package is the canonical artifact; npm and brew wrap it.

## Inputs

- Phases 00–08 complete.
- `GH_TOKEN`, `NPM_TOKEN`, `PYPI` available.

## Outputs

- `catalog/modules/<id>/` for each of the seven modules from phase 08.
- `catalog/index.json` (auto-built).
- `catalog/scripts/build-index.py`.
- `sz/commands/catalog.py` — full implementation.
- `dist/` — built `system_zero-0.1.0.tar.gz` and `.whl`.
- `npm-wrapper/` — Node package source.
- `install.sh` — curl bootstrap.
- `brew/system-zero.rb` — Homebrew formula stub.
- `tests/distribution/test_install_channels.sh` — end-to-end channel test.
- Current-branch git checkpoint history for this phase, with no branch operations.

## Atomic steps

### Step 9.1 — Confirm current branch + dirs

```bash
git branch --show-current
mkdir -p catalog/modules catalog/scripts npm-wrapper/{bin,scripts} brew tests/distribution
```

Verify: prints the current branch name, creates the distribution directories, and does not create or switch branches.

### Step 9.2 — Catalog entries

For each of `heartbeat, immune, subconscious, dreaming, metabolism, endocrine, prediction`:

`catalog/modules/<id>/module.yaml` — copy of `modules/<id>/module.yaml`.

`catalog/modules/<id>/source.yaml`:
```yaml
type: git
url: https://github.com/systemzero-dev/system-zero
ref: v0.1.0
path: modules/<id>
```

(For development before the public repo exists, use `type: local` with absolute paths. Phase 15 swaps to `git`.)

`catalog/modules/<id>/README.md` — paragraph-long human-facing description.

### Step 9.3 — `catalog/scripts/build-index.py`

```python
#!/usr/bin/env python3
"""Generate catalog/index.json from catalog/modules/."""
import json, sys
from pathlib import Path
import yaml

HERE = Path(__file__).resolve().parents[1]
MODULES = HERE / "modules"
OUT = HERE / "index.json"


def main() -> int:
    items = []
    for mdir in sorted(MODULES.iterdir()):
        man_p = mdir / "module.yaml"
        src_p = mdir / "source.yaml"
        rdme = mdir / "README.md"
        if not (man_p.exists() and src_p.exists()):
            continue
        man = yaml.safe_load(man_p.read_text())
        src = yaml.safe_load(src_p.read_text())
        items.append({
            "id": man["id"],
            "version": man["version"],
            "category": man.get("category", ""),
            "description": man.get("description", ""),
            "personas": man.get("personas", ["static", "dynamic"]),
            "provides": [c["name"] for c in man.get("provides", []) or []],
            "requires": [r["name"] for r in (man.get("requires") or []) if "name" in r],
            "setpoints": man.get("setpoints", {}),
            "source": src,
            "readme": rdme.read_text() if rdme.exists() else "",
        })
    OUT.write_text(json.dumps({"version": "0.1.0", "items": items}, indent=2))
    print(f"wrote {OUT} ({len(items)} entries)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

Run:
```bash
chmod +x catalog/scripts/build-index.py
catalog/scripts/build-index.py
```

Verify: `cat catalog/index.json | jq '.items | length'` returns `7`.

### Step 9.4 — Replace `sz/commands/catalog.py`

Same shape as the sz version: `list`, `show`, `fetch`. `DEFAULT_INDEX_URL` is `https://raw.githubusercontent.com/systemzero-dev/catalog/main/index.json`. Override via env `SZ_CATALOG`.

### Step 9.5 — `sz install` fetches from catalog by default

In `sz/commands/install.py`, when `source` is `None`, fetch via `sz catalog fetch <name> --out <tmp>` and proceed with the temp dir as `source`.

### Step 9.6 — Build the Python package

```bash
python3 -m pip install --upgrade build
python3 -m build
ls dist/
```

Verify: `dist/system_zero-0.1.0-py3-none-any.whl` and `dist/system_zero-0.1.0.tar.gz` exist.

### Step 9.7 — npm wrapper

`npm-wrapper/package.json`:
```json
{
  "name": "system-zero",
  "version": "0.1.0",
  "description": "One-click autonomy and self-improvement for any repo.",
  "bin": {
    "sz": "bin/sz"
  },
  "scripts": {
    "postinstall": "node scripts/install-python-package.js"
  },
  "homepage": "https://systemzero.dev",
  "repository": {
    "type": "git",
    "url": "git+https://github.com/systemzero-dev/system-zero.git",
    "directory": "npm-wrapper"
  },
  "license": "Apache-2.0"
}
```

`npm-wrapper/bin/s0`:
```bash
#!/usr/bin/env node
const { spawnSync } = require('child_process');
const r = spawnSync('sz', process.argv.slice(2), { stdio: 'inherit' });
process.exit(r.status === null ? 1 : r.status);
```

`npm-wrapper/scripts/install-python-package.js`:
```javascript
#!/usr/bin/env node
const { spawnSync } = require('child_process');
const which = (cmd) => spawnSync('which', [cmd], { encoding: 'utf-8' }).stdout.trim();

function run(cmd, args) {
  console.log(`> ${cmd} ${args.join(' ')}`);
  const r = spawnSync(cmd, args, { stdio: 'inherit' });
  return r.status === 0;
}

(async () => {
  if (which('pipx')) {
    if (!run('pipx', ['install', 'system-zero==0.1.0', '--force'])) process.exit(1);
  } else if (which('pip3')) {
    if (!run('pip3', ['install', '--user', 'system-zero==0.1.0'])) process.exit(1);
  } else if (which('python3')) {
    if (!run('python3', ['-m', 'pip', 'install', '--user', 'system-zero==0.1.0'])) process.exit(1);
  } else {
    console.error('No Python found. Install Python 3.10+ then re-run `npm i -g system-zero`.');
    process.exit(1);
  }
  console.log('system-zero CLI (s0) installed. Run `sz --help` to begin.');
})();
```

`chmod +x npm-wrapper/bin/s0 npm-wrapper/scripts/install-python-package.js`.

### Step 9.8 — `install.sh` (curl bootstrap)

`install.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail
echo "== System Zero installer =="
PYTHON="${PYTHON:-python3}"
$PYTHON --version >/dev/null 2>&1 || { echo "Need python3 (3.10+). Install it first." >&2; exit 1; }

if command -v pipx >/dev/null; then
  echo "Using pipx."
  pipx install --force system-zero==0.1.0
elif $PYTHON -m pip --version >/dev/null 2>&1; then
  echo "Using pip --user."
  $PYTHON -m pip install --user --upgrade system-zero==0.1.0
else
  echo "Need pip or pipx." >&2; exit 1
fi

echo ""
echo "Installed. Try: sz --help"
echo "Quick start:"
echo "  cd your/repo"
echo "  sz init     # this will run Repo Genesis"
```

`chmod +x install.sh`.

### Step 9.9 — Brew formula stub

`brew/system-zero.rb`:
```ruby
class SystemZero < Formula
  desc "One-click autonomy and self-improvement for any repository"
  homepage "https://systemzero.dev"
  url "https://files.pythonhosted.org/packages/source/s/system-zero/system_zero-0.1.0.tar.gz"
  sha256 "REPLACE_AFTER_PYPI_PUBLISH"
  license "Apache-2.0"
  depends_on "python@3.12"

  def install
    system Formula["python@3.12"].opt_bin/"python3", "-m", "venv", libexec
    system libexec/"bin/python3", "-m", "pip", "install", "--upgrade", "pip"
    system libexec/"bin/python3", "-m", "pip", "install", "system-zero==0.1.0"
    bin.install_symlink libexec/"bin/sz"
  end

  test do
    assert_match "0.1.0", shell_output("#{bin}/sz --version")
  end
end
```

The actual tap repo is created in phase 15.

### Step 9.10 — Cross-channel test driver

`tests/distribution/test_install_channels.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail
REPORT="${REPORT:-$PWD/.test-reports/phase-09.json}"
mkdir -p "$(dirname "$REPORT")"
results='[]'

record() { results=$(echo "$results" | jq --arg n "$1" --arg s "$2" --arg d "$3" '. + [{name:$n,status:$s,detail:$d}]'); }

# 1) PyPI-equivalent: install from local wheel via pipx
TMP=$(mktemp -d)
WHEEL=$(ls "$PWD/dist"/system_zero-0.1.0-py3-none-any.whl)
PIPX_HOME="$TMP/pipx" PIPX_BIN_DIR="$TMP/bin" pipx install "$WHEEL" --force
"$TMP/bin/s0" --version | grep -q "0.1.0" && record "channel: pip wheel" pass "$WHEEL" || record "channel: pip wheel" fail ""

# 2) curl bootstrap
PIPX_HOME="$TMP/pipx2" PIPX_BIN_DIR="$TMP/bin2" bash install.sh
"$TMP/bin2/s0" --version | grep -q "0.1.0" && record "channel: install.sh" pass "" || record "channel: install.sh" fail ""

# 3) npm wrapper
( cd npm-wrapper && npm pack --silent )
TGZ=$(ls "$PWD/npm-wrapper"/system-zero-0.1.0.tgz)
NPM_PREFIX="$TMP/npm" mkdir -p "$NPM_PREFIX"
PIPX_HOME="$TMP/pipx3" PIPX_BIN_DIR="$TMP/bin3" PATH="$TMP/bin3:$PATH" npm i -g --prefix "$NPM_PREFIX" "$TGZ"
"$NPM_PREFIX/bin/s0" --version | grep -q "0.1.0" && record "channel: npm" pass "$TGZ" || record "channel: npm" fail ""

echo "$results" | jq . > "$REPORT"
echo "Channels report at $REPORT"
FAILED=$(jq '[.[] | select(.status==\"fail\")] | length' "$REPORT")
[ "$FAILED" -eq 0 ] || { echo "PHASE 09 FAILED ($FAILED)"; exit 1; }
echo "PHASE 09 PASSED"
```

`chmod +x tests/distribution/test_install_channels.sh`.

Run:
```bash
bash tests/distribution/test_install_channels.sh
```

Verify: prints `PHASE 09 PASSED`.

### Step 9.11 — Pytest wrappers

`tests/distribution/test_catalog_index.py`:
```python
import json
from pathlib import Path

HERE = Path(__file__).resolve().parents[2]


def test_catalog_has_seven():
    idx = json.loads((HERE / "catalog" / "index.json").read_text())
    assert idx["version"] == "0.1.0"
    ids = {it["id"] for it in idx["items"]}
    assert ids >= {"heartbeat","immune","subconscious","dreaming","metabolism","endocrine","prediction"}
```

`tests/distribution/test_install_from_catalog.py`: monkeypatches `SZ_CATALOG` to a local `file://` URL; `sz install heartbeat` succeeds; registry has heartbeat.

Run:
```bash
python3 -m pytest tests/distribution -q
```

### Step 9.12 — Commit

```bash
git add catalog s0 npm-wrapper install.sh brew tests/distribution plan/phase-09-catalog-and-distribution
git commit -m "phase 09: catalog and four distribution channels complete"
```

## Acceptance criteria

1. `catalog/index.json` exists with all seven modules.
2. `pipx install dist/system_zero-0.1.0-py3-none-any.whl` produces a working `sz`.
3. `bash install.sh` produces a working `sz`.
4. `npm pack` + local install via the wrapper produces a working `sz`.
5. `sz install heartbeat` (no `--source`) fetches via the catalog and installs.
6. `tests/distribution/test_install_channels.sh` ends with `PHASE 09 PASSED`.
7. `pytest tests/distribution -q` is green.

## Failure modes and recovery

| Symptom | Cause | Action |
|---|---|---|
| pipx not on PATH after install | `~/.local/bin` missing | install.sh prints PATH hint with `--update-path` flag |
| npm postinstall fails on Windows | not v0.1 target | document; user runs pipx directly |
| Brew formula sha256 placeholder | post-publish | regenerate after phase 15 PyPI publish |
| Catalog 404 from raw.githubusercontent | repo not yet public | use `file://` fallback or jsdelivr mirror |

## Rollback

`git checkout main && git branch -D phase-09-catalog-and-distribution && rm -rf catalog npm-wrapper install.sh brew dist`.
