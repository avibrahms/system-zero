const CATALOG_URL = "__SZ_API_ENDPOINT__/v1/catalog/index";

const state = {
  catalog: [],
  installed: [],            // [{id, setpoints}]
  hover: '',
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

function pushEvent(text) {
  const stream = $('#event-stream');
  const line = document.createElement('span');
  line.className = 'ev';
  line.textContent = text;
  stream.prepend(line);
  requestAnimationFrame(() => line.classList.add('dim'));
  while (stream.children.length > 10) stream.lastChild.remove();
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
    pushEvent(`bus > module.uninstalled {"module":"${id}"}`);
  } else {
    const it = state.catalog.find(c => c.id === id);
    if (!it) return;
    const setp = {};
    for (const [k, v] of Object.entries(it.setpoints || {})) setp[k] = v.default;
    state.installed.push({ id, setpoints: setp });
    organism.emit('module.installed.' + id);
    pushEvent(`bus > module.installed {"module":"${id}"}`);
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
  if (!state.installed.find(x => x.id === id)) toggleInstall(id);
});

document.getElementById('module-grid').addEventListener('dragover', (e) => e.preventDefault());
document.getElementById('module-grid').addEventListener('drop', (e) => {
  e.preventDefault();
  const id = e.dataTransfer.getData('text/plain');
  if (state.installed.find(x => x.id === id)) toggleInstall(id);
});

window.addEventListener('organism:hover', (e) => {
  state.hover = e.detail.id;
  if (!state.hover) return;
  const lines = [
    `bus < ${state.hover}.tick {"status":"alive"}`,
    `bus < ${state.hover}.health {"state":"green"}`,
    `bus < reconcile.bound {"module":"${state.hover}"}`,
  ];
  pushEvent(lines[Math.floor(Math.random() * lines.length)]);
});

// Periodic synthetic events to make the organism feel alive.
setInterval(() => {
  organism.emit('pulse.tick');
  if (state.hover) pushEvent(`bus < ${state.hover}.pulse {"ts":"now"}`);
}, 1500);

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
