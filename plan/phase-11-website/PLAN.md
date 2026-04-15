# Phase 11 — Website (the unique living-organism design)

## Goal

Build `systemzero.dev` and `system0.dev`. The site is **not a generic landing page**. It is a real-time visualization of the protocol — a living, breathing, plug-in-able organism that the user can manipulate in the browser. The visitor sees what System Zero IS, not what it claims to be.

## What the website is — three layers in one page

1. **The Living Organism (hero)**: a black canvas occupying the upper half of the viewport. A pulsing "core" with thin animated lines connecting to module nodes that orbit it. Each module node breathes (radius modulates with the heartbeat). When a node is hovered, its bus events scroll past it as ASCII text.

2. **The Plug Board (middle)**: a grid of all catalog modules represented as drag-able cards. Drag a card onto the organism to "install" it — a new node appears in the orbit and a connection animates into the core. Drag back off to "uninstall." This is *literally* what `sz install` and `sz uninstall` do.

3. **The Control Panel (lower)**: for each currently-staged module, render its setpoints as sliders / dropdowns. Edits update the generated install command in real time.

A sticky bar at the bottom shows: `sz install <ids> --set <overrides>` ready to copy. One button copies it. A second button reveals the `curl | sh` fallback.

There is **no carousel**, **no testimonial section**, **no email capture**, **no marketing puff**. Just the organism and the control panel. Pricing is a separate page.

## Why this design

- Most "developer tool" sites tell. This one **shows**.
- The metaphor of a living organism IS the product. The visitor experiences the protocol before installing.
- Drag-to-install in the browser maps 1:1 to the CLI behavior — when they paste the command, they already know what will happen.
- It is unique enough to be talked about. People share screenshots of organisms they assembled.

## Inputs

- Phases 00–10 complete.
- The Fly.io app is live serving `/v1/catalog/index`.
- Hostinger DNS for `systemzero.dev` and `system0.dev` is configured.
- A modern browser supporting Canvas 2D and the Web Animations API (no WebGL required for v0.1).

## Outputs

- `website/` — static site source.
- `website/index.html` — the organism page.
- `website/pricing.html` — pricing + Stripe checkout button.
- `website/install/index.html` — `/i` route returns `install.sh` (one line server-side rewrite).
- `website/style.css`.
- `website/app.js` — organism renderer + drag-and-drop + setpoint sliders.
- `website/canvas.js` — the canvas drawing routines.
- DNS configured via Hostinger (only): both `systemzero.dev` and `system0.dev` A/CNAME records point at the Fly.io `sz-web` app.
- `tests/website/test_render.py` — a Playwright-based smoke test that loads the page and asserts the organism is drawn.
- Branch `phase-11-website`.

## Atomic steps

### Step 11.1 — Branch + dirs

```bash
git checkout main
git checkout -b phase-11-website
mkdir -p website/install tests/website
```

### Step 11.2 — `website/index.html`

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>System Zero — your repo, alive</title>
<meta name="description" content="One-click autonomy and self-improvement for any repository. The protocol that lets every module integrate with every other module, even when added at different times.">
<link rel="stylesheet" href="style.css">
</head>
<body>

<header class="topbar">
  <span class="brand">system zero</span>
  <nav>
    <a href="/pricing.html">pricing</a>
    <a href="https://github.com/systemzero-dev/system-zero">github</a>
    <a href="https://github.com/systemzero-dev/system-zero/blob/main/plan/PROTOCOL_SPEC.md">spec</a>
  </nav>
</header>

<section class="organism">
  <canvas id="organism"></canvas>
  <div class="overlay">
    <h1>your repo, alive.</h1>
    <p>Drag a module onto the organism. Watch it connect.</p>
    <p>Then copy the command at the bottom.</p>
  </div>
  <div id="event-stream" aria-live="polite"></div>
</section>

<section class="board">
  <h2>plug-in modules</h2>
  <div id="module-grid">loading…</div>
</section>

<section class="control">
  <h2>setpoints</h2>
  <div id="setpoints-panel"><em>install a module above to tune it.</em></div>
</section>

<section class="install-bar" aria-label="install command">
  <code id="install-cmd">sz init</code>
  <button id="copy-btn">copy</button>
  <details>
    <summary>need install? (curl)</summary>
    <pre><code>curl -sSL https://systemzero.dev/i | sh</code></pre>
  </details>
</section>

<footer>
  <span>made with discipline. apache 2.0.</span>
  <span>spec v0.1.0 · catalog: <a id="catalog-status">checking…</a></span>
</footer>

<script src="canvas.js"></script>
<script src="app.js"></script>
</body>
</html>
```

### Step 11.3 — `website/style.css`

```css
:root {
  --bg: #04060b;
  --fg: #e3eef3;
  --dim: #8aa3b0;
  --accent: #21f1a3;
  --warn: #ff5e7e;
  --grid: rgba(255,255,255,0.06);
  font-family: ui-monospace, "JetBrains Mono", "SF Mono", Menlo, Consolas, monospace;
}
* { box-sizing: border-box; }
html, body { margin: 0; background: var(--bg); color: var(--fg); }
body { line-height: 1.45; min-height: 100vh; display: flex; flex-direction: column; }

.topbar { display: flex; justify-content: space-between; align-items: center; padding: 0.75rem 1rem; border-bottom: 1px solid var(--grid); }
.brand { font-weight: 700; letter-spacing: 0.05em; }
.topbar nav a { color: var(--dim); text-decoration: none; margin-left: 1rem; }
.topbar nav a:hover { color: var(--accent); }

.organism { position: relative; height: 60vh; min-height: 380px; border-bottom: 1px solid var(--grid); overflow: hidden; }
canvas#organism { position: absolute; inset: 0; width: 100%; height: 100%; }
.overlay { position: absolute; left: 1.5rem; top: 1.5rem; max-width: 28rem; }
.overlay h1 { font-size: 1.6rem; margin: 0 0 0.5rem; }
.overlay p { color: var(--dim); margin: 0.2rem 0; }
#event-stream { position: absolute; right: 1rem; bottom: 1rem; max-width: 36rem; max-height: 14rem; overflow: hidden;
                font-size: 0.78rem; color: var(--dim); white-space: pre; }
#event-stream .ev { display: block; opacity: 0.85; transform: translateY(0); transition: transform 6s linear, opacity 6s; }
#event-stream .ev.dim { opacity: 0; transform: translateY(-2rem); }

.board { padding: 1.25rem 1rem; }
.board h2 { font-size: 0.95rem; color: var(--dim); margin: 0 0 0.75rem; text-transform: lowercase; letter-spacing: 0.08em; }
#module-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 0.75rem; }
.card { border: 1px solid var(--grid); border-radius: 6px; padding: 0.75rem; cursor: grab; user-select: none;
        transition: border-color .15s, transform .15s; }
.card:hover { border-color: var(--accent); transform: translateY(-1px); }
.card[draggable="true"]:active { cursor: grabbing; }
.card .id { font-weight: 700; }
.card .desc { color: var(--dim); font-size: 0.85rem; }
.card.installed { border-color: var(--accent); background: rgba(33,241,163,0.06); }

.control { padding: 1.25rem 1rem; min-height: 12rem; border-top: 1px solid var(--grid); }
.control h2 { font-size: 0.95rem; color: var(--dim); margin: 0 0 0.75rem; text-transform: lowercase; letter-spacing: 0.08em; }
.setpoint-row { display: flex; gap: 0.75rem; align-items: center; padding: 0.25rem 0; }
.setpoint-row label { width: 14rem; color: var(--dim); }
.setpoint-row .val { color: var(--accent); min-width: 4rem; }
.setpoint-row input[type="range"] { flex: 1; accent-color: var(--accent); }

.install-bar { position: sticky; bottom: 0; background: rgba(4,6,11,0.92); backdrop-filter: blur(8px);
               border-top: 1px solid var(--grid); padding: 0.75rem 1rem; display: flex; gap: 0.75rem; align-items: center; }
.install-bar code { flex: 1; color: var(--fg); }
.install-bar button { background: var(--accent); color: var(--bg); border: 0; padding: 0.5rem 1rem; border-radius: 4px;
                      cursor: pointer; font-weight: 700; }
.install-bar button:hover { filter: brightness(1.1); }
.install-bar details { color: var(--dim); }
.install-bar details summary { cursor: pointer; }
.install-bar pre { margin: 0.4rem 0 0; }

footer { padding: 0.6rem 1rem; color: var(--dim); display: flex; justify-content: space-between; font-size: 0.8rem; border-top: 1px solid var(--grid); }
footer a { color: var(--dim); }
#catalog-status.ok { color: var(--accent); }
#catalog-status.fail { color: var(--warn); }
```

### Step 11.4 — `website/canvas.js` (the organism renderer)

```javascript
// Living organism: a pulsing core + orbiting module nodes connected by lines.
// State is driven by app.js; we expose globals.
window.organism = (() => {
  const canvas = document.getElementById('organism');
  const ctx = canvas.getContext('2d');
  let W = 0, H = 0, dpr = 1;
  let modules = []; // [{id, theta, r, hue, installed}]
  let beat = 0;
  let lastT = 0;

  function resize() {
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    W = canvas.clientWidth; H = canvas.clientHeight;
    canvas.width  = W * dpr;
    canvas.height = H * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  function set(installedIds) {
    // Lay installed modules around the core in a circle.
    const inst = installedIds.map((id, i, arr) => ({
      id, installed: true,
      theta: (i / arr.length) * Math.PI * 2,
      r: Math.min(W, H) * 0.32,
      hue: 150 + (i * 47) % 80,
    }));
    modules = inst;
  }

  function emit(evType) {
    // visual ripple along the line of the matching module if any
    const m = modules.find(m => evType.startsWith(m.id) || evType.includes(m.id));
    if (!m) return;
    m.ripple = 1.0;
  }

  function frame(t) {
    if (!lastT) lastT = t;
    const dt = (t - lastT) / 1000; lastT = t;
    beat += dt * 1.2;
    const cx = W / 2, cy = H / 2;
    ctx.clearRect(0, 0, W, H);

    // background grid
    ctx.strokeStyle = 'rgba(255,255,255,0.04)';
    ctx.lineWidth = 1;
    for (let x = 0; x < W; x += 32) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke(); }
    for (let y = 0; y < H; y += 32) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke(); }

    // core
    const coreR = 22 + Math.sin(beat * 2.0) * 4;
    const grad = ctx.createRadialGradient(cx, cy, 0, cx, cy, coreR * 3);
    grad.addColorStop(0, 'rgba(33,241,163,0.55)');
    grad.addColorStop(1, 'rgba(33,241,163,0)');
    ctx.fillStyle = grad;
    ctx.beginPath(); ctx.arc(cx, cy, coreR * 3, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = '#21f1a3';
    ctx.beginPath(); ctx.arc(cx, cy, coreR, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = '#04060b';
    ctx.font = 'bold 11px ui-monospace, monospace';
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.fillText('sz', cx, cy);

    // modules
    for (const m of modules) {
      m.theta += dt * 0.10;
      const x = cx + Math.cos(m.theta) * m.r;
      const y = cy + Math.sin(m.theta) * m.r;
      const r = 14 + Math.sin(beat * 2.0 + m.theta) * 2.5;
      // connection line
      ctx.strokeStyle = `hsla(${m.hue}, 60%, 60%, 0.30)`;
      ctx.lineWidth = 1.2;
      ctx.beginPath(); ctx.moveTo(cx, cy); ctx.lineTo(x, y); ctx.stroke();
      // ripple
      if (m.ripple && m.ripple > 0) {
        ctx.strokeStyle = `hsla(${m.hue}, 80%, 65%, ${m.ripple})`;
        ctx.lineWidth = 2;
        const t1 = 1 - m.ripple;
        const px = cx + (x - cx) * t1, py = cy + (y - cy) * t1;
        ctx.beginPath(); ctx.arc(px, py, 8, 0, Math.PI * 2); ctx.stroke();
        m.ripple -= dt * 1.5;
      }
      // node
      ctx.fillStyle = `hsl(${m.hue}, 70%, 55%)`;
      ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fill();
      ctx.fillStyle = '#04060b';
      ctx.font = '10px ui-monospace, monospace';
      ctx.fillText(m.id, x, y);
    }
    requestAnimationFrame(frame);
  }

  window.addEventListener('resize', resize);
  resize();
  requestAnimationFrame(frame);

  return { set, emit };
})();
```

### Step 11.5 — `website/app.js` (orchestration + catalog + drag-and-drop + sliders)

```javascript
const CATALOG_URL = "__SZ_API_ENDPOINT__/v1/catalog/index";

const state = {
  catalog: [],
  installed: [],            // [{id, setpoints}]
};

const $ = (s) => document.querySelector(s);

async function loadCatalog() {
  const status = $('#catalog-status');
  try {
    const r = await fetch(CATALOG_URL, { mode: 'cors' });
    state.catalog = (await r.json()).items;
    status.textContent = `${state.catalog.length} modules`;
    status.className = 'ok';
  } catch (e) {
    state.catalog = FALLBACK_CATALOG;
    status.textContent = 'fallback (offline)';
    status.className = 'fail';
  }
  renderGrid();
  renderInstallCmd();
}

function renderGrid() {
  const g = $('#module-grid');
  g.innerHTML = '';
  for (const it of state.catalog) {
    const card = document.createElement('div');
    card.className = 'card' + (state.installed.find(x => x.id === it.id) ? ' installed' : '');
    card.draggable = true;
    card.dataset.id = it.id;
    card.innerHTML = `<div class="id">${it.id}</div><div class="desc">${it.description}</div>`;
    card.addEventListener('dragstart', (e) => e.dataTransfer.setData('text/plain', it.id));
    card.addEventListener('click', () => toggleInstall(it.id));
    g.appendChild(card);
  }
}

function toggleInstall(id) {
  const cur = state.installed.find(x => x.id === id);
  if (cur) {
    state.installed = state.installed.filter(x => x.id !== id);
    organism.emit('module.uninstalled');
  } else {
    const it = state.catalog.find(c => c.id === id);
    if (!it) return;
    const setp = {};
    for (const [k, v] of Object.entries(it.setpoints || {})) setp[k] = v.default;
    state.installed.push({ id, setpoints: setp });
    organism.emit('module.installed.' + id);
  }
  organism.set(state.installed.map(x => x.id));
  renderGrid();
  renderSetpoints();
  renderInstallCmd();
}

function renderSetpoints() {
  const p = $('#setpoints-panel');
  p.innerHTML = '';
  if (state.installed.length === 0) {
    p.innerHTML = '<em>install a module above to tune it.</em>';
    return;
  }
  for (const inst of state.installed) {
    const it = state.catalog.find(c => c.id === inst.id);
    if (!it) continue;
    const head = document.createElement('div');
    head.innerHTML = `<strong>${inst.id}</strong>`;
    p.appendChild(head);
    for (const [name, def] of Object.entries(it.setpoints || {})) {
      const row = document.createElement('div'); row.className = 'setpoint-row';
      const label = document.createElement('label'); label.textContent = name; label.title = def.description || '';
      const valEl = document.createElement('span'); valEl.className = 'val';
      let input;
      if (def.enum) {
        input = document.createElement('select');
        for (const v of def.enum) {
          const o = document.createElement('option'); o.value = v; o.textContent = v;
          if (String(v) === String(inst.setpoints[name])) o.selected = true;
          input.appendChild(o);
        }
        input.addEventListener('change', () => { inst.setpoints[name] = input.value; valEl.textContent = input.value; renderInstallCmd(); });
        valEl.textContent = inst.setpoints[name];
      } else {
        input = document.createElement('input'); input.type = 'range';
        input.min = def.range[0]; input.max = def.range[1]; input.value = inst.setpoints[name];
        input.addEventListener('input', () => { inst.setpoints[name] = +input.value; valEl.textContent = input.value; renderInstallCmd(); });
        valEl.textContent = inst.setpoints[name];
      }
      row.append(label, input, valEl);
      p.appendChild(row);
    }
  }
}

function renderInstallCmd() {
  const ids = state.installed.map(x => x.id);
  const sets = [];
  for (const inst of state.installed) {
    for (const [k, v] of Object.entries(inst.setpoints)) sets.push(`--set ${inst.id}.${k}=${v}`);
  }
  const cmd = ids.length === 0
    ? 'sz init'
    : `sz init && sz install ${ids.join(' ')}${sets.length ? ' ' + sets.join(' ') : ''}`;
  $('#install-cmd').textContent = cmd;
}

$('#copy-btn').addEventListener('click', () => navigator.clipboard.writeText($('#install-cmd').textContent));

// Make the organism canvas accept drops.
const canvas = document.getElementById('organism');
canvas.addEventListener('dragover', (e) => e.preventDefault());
canvas.addEventListener('drop', (e) => {
  e.preventDefault();
  const id = e.dataTransfer.getData('text/plain');
  toggleInstall(id);
});

// Periodic synthetic events to make the organism feel alive.
setInterval(() => organism.emit('pulse.tick'), 1500);

const FALLBACK_CATALOG = [
  {id:"heartbeat",   description:"periodic pulse; required for static repos", setpoints:{}},
  {id:"immune",      description:"passive anomaly detector",                  setpoints:{severity_threshold:{enum:["low","medium","high"], default:"medium"}}},
  {id:"subconscious",description:"anomaly aggregator → red/amber/green",       setpoints:{red_threshold:{range:[1,100], default:5}}},
  {id:"dreaming",    description:"hypothesis generator (cron 3am)",            setpoints:{novelty_threshold:{range:[0,1], default:0.7}}},
  {id:"metabolism",  description:"rotates the bus log",                        setpoints:{rotate_after_mb:{range:[1,1024], default:50}}},
  {id:"endocrine",   description:"modulates other modules' setpoints",         setpoints:{}},
  {id:"prediction",  description:"predicts the next likely event",             setpoints:{top_k:{range:[1,20], default:3}}},
];

loadCatalog();
```

### Step 11.6 — `website/install/index.html` (the curl bootstrap)

This file *is* the install.sh content served at `/i`. We serve it from `sz-cloud` on Fly.io (see phase-10 step 10 amendment, which adds the `/i` route). The website redirects `/i` to the API endpoint recorded in `.s0-release.json`, so both the website host and the API host return the install script with `Content-Type: text/x-shellscript`.

For Fly.io static + a tiny FastAPI route, simplest: add a `/i` route to the cloud app from phase 10 that returns the contents of `install.sh` with shell content-type. Add this in step 11.10.

### Step 11.7 — `website/pricing.html`

```html
<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Pricing — System Zero</title>
<link rel="stylesheet" href="style.css">
</head><body>
<header class="topbar"><span class="brand">system zero</span>
<nav><a href="/">home</a><a href="https://github.com/systemzero-dev/system-zero">github</a></nav></header>
<section style="padding: 2rem 1rem; max-width: 56rem; margin: 0 auto;">
<h1>pricing</h1>
<p style="color: var(--dim);">The protocol is open-source and free forever. Pro and Team pay for hosted intelligence — we aggregate anonymous signals across installations and redistribute them back to every user (including Free) through better Genesis recommendations, catalog rankings, and <code>sz insights</code>.</p>
<div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 1rem; margin-top: 1.5rem;">
  <div class="card"><div class="id">free</div><div class="desc">protocol + CLI + every public module + local-only. Forever. Reads community insights; never transmits.</div><br><strong>$0</strong></div>
  <div class="card"><div class="id">pro · $19/mo</div><div class="desc">hosted catalog dashboard, private modules, cloud absorb (we host the LLM call), cloud backup of .sz/, telemetry opt-in (you help train the recommender, you see your own aggregates).</div><br>
    <button data-tier="pro" class="upgrade-btn">upgrade</button></div>
  <div class="card"><div class="id">team · $49/seat</div><div class="desc">pro + shared module library across teammates, audit log, team-private insights, SSO via Clerk (Google/Microsoft).</div><br>
    <button data-tier="team" class="upgrade-btn">upgrade</button></div>
</div>
<p style="color: var(--dim); margin-top: 1.5rem;">Pricing is interim; the moat is the network of anonymous telemetry plus the redistribution pipeline, not the price tag.</p>
</section>

<!-- Clerk widget. The website uses Clerk for authentication before calling /v1/billing/checkout. -->
<script async crossorigin src="https://cdn.jsdelivr.net/npm/@clerk/clerk-js@5/dist/clerk.browser.js"
        data-clerk-publishable-key="__NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY__"
        onload="initClerk()"></script>
<script>
const API_ENDPOINT = "__SZ_API_ENDPOINT__";

async function initClerk() {
  await window.Clerk.load();
  document.querySelectorAll('.upgrade-btn').forEach(btn => {
    btn.addEventListener('click', () => upgrade(btn.dataset.tier));
  });
}

async function upgrade(tier) {
  if (!window.Clerk.user) {
    window.Clerk.openSignIn({
      afterSignInUrl: location.pathname + "?upgrade=" + tier,
      afterSignUpUrl: location.pathname + "?upgrade=" + tier,
    });
    return;
  }
  const token = await window.Clerk.session.getToken();
  const r = await fetch(`${API_ENDPOINT}/v1/billing/checkout`, {
    method: "POST",
    headers: {"content-type":"application/json", "authorization":"Bearer " + token},
    body: JSON.stringify({tier,
      success_url: location.origin + "/welcome",
      cancel_url:  location.origin + "/pricing.html"})
  });
  const data = await r.json();
  location.href = data.url;
}

// Auto-resume checkout if returning from Clerk sign-in with ?upgrade=<tier>
const q = new URLSearchParams(location.search);
if (q.get("upgrade")) {
  const waitForClerk = setInterval(() => {
    if (window.Clerk && window.Clerk.user) {
      clearInterval(waitForClerk);
      upgrade(q.get("upgrade"));
    }
  }, 100);
}
</script></body></html>
```

### Step 11.8 — Deploy the website

The only hosting platform is Fly.io. No alternatives. A second Fly app `sz-web` serves `website/` with Caddy. DNS (Hostinger only) points `systemzero.dev` and `system0.dev` at the Fly app.

`website/Dockerfile`:
```dockerfile
FROM caddy:2-alpine AS build
COPY . /src
# Substitute build-time placeholders BEFORE baking the image.
ARG NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY
ARG NEXT_PUBLIC_SUPABASE_URL
ARG NEXT_PUBLIC_SUPABASE_ANON_KEY
ARG NEXT_PUBLIC_POSTHOG_KEY
ARG SZ_API_ENDPOINT
RUN if [ -z "$NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY" ]; then echo "missing NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY build arg" >&2; exit 1; fi
RUN if [ -z "$SZ_API_ENDPOINT" ]; then echo "missing SZ_API_ENDPOINT build arg" >&2; exit 1; fi
RUN for f in /src/*.html /src/pricing.html /src/index.html /src/Caddyfile; do \
      [ -f "$f" ] && \
        sed -i \
          -e "s|__NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY__|${NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY}|g" \
          -e "s|__NEXT_PUBLIC_SUPABASE_URL__|${NEXT_PUBLIC_SUPABASE_URL}|g" \
          -e "s|__NEXT_PUBLIC_SUPABASE_ANON_KEY__|${NEXT_PUBLIC_SUPABASE_ANON_KEY}|g" \
          -e "s|__NEXT_PUBLIC_POSTHOG_KEY__|${NEXT_PUBLIC_POSTHOG_KEY:-}|g" \
          -e "s|__SZ_API_ENDPOINT__|${SZ_API_ENDPOINT}|g" \
          "$f"; \
    done

FROM caddy:2-alpine
COPY --from=build /src /srv
COPY --from=build /src/Caddyfile /etc/caddy/Caddyfile
EXPOSE 80
```

`website/Caddyfile`:
```caddy
:80 {
  root * /srv
  encode gzip
  redir /i __SZ_API_ENDPOINT__/i 302
  file_server
  @noext { not path /*.* }
  rewrite @noext {path}.html
}
```

`website/fly.toml`:
```toml
app = "sz-web"
primary_region = "iad"
[build]
[http_service]
  internal_port = 80
  force_https = true
  auto_stop_machines = true
  auto_start_machines = true
  min_machines_running = 1
```

Deploy — pass the public keys as build args so they end up in the shipped HTML:
```bash
cd /Users/avi/Documents/Projects/system0-natural/website
. ../.env

# Auto-rename on Fly name collision (per Appendix A in plan/EXECUTION_RULES.md).
WEB_APP="sz-web"
for i in "" -2 -3 -4 -5 -6 -7 -8 -9; do
  candidate="sz-web$i"
  if fly apps create "$candidate" --org personal >/dev/null 2>&1 \
     || fly status -a "$candidate" >/dev/null 2>&1; then
    WEB_APP="$candidate"; break
  fi
done
echo "fly web app: $WEB_APP"
sed -i.bak "s/^app = \".*\"/app = \"$WEB_APP\"/" fly.toml
rm -f fly.toml.bak

fly deploy -a "$WEB_APP" \
  --build-arg NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY="$NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY" \
  --build-arg NEXT_PUBLIC_SUPABASE_URL="$NEXT_PUBLIC_SUPABASE_URL" \
  --build-arg NEXT_PUBLIC_SUPABASE_ANON_KEY="$NEXT_PUBLIC_SUPABASE_ANON_KEY" \
  --build-arg NEXT_PUBLIC_POSTHOG_KEY="${NEXT_PUBLIC_POSTHOG_KEY:-}" \
  --build-arg SZ_API_ENDPOINT="$(jq -r '.endpoints.api // "https://api.systemzero.dev"' ../.s0-release.json)"
fly status -a "$WEB_APP"

python3 - <<PY
import json, pathlib
p = pathlib.Path("../.s0-release.json"); s = json.loads(p.read_text())
s.setdefault("fly_apps", {})["web"] = "$WEB_APP"
if "$WEB_APP" != "sz-web":
    s["degraded"].append("phase-11: fly web app auto-renamed to $WEB_APP")
p.write_text(json.dumps(s, indent=2))
PY
```

Verify the placeholder was replaced:
```bash
WEB_APP=$(jq -r '.fly_apps.web // "sz-web"' ../.s0-release.json)
curl -sSf "https://$WEB_APP.fly.dev/pricing.html" | grep -c "__NEXT_PUBLIC_" | grep -q "^0$" \
  && echo "placeholders resolved" \
  || echo "placeholder still present — build args missing"
```

### Step 11.9 — DNS for the apex domains via Hostinger (only)

Reuse the `hostinger_endpoint` discovered in phase 00. No Cloudflare, no other provider.

```bash
. ./.env
ENDPOINT=$(jq -r '.hostinger_endpoint' .tooling-report.json)
if [ -z "$ENDPOINT" ] || [ "$ENDPOINT" = "null" ]; then
  # SOFT bypass per EXECUTION_RULES.md Appendix A — no DNS endpoint means skip apex DNS; continue on .fly.dev.
  WEB_APP_FALLBACK=$(jq -r '.fly_apps.web // "sz-web"' ../.s0-release.json)
  echo "no hostinger_endpoint; apex DNS deferred for all target zones"
  {
    echo ""
    echo "## $(date -u +%FT%TZ) · phase-11 · apex-dns-deferred-all"
    echo ""
    echo "- **Category**: deferred"
    echo "- **What failed**: .s0-release.json.hostinger_endpoint is empty; phase 00 could not validate a Hostinger DNS surface"
    echo "- **Bypass applied**: apex DNS skipped for all zones; site stays on $WEB_APP_FALLBACK.fly.dev"
    echo "- **Downstream effect**: users reach the website via https://$WEB_APP_FALLBACK.fly.dev"
    echo "- **Action to resolve**: rotate Hostinger token, re-run phase 00's endpoint check, then bash tooling/retry-dns.sh"
    echo "- **Run command to retry only this bypass**: bash tooling/retry-dns.sh all apex"
  } >> ../BLOCKERS.md
  python3 - <<PY
import json, pathlib
p = pathlib.Path("../.s0-release.json"); s = json.loads(p.read_text())
s["endpoints"]["web"] = "https://$WEB_APP_FALLBACK.fly.dev"
s["endpoints"]["alias_web"] = "(deferred)"
s["degraded"].append("phase-11: apex dns deferred for all zones (no hostinger endpoint)")
p.write_text(json.dumps(s, indent=2))
PY
  # Skip the DNS loop entirely.
  exit 0
fi

# Allocate a DEDICATED v4 IP on Fly so the apex A records remain stable.
# Shared IPs rotate; an apex A record pointing at a rotating IP breaks.
cd cloud || cd ../cloud 2>/dev/null || true
cd /Users/avi/Documents/Projects/system0-natural/website
WEB_APP=$(jq -r '.fly_apps.web // "sz-web"' ../.s0-release.json)
fly ips list -a "$WEB_APP" | grep -q v4 || fly ips allocate-v4 --region iad -a "$WEB_APP"
IP=$(fly ips list -a "$WEB_APP" --json | jq -r '[.[] | select(.Type=="v4")] [0].Address // empty')
[ -z "$IP" ] && { echo "could not allocate dedicated v4 IP for $WEB_APP"; exit 3; }

for DOMAIN in systemzero.dev system0.dev; do
  ZONE_ID=$(curl -sS -H "Authorization: Bearer $HOSTINGER_API_TOKEN" \
    "$ENDPOINT/zones?name=$DOMAIN" | jq -r '(.data // .zones // .result // [])[0].id // empty')

  if [ -z "$ZONE_ID" ]; then
    # SOFT blocker: skip apex DNS for this zone; web stays on .fly.dev hostname.
    echo "zone $DOMAIN not visible → apex DNS deferred for $DOMAIN"
    {
      echo ""
      echo "## $(date -u +%FT%TZ) · phase-11 · apex-dns-deferred"
      echo ""
      echo "- **Category**: deferred"
      echo "- **What failed**: Hostinger zone lookup for apex of $DOMAIN returned empty"
      echo "- **Bypass applied**: Hostinger-zone-not-visible — apex A-record not provisioned; site stays on $WEB_APP.fly.dev"
      echo "- **Downstream effect**: Visitors use https://$WEB_APP.fly.dev instead of https://$DOMAIN"
      echo "- **Action to resolve**: rotate token with DNS-write scope for $DOMAIN"
      echo "- **Run command to retry only this bypass**: bash ../tooling/retry-dns.sh $DOMAIN @"
    } >> ../BLOCKERS.md
    python3 - <<PY
import json, pathlib
p = pathlib.Path("../.s0-release.json"); s = json.loads(p.read_text())
key = "web" if "$DOMAIN" == "systemzero.dev" else "alias_web"
s["endpoints"][key] = "https://$WEB_APP.fly.dev"
s["degraded"].append("phase-11: apex $DOMAIN deferred")
p.write_text(json.dumps(s, indent=2))
PY
    continue
  fi

  # Idempotent upsert.
  EXISTING=$(curl -sS -H "Authorization: Bearer $HOSTINGER_API_TOKEN" \
    "$ENDPOINT/zones/$ZONE_ID/records?name=@&type=A" | jq -r '(.data // .records // .result // [])[0].id // empty')

  if [ -z "$EXISTING" ]; then
    curl -sS -X POST -H "Authorization: Bearer $HOSTINGER_API_TOKEN" \
      -H "Content-Type: application/json" \
      "$ENDPOINT/zones/$ZONE_ID/records" \
      -d "{\"name\":\"@\",\"type\":\"A\",\"value\":\"$IP\",\"ttl\":300}"
  else
    curl -sS -X PUT -H "Authorization: Bearer $HOSTINGER_API_TOKEN" \
      -H "Content-Type: application/json" \
      "$ENDPOINT/zones/$ZONE_ID/records/$EXISTING" \
      -d "{\"name\":\"@\",\"type\":\"A\",\"value\":\"$IP\",\"ttl\":300}"
  fi
done
```

Then in Fly:
```bash
cd website
fly certs add systemzero.dev
fly certs add system0.dev
fly certs check systemzero.dev
fly certs check system0.dev
```

If Hostinger's DNS API surface differs from the body-shape variants the script tolerates, the apex DNS is soft-skipped per EXECUTION_RULES.md Appendix A: the deferral is annotated to `BLOCKERS.md`, the website continues to serve on `sz-web.fly.dev`, and the operator can pin the correct body shape + run `tooling/retry-dns.sh` in the morning. Never switch DNS providers.

### Step 11.10 — Add `/i` route to the cloud app (phase 10 amendment)

In `cloud/app/main.py`, add:
```python
@app.get("/i")
def install_script():
    p = Path(__file__).resolve().parents[2] / "install.sh"
    return Response(content=p.read_text(), media_type="text/x-shellscript")
```

Redeploy: `cd cloud && fly deploy`.

Then add a simple Caddy redirect from `/i` on sz-web → the exact API endpoint recorded in `.s0-release.json` (this may be `https://api.systemzero.dev/i` or `https://sz-cloud*.fly.dev/i` if DNS was deferred):

`website/Caddyfile` (amended; the same `__SZ_API_ENDPOINT__` placeholder is substituted during the website build):
```caddy
:80 {
  root * /srv
  encode gzip
  redir /i __SZ_API_ENDPOINT__/i 302
  file_server
  @noext { not path /*.* }
  rewrite @noext {path}.html
}
```

Re-deploy sz-web.

### Step 11.11 — Smoke test

`tests/website/test_render.py` (Playwright):
```python
import os, pytest
playwright = pytest.importorskip("playwright.sync_api")


def test_organism_renders():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page()
        page.goto("https://systemzero.dev")
        # canvas exists and has non-zero size
        canvas = page.query_selector("#organism")
        assert canvas is not None
        bbox = canvas.bounding_box()
        assert bbox["width"] > 100 and bbox["height"] > 100
        # at least one module card renders (after catalog fetch or fallback)
        page.wait_for_selector(".card", timeout=10000)
        cards = page.query_selector_all(".card")
        assert len(cards) >= 5
        b.close()
```

If Playwright is not installed in the environment, skip — but document the manual smoke: visit `https://systemzero.dev`, see the organism, drag a card onto it, watch the install command update.

### Step 11.12 — Commit

```bash
git add website cloud/app/main.py tests/website plan/phase-11-website
git commit -m "phase 11: living-organism website complete"
```

## Acceptance criteria

1. `$(jq -r '.endpoints.web' .s0-release.json)` returns the organism page and renders the canvas + module cards.
2. If `.s0-release.json.endpoints.alias_web` is a URL, it resolves to the same site; if it is `(deferred)`, the deferral is recorded in `BLOCKERS.md`.
3. Dragging a module card onto the organism produces a node and updates the install command at the bottom.
4. The pricing page checkout produces a Stripe redirect.
5. `$(jq -r '.endpoints.web' .s0-release.json)/i` returns a working `install.sh`.
6. Playwright test (when available) passes.

## Failure modes and recovery

| Symptom | Cause | Action |
|---|---|---|
| CORS error fetching catalog | API not setting headers | add `Access-Control-Allow-Origin: *` to the catalog endpoints in cloud/app/main.py |
| Canvas blank on Safari | dpr handling | confirm `setTransform(dpr,...)` in resize |
| Hostinger DNS API differs | account tier | manually configure A records in UI |
| Fly cert pending | DNS not propagated | wait, then `fly certs check` |
| Drop event ignored on Firefox | `dragover` preventDefault missing somewhere | confirm both `dragover` and `drop` on canvas |

## Rollback

`fly destroy sz-web --yes; git checkout main && git branch -D phase-11-website`. (Keep the API up.)
