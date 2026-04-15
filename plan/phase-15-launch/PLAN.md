# Phase 15 — Launch

## Goal

Make System Zero publicly usable. Audit the current-branch checkpoint history, run the full test bench, publish the Python package to PyPI, publish the npm wrapper to npm, create the Homebrew tap, deploy the cloud apps to Fly.io, point DNS at them via Hostinger, cut a v0.1.0 GitHub release, post a launch announcement.

This phase introduces no new code beyond minor configuration; it executes the publishing steps.

## Inputs

- Phases 00–14 complete and committed on the current branch.
- All credentials in `.env` validated in phase 00.
- The two Fly.io apps (`sz-cloud`, `sz-web`) live from phases 10 and 11.

## Outputs

- The current branch containing every phase's checkpoint commit history.
- Public GitHub repos `avibrahms/system-zero`, `avibrahms/catalog`, `avibrahms/homebrew-tap`.
- `sz-cli==0.1.0` on PyPI (`system-zero==0.1.0` and `system-zero-cli==0.1.0` were published first but failed packaged smoke; the release state records the launchable package).
- `system-zero@0.1.0` on npm.
- `$(jq -r '.endpoints.web' .s0-release.json)/i` returns the install bootstrap.
- `$(jq -r '.endpoints.api' .s0-release.json)/v1/catalog/index` returns the seven modules.
- A v0.1.0 GitHub Release with `dist/*` and `install.sh` attached.
- `launch/announce.md` with a draft post for LinkedIn / X / HN.

## Atomic steps

### Step 15.1 — Audit the current-branch checkpoint history

```bash
git branch --show-current
git log --oneline | head -25
```

Verify: prints the current branch name and shows the accumulated checkpoint history from phases 00–14 without any branch merges.

### Step 15.2 — Re-run the full test bench

```bash
python3 -m pytest -q
bash tests/e2e/static/run.sh
bash tests/e2e/dynamic/run.sh
bash tests/e2e/absorb/run.sh
bash tests/distribution/test_install_channels.sh
```

Verify: every command exits 0.

Recovery: do not patch over failures. `git revert` the offending checkpoint commit(s), fix the underlying phase, rerun.

### Step 15.3 — Create public GitHub repos

```bash
. ./.env
gh auth status
GITHUB_OWNER="${SZ_GITHUB_OWNER:-avibrahms}"
python3 - <<PY
import json, pathlib, os
p = pathlib.Path(".s0-release.json"); s = json.loads(p.read_text())
s["github_owner"] = os.environ.get("SZ_GITHUB_OWNER", "avibrahms")
p.write_text(json.dumps(s, indent=2) + "\n")
PY

# Helper: create a public GitHub repo; auto-append suffix on name collision (per Appendix A in plan/EXECUTION_RULES.md).
create_repo_with_rename() {
  local org="$1" desired="$2" src_dir="$3"
  local chosen=""
  for suffix in "" -protocol -dev-2 -dev-3; do
    local cand="$desired$suffix"
    if gh repo create "$org/$cand" --public --source "$src_dir" --push 2>/tmp/gh.log; then
      chosen="$cand"; break
    elif grep -q "already exists\|Name already exists" /tmp/gh.log; then
      continue
    else
      cat /tmp/gh.log >&2
      echo "gh repo create: unexpected error; trying next suffix"
    fi
  done
  if [ -z "$chosen" ]; then
    echo "github repo creation failed for owner=$org desired=$desired" >&2
    return 1
  fi
  echo "$chosen"
}

CORE_REPO=$(create_repo_with_rename "$GITHUB_OWNER" system-zero .)
CATALOG_REPO=$(cd catalog && create_repo_with_rename "$GITHUB_OWNER" catalog . && cd ..)
mkdir -p ../homebrew-tap/Formula
cp brew/system-zero.rb ../homebrew-tap/Formula/
( cd ../homebrew-tap && git init -q && git add -A && git commit -qm "tap v0.1.0" )
TAP_REPO=$(cd ../homebrew-tap && create_repo_with_rename "$GITHUB_OWNER" homebrew-tap . && cd -)

python3 - <<PY
import json, pathlib
p = pathlib.Path(".s0-release.json"); s = json.loads(p.read_text())
s["github_owner"] = "$GITHUB_OWNER"
s["github_repos"] = {"core": "$CORE_REPO", "catalog": "$CATALOG_REPO", "tap": "$TAP_REPO"}
for name, desired in [("$CORE_REPO","system-zero"), ("$CATALOG_REPO","catalog"), ("$TAP_REPO","homebrew-tap")]:
    if name != desired:
        s["degraded"].append(f"phase-15: github repo renamed: {desired} -> {name}")
p.write_text(json.dumps(s, indent=2) + "\n")
PY
```

Verify: `jq '.github_repos' .s0-release.json` shows three non-empty names. Each repo URL resolves.

### Step 15.4 — Update the catalog entries to point at the public source repo

For each `catalog/modules/<id>/source.yaml`, change `type: local` → `type: git`, `url:` → the public URL, `ref: v0.1.0`. Re-run `catalog/scripts/build-index.py`. Commit and push the catalog repo.

### Step 15.5 — Publish to PyPI (with auto-rename on name collision)

Try the canonical name; on "name already taken" (HTTP 403 / "already exists") cascade through `system-zero` → `systemzero` → `system-zero-cli` → `sz-cli`. First success wins and is written to `.s0-release.json.pypi_package`.

```bash
. ./.env
python3 -m pip install --upgrade build twine

CANDIDATES=("system-zero" "systemzero" "system-zero-cli" "sz-cli")
PUBLISHED_NAME=""

for NAME in "${CANDIDATES[@]}"; do
  cp pyproject.toml pyproject.toml.bak
  sed -i.tmp "s/^name = \".*\"/name = \"$NAME\"/" pyproject.toml
  rm -f pyproject.toml.tmp
  rm -rf dist && python3 -m build >/dev/null 2>&1 || { mv pyproject.toml.bak pyproject.toml; continue; }
  if TWINE_PASSWORD="$PYPI" TWINE_USERNAME="__token__" twine upload --non-interactive dist/* 2>&1 | tee /tmp/twine.log | grep -q "uploaded\|View at"; then
    PUBLISHED_NAME="$NAME"; rm -f pyproject.toml.bak; break
  fi
  # Restore, try next candidate.
  mv pyproject.toml.bak pyproject.toml
  echo "pypi: $NAME unavailable; trying next"
done

if [ -z "$PUBLISHED_NAME" ]; then
  {
    echo ""
    echo "## $(date -u +%FT%TZ) · phase-15 · pypi-deferred"
    echo ""
    echo "- **Category**: deferred"
    echo "- **What failed**: All PyPI candidates unavailable"
    echo "- **Bypass applied**: install.sh falls back to \`pip install git+https://github.com/avibrahms/system-zero@v0.1.0\`"
    echo "- **Downstream effect**: slower install for users; no visible PyPI entry"
    echo "- **Action to resolve**: free up the name or rotate token; re-run tooling/retry-pypi.sh"
    echo "- **Run command to retry only this bypass**: bash tooling/retry-pypi.sh"
  } >> BLOCKERS.md
else
  # Pin the chosen name into pyproject.toml for reproducibility and record it.
  sed -i.tmp "s/^name = \".*\"/name = \"$PUBLISHED_NAME\"/" pyproject.toml && rm -f pyproject.toml.tmp
  git add pyproject.toml && git commit -m "phase 15: pin pypi name to $PUBLISHED_NAME" || true
  python3 - <<PY
import json, pathlib
p = pathlib.Path(".s0-release.json"); s = json.loads(p.read_text())
s["pypi_package"] = "$PUBLISHED_NAME"
if "$PUBLISHED_NAME" != "system-zero":
    s["degraded"].append(f"phase-15: pypi published as $PUBLISHED_NAME (system-zero taken)")
p.write_text(json.dumps(s, indent=2))
PY
fi
```

Verify: if a name was published, `pipx install "$PUBLISHED_NAME==0.1.0" --force` produces a working `sz`. Otherwise BLOCKERS.md shows `pypi-deferred` and the git-install fallback remains usable.

### Step 15.6 — Update the brew formula sha256

```bash
SHA=$(curl -sSL https://files.pythonhosted.org/packages/source/s/system-zero/system_zero-0.1.0.tar.gz | shasum -a 256 | awk '{print $1}')
sed -i.bak "s/REPLACE_AFTER_PYPI_PUBLISH/$SHA/" ../homebrew-tap/Formula/system-zero.rb
( cd ../homebrew-tap && git add -A && git commit -qm "set sha256 for v0.1.0" && git push )
```

Verify: `brew install avibrahms/tap/system-zero` (on a Mac) installs and `sz --version` prints `0.1.0`.

### Step 15.7 — Publish to npm (with auto-rename cascade)

```bash
. ./.env
cd npm-wrapper

NPM_CANDIDATES=("system-zero" "systemzero" "sz-cli")
NPM_NAME=""

if [ -n "${NPM_TOKEN:-}" ]; then
  echo "//registry.npmjs.org/:_authToken=$NPM_TOKEN" > .npmrc
else
  : > .npmrc
fi

for NAME in "${NPM_CANDIDATES[@]}"; do
  cp package.json package.json.bak
  python3 - <<PY
import json, pathlib
p = pathlib.Path("package.json"); d = json.loads(p.read_text())
d["name"] = "$NAME"
p.write_text(json.dumps(d, indent=2) + "\n")
PY
  if npm publish --access public 2>&1 | tee /tmp/npm.log | grep -q "+ .*@0.1.0"; then
    NPM_NAME="$NAME"; rm -f package.json.bak; break
  fi
  mv package.json.bak package.json
  echo "npm: $NAME unavailable; trying next"
done
rm -f .npmrc
cd ..

if [ -z "$NPM_NAME" ]; then
  {
    echo ""
    echo "## $(date -u +%FT%TZ) · phase-15 · npm-deferred"
    echo ""
    echo "- **Category**: deferred"
    echo "- **What failed**: All npm candidate names unavailable"
    echo "- **Bypass applied**: npm install path deferred; pipx / curl / brew still work"
    echo "- **Downstream effect**: JS/TS users install via pipx"
    echo "- **Action to resolve**: free up the npm name or rotate the token"
    echo "- **Run command to retry only this bypass**: bash tooling/retry-npm.sh"
  } >> BLOCKERS.md
else
  python3 - <<PY
import json, pathlib
p = pathlib.Path(".s0-release.json"); s = json.loads(p.read_text())
s["npm_package"] = "$NPM_NAME"
if "$NPM_NAME" != "system-zero":
    s["degraded"].append(f"phase-15: npm published as $NPM_NAME")
p.write_text(json.dumps(s, indent=2))
PY
fi
```

Verify: `NPM_NAME=$(jq -r .npm_package .s0-release.json)` then `npm i -g "$NPM_NAME"` produces a working `sz`. If `NPM_NAME` is null, BLOCKERS.md records the deferral and the other channels remain primary.

### Step 15.8 — Confirm cloud apps healthy

```bash
FLY_CLOUD=$(jq -r '.fly_apps.cloud // "sz-cloud"' .s0-release.json)
FLY_WEB=$(jq -r '.fly_apps.web // "sz-web"' .s0-release.json)
API_ENDPOINT=$(jq -r '.endpoints.api' .s0-release.json)
WEB_ENDPOINT=$(jq -r '.endpoints.web' .s0-release.json)
fly status -a "$FLY_CLOUD"
fly status -a "$FLY_WEB"
curl -sSf "$API_ENDPOINT/v1/catalog/index" | jq '.items | length'
curl -sSf "$WEB_ENDPOINT/" | head -c 300
curl -sSf "$WEB_ENDPOINT/i" | head -n 5
```

Verify: catalog returns 7+ items, website returns the organism page, `/i` returns a script header.

### Step 15.9 — Confirm DNS

```bash
for d in systemzero.dev system0.dev api.systemzero.dev; do
  dig +short "$d" | head -n3
  curl -sSI "https://$d" | head -n1
done
```

Verify: every domain resolves; HTTPS returns a non-redirect 200 (or 301→TLS 200).

### Step 15.10 — Cut the GitHub release

```bash
gh release create v0.1.0 \
  dist/system_zero-0.1.0.tar.gz \
  dist/system_zero-0.1.0-py3-none-any.whl \
  install.sh \
  --title "System Zero v0.1.0" \
  --notes-file plan/PROTOCOL_SPEC.md
```

### Step 15.11 — Launch announcement

`launch/announce.md`:

```markdown
# System Zero — your repo, alive

I'm releasing System Zero today.

It's the smallest, host-agnostic, framework-agnostic protocol that gives any repository, in one click, autonomy + self-improvement + safe absorption of any open-source feature.

Two clicks for the visitor:
1. `pipx install system-zero` (or `npm i -g system-zero`, or `curl -sSL https://systemzero.dev/i | sh`)
2. `sz init`

What happens at step 2 — Repo Genesis: System Zero scans the repo, detects whether it has a heartbeat (Claude Code, Cursor, Hermes, OpenClaw, MetaClaw, connection-engine, custom), then either installs its own (Owned) or adopts the existing one (Adopted). It picks 3-5 self-improvement modules to install (immune, subconscious, dreaming, metabolism, endocrine, prediction, …), runs the reconcile cycle, and starts the heartbeat. The repo is alive.

When you absorb a feature from any GitHub repo (`sz absorb https://github.com/<x>`), the protocol's reconcile cycle re-wires every previously installed module to the newcomer. That's how features added today still talk to features added next month — the magic-board property.

The protocol is open-source forever. Cloud features (hosted catalog, Pro absorb, cloud backup, telemetry opt-in, team library) are $19/mo Pro, $49/seat Team. Stripe.

→ install: https://systemzero.dev
→ source: https://github.com/avibrahms/system-zero
→ catalog: https://github.com/avibrahms/catalog
→ spec: https://github.com/avibrahms/system-zero/blob/main/plan/PROTOCOL_SPEC.md

Apache 2.0. PRs welcome.
```

### Step 15.12 — Tag and close

```bash
git tag v0.1.0
git push --tags
```

## Acceptance criteria

Phase 15 reads `.s0-release.json` and `BLOCKERS.md` written by earlier phases and checks the **core-essentials green** invariant defined in Appendix A of `plan/EXECUTION_RULES.md`. All of these must hold for `overall_status = green` or `degraded` (either is launch-acceptable for v0.1.0-rc1):

1. `git log --oneline | head -25` shows the current-branch checkpoint history for every completed phase plus the v0.1.0 tag.
2. `pytest -q` and every e2e driver script pass on `main` (tests that themselves hit deferred services use the mocks).
3. `gh release view v0.1.0` shows the three assets attached.
4. `pipx install "$(jq -r .pypi_package .s0-release.json)==0.1.0"` on a fresh machine produces a working `sz` that can `sz init` a temp repo and run Repo Genesis end-to-end. (If `pypi_package` is `null`, the git-install fallback in `install.sh` is used instead.)
5. At least one install channel resolves end-to-end: pip, npm, curl, or brew. `null` values in `.s0-release.json` are acceptable as long as one channel works.
6. `$(jq -r .endpoints.web .s0-release.json)` returns the organism page; `$(jq -r .endpoints.api .s0-release.json)/v1/catalog/index` returns 7+ items. (These may be `.fly.dev` URLs if DNS was deferred — that still counts as green.)
7. If `billing.status == "live"` or `"test"`: a Stripe checkout completes end-to-end. If `billing.status == "deferred"`: the deferral is recorded in BLOCKERS.md and the website shows the "Billing setup pending" state. Both states are launch-acceptable.
8. `BLOCKERS.md` contains only rows from the soft-blocker table in Appendix A of `plan/EXECUTION_RULES.md`. Any row not matching a policy entry = run fails the acceptance bar; the operator resolves and re-runs phase 15.

If all 8 hold, set `.s0-release.json.overall_status` to `green` when `degraded` is empty, else `degraded`. Either value is launch-acceptable. `hard_blocked` is the only value that blocks launch.

## Failure modes and recovery

| Symptom | Cause | Action |
|---|---|---|
| `gh repo create` name taken | upstream conflict | use the auto-suffixed repo recorded in `.s0-release.json.github_repos`; update README links and re-run downstream steps |
| GitHub Pages 404 | not configured (we use Fly for the website here) | confirm CNAME at Hostinger; `fly certs check` |
| PyPI upload 403 | wrong token or scope | regenerate token at pypi.org with project scope |
| npm publish 403 | wrong token, missing 2FA on automation token | regenerate token with `Automation` type |
| Brew tap install fails | sha256 mismatch | re-run step 15.6; verify the URL points to the published tarball |
| Catalog 404 from raw.githubusercontent | repo not yet propagated | wait 1-5 min; otherwise ensure repo is public |
| Fly app cold start lag on first hit | acceptable | `min_machines_running = 1` is set in fly.toml; if not, edit and redeploy |

## Rollback

If something post-launch is broken:
- `gh release delete v0.1.0`
- `pip install` users keep working from the published wheel even if we yank later; they can `pip install system-zero==0.1.0`.
- `npm unpublish system-zero@0.1.0` only works within 72h.
- `fly destroy sz-cloud --yes; fly destroy sz-web --yes` (only as a last resort).

## After-launch follow-ups (not in v0.1)

- Catalog quality CI: every PR's module runs through the conformance bench.
- Module signing (sigstore) for v0.2.
- Web sliders that commit to `.sz.yaml` via OAuth.
- Vector-search provider plug-in for memory.
- Windows-native runtime.
- v0.1.1: real hosted-absorb implementation in cloud (currently a stub).
