// Drives and records the app at 2x device pixel ratio using Playwright + Chrome DevTools Protocol (CDP) screencast.
// Logs every voice line, feature card, tap/click, zoom target, and result to <TARGET_DIR>/raw/events.json.
// Usage: node demo/record.mjs
import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';

const TARGET_DIR = process.env.DEMO_DIR || 'demo';
const APP_URL = process.env.APP_URL || 'http://127.0.0.1:3000/';
const SCRIPT = JSON.parse(fs.readFileSync(path.join(TARGET_DIR, 'script.json'), 'utf8'));
const DUR = JSON.parse(fs.readFileSync(path.join(TARGET_DIR, 'voice', 'durations.json'), 'utf8'));

// Layout preset: 'mobile' (390x844 touch) or 'desktop' (1280x800 mouse/pointer)
const LAYOUT = process.env.DEMO_LAYOUT || SCRIPT.layout || 'mobile';
const VIEWPORTS = {
  mobile:  { width: 390,  height: 844, scale: 2, isMobile: true,  hasTouch: true  },
  desktop: { width: 1280, height: 800, scale: 2, isMobile: false, hasTouch: false },
};
const VP = VIEWPORTS[LAYOUT] || VIEWPORTS.mobile;
const W = VP.width, H = VP.height, SCALE = VP.scale;

const OUT = path.join(TARGET_DIR, 'raw');
fs.rmSync(OUT, { recursive: true, force: true });
fs.mkdirSync(path.join(OUT, 'frames'), { recursive: true });

// ---------- Optional upfront API prefetch & deterministic cache ----------
// Prevents slow LLM / backend calls or 503 errors from ruining a recording take.
const API_ORIGIN = new URL(APP_URL).origin;
const CACHE_FILE = path.join(TARGET_DIR, 'api-cache.json');
const cache = new Map(
  fs.existsSync(CACHE_FILE) ? Object.entries(JSON.parse(fs.readFileSync(CACHE_FILE, 'utf8'))) : []
);
const saveCache = () => fs.writeFileSync(CACHE_FILE, JSON.stringify(Object.fromEntries(cache), null, 2));

export const callApi = async (apiPath, body, method = 'POST') => {
  const key = `${method}:${apiPath}:${body}`;
  if (cache.has(key)) return cache.get(key);
  for (let attempt = 1; attempt <= 10; attempt++) {
    try {
      const res = await fetch(API_ORIGIN + apiPath, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: method === 'GET' ? undefined : body,
      });
      const text = await res.text();
      if (res.ok) {
        cache.set(key, text);
        saveCache();
        return text;
      }
      console.log(`  [api-cache] ${apiPath} HTTP ${res.status}, retry ${attempt}/10...`);
    } catch (err) {
      console.log(`  [api-cache] ${apiPath} network error (${err.message}), retry ${attempt}/10...`);
    }
    await new Promise(r => setTimeout(r, Math.min(15000, 2000 * attempt)));
  }
  throw new Error(`Failed to prefetch ${apiPath} after 10 attempts`);
};

// Add any API requests to prefetch before launching the browser:
// Example:
// for (const payload of [{ query: 'example' }]) {
//   await callApi('/api/generate', JSON.stringify(payload));
// }

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
  isMobile: VP.isMobile,
  hasTouch: VP.hasTouch,
});

// Intercept matching API routes during recording and serve from cache with a natural spinner delay
const API_ROUTE_GLOB = process.env.API_ROUTE_GLOB || '**/api/**';
const SIMULATED_LATENCY_MS = 1400;
await ctx.route(API_ROUTE_GLOB, async (route) => {
  const req = route.request();
  if (req.method() !== 'POST') return route.continue();
  const apiPath = new URL(req.url()).pathname;
  const started = Date.now();
  try {
    const body = await callApi(apiPath, req.postData() || '', req.method());
    const wait = SIMULATED_LATENCY_MS - (Date.now() - started);
    if (wait > 0) await new Promise(r => setTimeout(r, wait));
    await route.fulfill({ status: 200, contentType: 'application/json', body });
  } catch {
    await route.continue();
  }
});

const page = await ctx.newPage();

// ---------- 2x CDP Screencast Capture ----------
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

await page.goto(APP_URL);
await page.addStyleTag({ content: `
  .demo-tap {
    position: fixed; z-index: 2147483647; width: 44px; height: 44px; margin: -22px 0 0 -22px;
    border-radius: 50%; pointer-events: none;
    background: rgba(56,189,248,.30); border: 2.5px solid rgba(14,165,233,.70);
    animation: demo-tap-anim .58s ease-out forwards;
  }
  @keyframes demo-tap-anim {
    from { transform: scale(.35); opacity: 1; }
    to   { transform: scale(1.55); opacity: 0; }
  }
  html { scroll-behavior: smooth; }
`});

// ---------- Directing & Synchronization Helpers ----------
let voiceEnd = 0;
const settle = async (gap = 350) => {
  const left = voiceEnd + gap - Date.now();
  if (left > 0) await sleep(left);
};
const say = async (id) => {
  await settle();
  if (!(id in DUR)) throw new Error(`Voice ID "${id}" not found in voice/durations.json`);
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

const tap = async (locatorOrSelector, kind = 'tap') => {
  const loc = typeof locatorOrSelector === 'string' ? page.locator(locatorOrSelector).first() : locatorOrSelector;
  await loc.scrollIntoViewIfNeeded();
  const b = await loc.boundingBox();
  if (!b) throw new Error(`Cannot find boundingBox for tap target`);
  const x = b.x + b.width / 2, y = b.y + b.height / 2;
  await sleep(300);
  log(kind, { x: Math.round(x), y: Math.round(y) });
  await ripple(x, y);
  if (VP.hasTouch) await loc.tap();
  else await loc.click();
};

const typeText = async (locatorOrSelector, text, delay = 80) => {
  const loc = typeof locatorOrSelector === 'string' ? page.locator(locatorOrSelector).first() : locatorOrSelector;
  await tap(loc, 'tap');
  await page.keyboard.press('ControlOrMeta+A');
  await page.keyboard.press('Backspace');
  await sleep(200);
  await page.keyboard.type(text, { delay });
  await sleep(350);
};

const scrollToY = async (y) => {
  await page.evaluate(v => window.scrollTo(0, v), y);
  await sleep(800);
};

const scrollToEl = async (selector, offset = 100) => {
  await page.evaluate(([s, o]) => {
    const e = document.querySelector(s);
    if (e) window.scrollTo(0, e.getBoundingClientRect().top + window.scrollY - o);
  }, [selector, offset]);
  await sleep(800);
};

const boxOf = async (locatorOrSelector) => {
  const loc = typeof locatorOrSelector === 'string' ? page.locator(locatorOrSelector).first() : locatorOrSelector;
  const b = await loc.boundingBox();
  return b ? { x: b.x, y: b.y, w: b.width, h: b.height } : null;
};

const openZoom = async (triggerLocator, targetSelectorOrLocator, cardId, extra = {}) => {
  if (triggerLocator) await tap(triggerLocator, 'zoom');
  else log('zoom');
  await sleep(450);
  const rect = await boxOf(targetSelectorOrLocator);
  card(cardId, { rect, ...extra });
};

const closeZoom = async (closeAction = null) => {
  log('close');
  if (closeAction) await closeAction();
  await sleep(400);
};

// ============================================================================
// SCENE SCRIPT — Customize below according to demo/storyboard.md
// ============================================================================

await sleep(700);
card('intro');
await say('intro1');
await hold(500);

// 1 · scan: zoom on the director's first message
card('scan', { rect: await boxOf('#scan') });
await say('scan');
await hold(300);
log('close');
await tap('#ok1');
await sleep(1100);

// 2 · style picker
card('style', { rect: await boxOf('#styles') });
await say('style');
await sleep(1500);
await tap('#clay');
await hold(300);
log('close');
await sleep(1300);

// 3 · social formats
card('formats', { rect: await boxOf('#fmts') });
await say('formats');
await sleep(1600);
await tap('#fs');
await hold(400);
log('close');
await tap('#ok2');
await sleep(1100);

// 4 · storyboard approval
card('board', { rect: await boxOf('#board') });
await say('board');
await hold(300);
log('close');
await tap('#shoot');
await sleep(1000);

// 5 · pipeline runs
card('run');
await say('run');
await sleep(5600);
await hold(300);
card('done', { rect: await boxOf('#files') });
log('result');
await sleep(1800);
log('close');

// outro
card('outro');
await say('outro');
await hold(1200);
log('end');

// ============================================================================
// Finalize Screencast & Write events.json + frames/list.txt
// ============================================================================
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
console.log(`[record.mjs] Captured ${frames.length} 2x frames | duration: ${endT.toFixed(1)}s | layout: ${LAYOUT}`);
