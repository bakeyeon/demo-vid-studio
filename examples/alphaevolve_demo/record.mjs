// Drives and records the AlphaEvolve Live Evolution Cockpit at 1280x800 (2x DPR)
// Logs every voice line, feature card, tap/click, live 2x MAP-Elites zoom, and result to examples/alphaevolve_demo/raw/events.json.
import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';
import { pathToFileURL } from 'url';

const TARGET_DIR = 'examples/alphaevolve_demo';
const COCKPIT_URL = pathToFileURL(path.resolve(TARGET_DIR, 'cockpit.html')).href;
const DUR = JSON.parse(fs.readFileSync(path.join(TARGET_DIR, 'voice', 'durations.json'), 'utf8'));

const W = 1280, H = 800, SCALE = 2;
const OUT = path.join(TARGET_DIR, 'raw');
fs.rmSync(OUT, { recursive: true, force: true });
fs.mkdirSync(path.join(OUT, 'frames'), { recursive: true });

const launchBrowser = async (extraArgs = []) => {
  try {
    return await chromium.launch({ args: extraArgs });
  } catch {
    return await chromium.launch({ channel: 'chrome', args: extraArgs });
  }
};
const browser = await launchBrowser([`--force-device-scale-factor=${SCALE}`]);
const ctx = await browser.newContext({
  viewport: { width: W, height: H },
  deviceScaleFactor: SCALE,
  isMobile: false,
  hasTouch: false,
});
const page = await ctx.newPage();

const frames = [];
const cdp = await ctx.newCDPSession(page);
cdp.on('Page.screencastFrame', async (f) => {
  const file = path.join(OUT, 'frames', `${String(frames.length).padStart(6, '0')}.jpg`);
  frames.push({ file: path.basename(file), ts: f.metadata.timestamp });
  fs.writeFileSync(file, Buffer.from(f.data, 'base64'));
  try { await cdp.send('Page.screencastFrameAck', { sessionId: f.sessionId }); } catch {}
});
await cdp.send('Page.startScreencast', {
  format: 'jpeg',
  quality: 92,
  maxWidth: W * SCALE,
  maxHeight: H * SCALE,
  everyNthFrame: 1,
});

const t0 = Date.now();
const events = [];
const log = (type, extra = {}) => events.push({ type, t: Number(((Date.now() - t0) / 1000).toFixed(4)), ...extra });
const sleep = (ms) => page.waitForTimeout(ms);

await page.goto(COCKPIT_URL);
await page.addStyleTag({ content: `
  .demo-tap {
    position: fixed; z-index: 2147483647; width: 46px; height: 46px; margin: -23px 0 0 -23px;
    border-radius: 50%; pointer-events: none;
    background: rgba(217,70,239,.35); border: 2.5px solid #22d3ee;
    box-shadow: 0 0 18px #22d3ee;
    animation: demo-tap-anim .55s ease-out forwards;
  }
  @keyframes demo-tap-anim {
    from { transform: scale(.35); opacity: 1; }
    to   { transform: scale(1.6); opacity: 0; }
  }
`});

let voiceEnd = 0;
const settle = async (gap = 320) => {
  const left = voiceEnd + gap - Date.now();
  if (left > 0) await sleep(left);
};
const say = async (id) => {
  await settle();
  log('voice', { id });
  voiceEnd = Date.now() + DUR[id] * 1000;
};
const card = (id, extra = {}) => log('card', { id, ...extra });
const hold = async (ms = 600) => {
  const until = Math.max(Date.now() + ms, voiceEnd + 300);
  await sleep(Math.max(0, until - Date.now()));
};
const ripple = (x, y) => page.evaluate(([x, y]) => {
  const d = document.createElement('div');
  d.className = 'demo-tap';
  d.style.left = `${x}px`;
  d.style.top = `${y}px`;
  document.body.append(d);
  setTimeout(() => d.remove(), 650);
}, [x, y]);

const tap = async (sel, kind = 'tap') => {
  const loc = page.locator(sel).first();
  const b = await loc.boundingBox();
  const x = b.x + b.width / 2, y = b.y + b.height / 2;
  await sleep(250);
  log(kind, { x: Math.round(x), y: Math.round(y) });
  await ripple(x, y);
  await loc.click();
};

const boxOf = async (sel) => {
  const b = await page.locator(sel).first().boundingBox();
  return { x: b.x, y: b.y, w: b.width, h: b.height };
};

// ---------------- Scene 1: Intro ----------------
await sleep(600);
card('intro');
await say('intro1');
await hold(600);
await say('intro2');
await hold(600);

// ---------------- Scene 2: Scaffold & Verify Baseline ----------------
card('baseline');
await say('scaffold');
await sleep(900);
await tap('#btn-baseline', 'tap');
await hold(1000);

// ---------------- Scene 3: Mode A Evolution Loop (Gen 1 -> Gen 3) ----------------
card('loop');
await say('mutate1');
await sleep(1100);
await tap('#btn-gen1', 'tap');
await sleep(1500);
await tap('#btn-gen2', 'tap');
await say('mutate2');
await sleep(1400);
await tap('#btn-gen3', 'tap');
log('result'); // triggers Ding SFX on reaching 1.000!
await hold(1200);

// ---------------- Scene 4: Live 2x Region Zoom of MAP-Elites Archive ----------------
await tap('#btn-archive', 'zoom');
await sleep(350);
card('map-zoom', { rect: await boxOf('#map-panel') });
await say('zoom_map');
await hold(1800);
log('close');

// ---------------- Scene 5: Held-Out & Blind Mode Guardrails ----------------
card('guardrails');
await say('guardrails');
await sleep(1000);
await tap('#btn-guard', 'tap');
log('result');
await hold(1200);

// ---------------- Scene 6: Outro ----------------
card('outro');
await say('outro');
await hold(1500);
log('end');

await cdp.send('Page.stopScreencast');
await ctx.close();

const startSec = t0 / 1000;
const endT = events.at(-1).t;
const lines = [];
frames.forEach((f, i) => {
  const from = i === 0 ? 0 : Math.max(0, f.ts - startSec);
  const to = i + 1 < frames.length ? Math.max(from, frames[i + 1].ts - startSec) : endT;
  if (to > from) {
    lines.push(`file '${f.file}'`, `duration ${(to - from).toFixed(4)}`);
  }
});
if (lines.length >= 2) lines.push(lines.at(-2));
fs.writeFileSync(path.join(OUT, 'frames', 'list.txt'), lines.join('\n'));
await browser.close();

fs.writeFileSync(path.join(OUT, 'events.json'), JSON.stringify(events, null, 2));
console.log(`[record.mjs] Captured ${frames.length} 2x frames | duration: ${endT.toFixed(1)}s`);
