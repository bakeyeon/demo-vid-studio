// Renders the 1080p Cyberpunk Desktop stage graphics as PNGs for the AlphaEvolve Plugin demo.
import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';

const TARGET_DIR = 'examples/alphaevolve_demo';
const OUT = path.join(TARGET_DIR, 'build');
fs.mkdirSync(OUT, { recursive: true });

const events = JSON.parse(fs.readFileSync(path.join(TARGET_DIR, 'raw', 'events.json'), 'utf8'));
const script = JSON.parse(fs.readFileSync(path.join(TARGET_DIR, 'script.json'), 'utf8'));
const DUR = JSON.parse(fs.readFileSync(path.join(TARGET_DIR, 'voice', 'durations.json'), 'utf8'));
const END = events.at(-1).t;

export const L = {
  W: 1920, H: 1080,
  layout: 'desktop',
  screen:  { x: 64,   y: 124, w: 1120, h: 700 }, // 1280x800 scaled
  bezel:   14,
  card:    { x: 1236, y: 124, w: 620,  h: 700 },
  zoom:    { x: 34,   y: 92,  w: 552,  h: 345 }, // inside the card
  caption: { x: 360,  y: 874, w: 1200 },
  brand:   { x: 64,   y: 36 },
};

const LOGO_SVG = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128" width="100%" height="100%" fill="none">
  <defs>
    <linearGradient id="ae-grad-1" x1="16" y1="16" x2="112" y2="112" gradientUnits="userSpaceOnUse">
      <stop offset="0%" stop-color="#22d3ee"/>
      <stop offset="50%" stop-color="#f43f5e"/>
      <stop offset="100%" stop-color="#d946ef"/>
    </linearGradient>
    <linearGradient id="ae-grad-2" x1="112" y1="16" x2="16" y2="112" gradientUnits="userSpaceOnUse">
      <stop offset="0%" stop-color="#67e8f9"/>
      <stop offset="100%" stop-color="#4ade80"/>
    </linearGradient>
  </defs>
  <path d="M32 36L16 64L32 92" stroke="url(#ae-grad-1)" stroke-width="8" stroke-linecap="round" stroke-linejoin="round"/>
  <path d="M96 36L112 64L96 92" stroke="url(#ae-grad-1)" stroke-width="8" stroke-linecap="round" stroke-linejoin="round"/>
  <path d="M44 26C44 50 84 50 84 64C84 78 44 78 44 102" stroke="url(#ae-grad-1)" stroke-width="7" stroke-linecap="round"/>
  <path d="M84 26C84 50 44 50 44 64C44 78 84 78 84 102" stroke="url(#ae-grad-2)" stroke-width="7" stroke-linecap="round"/>
  <line x1="50" y1="36" x2="78" y2="36" stroke="#67e8f9" stroke-width="4.5" stroke-linecap="round"/>
  <line x1="52" y1="64" x2="76" y2="64" stroke="#4ade80" stroke-width="4.5" stroke-linecap="round"/>
  <line x1="50" y1="92" x2="78" y2="92" stroke="#f0abfc" stroke-width="4.5" stroke-linecap="round"/>
  <circle cx="44" cy="26" r="5.5" fill="#22d3ee"/>
  <circle cx="84" cy="26" r="5.5" fill="#67e8f9"/>
  <circle cx="44" cy="102" r="5.5" fill="#4ade80"/>
  <circle cx="84" cy="102" r="5.5" fill="#d946ef"/>
</svg>`;

const CSS = `
  @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@600;800&family=Rajdhani:wght@500;600;700&family=JetBrains+Mono:wght@500;700&display=swap');
  * { box-sizing: border-box; margin: 0; }
  body { font-family: 'Rajdhani', sans-serif; color: #f8fafc; background: transparent; }
  .heading { font-family: 'Orbitron', sans-serif; }
  .grad { background: linear-gradient(90deg, #22d3ee, #f43f5e, #d946ef); -webkit-background-clip: text; background-clip: text; color: transparent; }
  .card {
    width: ${L.card.w}px; height: ${L.card.h}px; padding: 34px 36px; position: relative;
    border-radius: 18px; background: rgba(8,11,22,.90); border: 2px solid #06b6d4;
    box-shadow: 0 0 36px rgba(6,182,212,.30), inset 0 0 22px rgba(217,70,239,.14);
  }
  .chip {
    display: inline-block; padding: 6px 16px; border-radius: 6px;
    font: 700 18px 'Rajdhani', sans-serif; letter-spacing: .04em;
    color: #22d3ee; background: rgba(6,182,212,.16); border: 1.5px solid #22d3ee;
    box-shadow: 0 0 12px rgba(6,182,212,.35);
  }
  .chip.pink { color: #f0abfc; background: rgba(217,70,239,.16); border-color: #d946ef; box-shadow: 0 0 12px rgba(217,70,239,.35); }
  h2 { font: 800 32px/1.22 'Orbitron', sans-serif; letter-spacing: .01em; margin: 18px 0 14px; color: #f8fafc; }
  p { font-size: 23px; line-height: 1.44; color: #a5f3fc; font-weight: 500; }
  .row { display: flex; align-items: center; gap: 14px; font-size: 21px; color: #e2e8f0; margin: 14px 0; font-weight: 600; }
  .ico { width: 42px; height: 42px; border-radius: 10px; display: grid; place-items: center; background: rgba(6,182,212,.18); border: 1px solid #06b6d4; font-size: 20px; flex: none; }
  .slot {
    position: absolute; left: ${L.zoom.x}px; top: ${L.zoom.y}px; width: ${L.zoom.w}px; height: ${L.zoom.h}px;
    border-radius: 14px; border: 2px solid #f43f5e;
    box-shadow: 0 0 24px rgba(244,63,94,.40); background: transparent;
  }
  .side { position: absolute; left: 34px; right: 34px; top: ${L.zoom.y + L.zoom.h + 22}px; }
  code { font: 600 19px 'JetBrains Mono', monospace; background: rgba(15,23,42,.95); color: #4ade80; border: 1px solid rgba(74,222,128,.4); padding: 3px 9px; border-radius: 6px; }
  .cap {
    width: ${L.caption.w}px; padding: 18px 28px; border-radius: 12px;
    background: rgba(8,11,22,.94); color: #f0abfc; border: 2px solid #d946ef;
    font: 700 26px/1.35 'Rajdhani', sans-serif; letter-spacing: .02em; text-align: center;
    box-shadow: 0 0 28px rgba(217,70,239,.40);
  }
`;

const cards = {
  intro: () => `<div class="card">
      <div style="display:flex;align-items:center;gap:18px;margin-top:16px">
        <div style="width:84px;height:84px;flex:none">${LOGO_SVG}</div>
        <div class="heading" style="font-size:40px;line-height:1.08">
          <span class="grad" style="font-weight:800">ALPHA</span><br/>
          <span style="color:#e2e8f0;font-weight:600">EVOLVE</span>
        </div>
      </div>
      <p style="margin-top:28px;font-size:26px;color:#fff"><b>Evolutionary Algorithm Discovery for Coding Agents</b></p>
      <p style="margin-top:14px">Inspired by Google DeepMind's AlphaEvolve &amp; OpenEvolve. Mutates code inside <code># EVOLVE-BLOCK</code> and climbs a deterministic fitness landscape.</p>
      <div style="margin-top:28px;display:flex;flex-wrap:wrap;gap:10px">
        <span class="chip">Claude Code</span>
        <span class="chip">Antigravity</span>
        <span class="chip pink">MAP-Elites</span>
      </div>
    </div>`,
  baseline: () => `<div class="card">
      <span class="chip">STEP 1 // BASELINE ORACLE</span>
      <h2>Deterministic Scoring</h2>
      <p>Before evolving, <code>evaluator.py</code> verifies the L1 baseline against a trusted reference oracle across 45 seeded instances.</p>
      <div style="margin-top:24px">
        <div class="row"><span class="ico">🎯</span><span><b>gen_000</b>: L1 Greedy Baseline (<code>0.724</code>)</span></div>
        <div class="row"><span class="ico">⏱️</span><span><b>Subprocess Timeout</b>: Stops infinite loops</span></div>
        <div class="row"><span class="ico">🔒</span><span><b>Deterministic</b>: Runtime logged separately</span></div>
      </div>
    </div>`,
  loop: () => `<div class="card">
      <span class="chip pink">STEP 2 // MODE A: ZERO-KEY LOOP</span>
      <h2>Agent-Driven Mutations</h2>
      <p>The agent samples top parents (<b>Exploit</b> + <b>Explore</b>), writes a single algorithmic hypothesis, and evaluates the child.</p>
      <div style="margin-top:22px">
        <div class="row"><span class="ico">1️⃣</span><span><b>gen_001</b>: Value/Weight Ratio → <code>0.865</code></span></div>
        <div class="row"><span class="ico">2️⃣</span><span><b>gen_002</b>: 2-Opt Local Swap → <code>0.942</code></span></div>
        <div class="row"><span class="ico">★</span><span><b>gen_003</b>: Exact 1D DP → <code>1.000</code></span></div>
      </div>
    </div>`,
  'map-zoom': () => `<div class="card">
      <span class="chip pink">LIVE 2× ZOOM // ARCHIVE.JSON</span>
      <div class="slot"></div>
      <div class="side">
        <div class="row"><span class="ico">📈</span><span><b>Fitness Curve</b>: <code>0.724</code> → <code>1.000</code></span></div>
        <div class="row"><span class="ico">🧬</span><span><b>Full Lineage</b>: Parent ID, rationale &amp; delta</span></div>
        <div class="row"><span class="ico">🏆</span><span><b>Auto-Save</b>: Updates <code>best_program.py</code></span></div>
      </div>
    </div>`,
  guardrails: () => `<div class="card">
      <span class="chip">STEP 3 // EVALUATOR GUARDRAILS</span>
      <h2>Anti-Overfit &amp; Privacy</h2>
      <p>Strict verification rules prevent reward hacking, lookup-table memorization, and sensitive data leaks.</p>
      <div style="margin-top:22px">
        <div class="row"><span class="ico">🧪</span><span><code>--held-out</code>: Unseen verification split</span></div>
        <div class="row"><span class="ico">📏</span><span><code>MAX_CODE_CHARS</code>: Blocks hardcoded answers</span></div>
        <div class="row"><span class="ico">🛡️</span><span><code>BLIND_MODE = True</code>: Zero raw data in context</span></div>
      </div>
    </div>`,
  outro: () => `<div class="card">
      <div style="display:flex;align-items:center;gap:16px;margin-top:16px">
        <div style="width:70px;height:70px;flex:none">${LOGO_SVG}</div>
        <div class="heading" style="font-size:34px">
          <span class="grad" style="font-weight:800">ALPHAEVOLVE</span>
        </div>
      </div>
      <p style="margin-top:26px"><code>github.com/bakeyeon/alphaevolve-plugin</code></p>
      <p style="margin-top:22px"><b>Mode A</b>: Agent-driven loop (Zero extra API key)<br/><b>Mode B</b>: Autonomous OpenEvolve CLI integration</p>
      <div style="margin-top:28px;display:flex;gap:10px">
        <span class="chip">Shot with demo-vid-studio</span>
        <span class="chip pink">cyberpunk preset</span>
      </div>
    </div>`,
};

const launchBrowser = async () => {
  try {
    return await chromium.launch();
  } catch {
    return await chromium.launch({ channel: 'chrome' });
  }
};
const browser = await launchBrowser();
const page = await browser.newPage({ viewport: { width: L.W, height: L.H }, deviceScaleFactor: 1 });
const render = async (html, file, sel, transparent = true) => {
  await page.setContent(`<!doctype html><html><head><meta charset="utf-8"><style>${CSS}</style></head><body>${html}</body></html>`);
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(150);
  await page.locator(sel).first().screenshot({ path: path.join(OUT, file), omitBackground: transparent });
};

await render(`<div id="bg" style="width:${L.W}px;height:${L.H}px;position:relative;background:
    linear-gradient(rgba(6,182,212,.08) 1px, transparent 1px) 0 0 / 40px 40px,
    linear-gradient(90deg, rgba(6,182,212,.08) 1px, transparent 1px) 0 0 / 40px 40px,
    radial-gradient(950px 600px at 85% 20%, rgba(217,70,239,.24), transparent 62%),
    radial-gradient(950px 600px at 15% 85%, rgba(6,182,212,.22), transparent 62%), #04060e;">
    <div style="position:absolute;left:${L.brand.x}px;top:${L.brand.y}px;display:flex;align-items:center;gap:14px">
      <div style="width:46px;height:46px">${LOGO_SVG}</div>
      <div class="heading" style="font-size:28px"><span class="grad" style="font-weight:800">ALPHAEVOLVE</span> <span style="font-weight:600;color:#e2e8f0">PLUGIN</span></div>
      <span class="chip" style="padding:4px 14px;font-size:15px;margin-left:8px">CLAUDE CODE &amp; ANTIGRAVITY</span>
    </div>
  </div>`, 'bg.png', '#bg', false);

const S = L.screen, B = L.bezel, topBar = 36;
await render(`<div id="ph" style="width:${S.w + 2 * B}px;height:${S.h + 2 * B + topBar}px;position:relative">
    <svg width="${S.w + 2 * B}" height="${S.h + 2 * B + topBar}" style="position:absolute;inset:0;filter:drop-shadow(0 0 36px rgba(6,182,212,.35))">
      <defs><mask id="m"><rect width="100%" height="100%" fill="#fff"/><rect x="${B}" y="${B + topBar}" width="${S.w}" height="${S.h}" rx="12" fill="#000"/></mask></defs>
      <rect width="100%" height="100%" rx="${16 + B}" fill="#080b16" mask="url(#m)"/>
      <rect x="1.5" y="1.5" width="${S.w + 2 * B - 3}" height="${S.h + 2 * B + topBar - 3}" rx="${15 + B}" fill="none" stroke="#06b6d4" stroke-width="2.5" mask="url(#m)"/>
      <circle cx="${B + 22}" cy="${B + topBar / 2}" r="6.5" fill="#f43f5e"/>
      <circle cx="${B + 44}" cy="${B + topBar / 2}" r="6.5" fill="#facc15"/>
      <circle cx="${B + 66}" cy="${B + topBar / 2}" r="6.5" fill="#22d3ee"/>
    </svg></div>`, 'frame.png', '#ph');
L.frameOffset = { x: S.x - B, y: S.y - B - topBar };

const cardEvents = events.filter(e => e.type === 'card');
const items = [];
cardEvents.forEach((e, i) => {
  let end = i + 1 < cardEvents.length ? cardEvents[i + 1].t : END;
  if (e.rect) {
    const close = events.find(c => c.type === 'close' && c.t > e.t);
    if (close && close.t < end) end = close.t + 0.2;
  }
  items.push({ kind: 'card', n: i, id: e.id, start: e.t, end, rect: e.rect || null });
});

const cardItems = items.filter(i => i.kind === 'card');
for (let i = 1; i < cardItems.length; i++) {
  const prev = cardItems[i - 1], it = cardItems[i];
  if (it.start > prev.end + 0.05) {
    if (it.rect) it.zoomStart = it.start;
    it.start = prev.end;
  }
}

const voices = events.filter(e => e.type === 'voice');
voices.forEach((v, i) => {
  const next = i + 1 < voices.length ? voices[i + 1].t : END;
  items.push({
    kind: 'caption',
    n: i,
    id: v.id,
    start: v.t,
    end: Math.min(next - 0.05, v.t + (DUR[v.id] || 3.0) + 0.9),
  });
});

for (const it of items) {
  if (it.kind === 'card') {
    const e = cardEvents[it.n];
    await render(cards[e.id](e), `card_${it.n}.png`, '.card');
    it.file = `card_${it.n}.png`;
  } else {
    const capText = script.lines[it.id].cap;
    await render(`<div class="cap">${capText}</div>`, `cap_${it.n}.png`, '.cap');
    it.file = `cap_${it.n}.png`;
  }
}

const START = Math.max(0, cardItems[0].start - 0.5);
fs.writeFileSync(
  path.join(OUT, 'timeline.json'),
  JSON.stringify({ L, style: 'cyberpunk', layout: 'desktop', start: START, end: END, items, events }, null, 2)
);
await browser.close();
console.log(`[assets.mjs] Rendered ${cardItems.length} cyberpunk cards, ${voices.length} captions`);
