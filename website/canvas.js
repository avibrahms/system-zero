// Living organism: a pulsing core + orbiting module nodes connected by lines.
// State is driven by app.js; we expose globals.
window.organism = (() => {
  const canvas = document.getElementById('organism');
  const ctx = canvas.getContext('2d');
  let W = 0, H = 0, dpr = 1;
  let modules = []; // [{id, theta, r, hue, installed}]
  let beat = 0;
  let lastT = 0;
  let hoverId = "";
  const nodePositions = new Map();

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

  function pointer(ev) {
    const rect = canvas.getBoundingClientRect();
    const px = ev.clientX - rect.left;
    const py = ev.clientY - rect.top;
    let next = "";
    for (const [id, pos] of nodePositions.entries()) {
      const dx = pos.x - px;
      const dy = pos.y - py;
      if (Math.sqrt(dx * dx + dy * dy) <= 28) {
        next = id;
        break;
      }
    }
    if (next !== hoverId) {
      hoverId = next;
      window.dispatchEvent(new CustomEvent('organism:hover', { detail: { id: hoverId } }));
    }
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
    nodePositions.clear();
    for (const m of modules) {
      m.theta += dt * 0.10;
      const x = cx + Math.cos(m.theta) * m.r;
      const y = cy + Math.sin(m.theta) * m.r;
      const r = 14 + Math.sin(beat * 2.0 + m.theta) * 2.5;
      nodePositions.set(m.id, { x, y });
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
      if (m.id === hoverId) {
        ctx.strokeStyle = 'rgba(227,238,243,0.85)';
        ctx.lineWidth = 1;
        ctx.beginPath(); ctx.arc(x, y, r + 7, 0, Math.PI * 2); ctx.stroke();
      }
    }
    requestAnimationFrame(frame);
  }

  window.addEventListener('resize', resize);
  canvas.addEventListener('pointermove', pointer);
  canvas.addEventListener('pointerleave', () => {
    hoverId = "";
    window.dispatchEvent(new CustomEvent('organism:hover', { detail: { id: "" } }));
  });
  resize();
  requestAnimationFrame(frame);

  return { set, emit };
})();
