// Renders the 1080p stage graphics as PNGs (background, device frame, feature cards, captions)
// into <TARGET_DIR>/build/, plus build/timeline.json for compose.
// Supports 2 layouts ('mobile', 'desktop') and 6 styles ('ambient', 'minimal', 'cartoon', 'storybook', 'clay3d', 'cyberpunk').
// Usage: node demo/assets.mjs   (run after record.mjs)
import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';

const TARGET_DIR = process.env.DEMO_DIR || 'demo';
const OUT = path.join(TARGET_DIR, 'build');
fs.mkdirSync(OUT, { recursive: true });

const events = JSON.parse(fs.readFileSync(path.join(TARGET_DIR, 'raw', 'events.json'), 'utf8'));
const script = JSON.parse(fs.readFileSync(path.join(TARGET_DIR, 'script.json'), 'utf8'));
const DUR = JSON.parse(fs.readFileSync(path.join(TARGET_DIR, 'voice', 'durations.json'), 'utf8'));
const END = events.at(-1).t;

const LAYOUT = process.env.DEMO_LAYOUT || script.layout || 'mobile';
const STYLE = process.env.DEMO_STYLE || script.style || 'ambient';

// ---------- 1080p Layout Presets ----------
export const LAYOUT_PRESETS = {
  mobile: {
    W: 1920, H: 1080,
    layout: 'mobile',
    screen:  { x: 260, y: 90,  w: 416, h: 900 },   // 390x844 scaled
    bezel:   16,
    card:    { x: 820, y: 165, w: 940, h: 610 },
    zoom:    { x: 40,  y: 96,  w: 450, h: 474 },   // inside the card
    caption: { x: 820, y: 815, w: 940 },
    brand:   { x: 820, y: 86 },
  },
  desktop: {
    W: 1920, H: 1080,
    layout: 'desktop',
    screen:  { x: 76,   y: 120, w: 1120, h: 700 }, // 1280x800 scaled (16:10)
    bezel:   14,
    card:    { x: 1244, y: 120, w: 600,  h: 700 },
    zoom:    { x: 36,   y: 96,  w: 528,  h: 340 }, // top slot inside the narrower desktop card
    caption: { x: 360,  y: 868, w: 1200 },
    brand:   { x: 76,   y: 44 },
  },
};

export const L = LAYOUT_PRESETS[LAYOUT] || LAYOUT_PRESETS.mobile;

// ---------- Brand Metadata (Customize per project) ----------
const BRAND = {
  titleFirst: 'Demo Vid',
  titleSecond: 'Studio',
  badge: `${STYLE} · ${LAYOUT}`,
  tagline: 'Automated 1080p prototype demo video pipeline',
  repo: 'github.com/your-org/your-repo',
  logoSvg: `<svg viewBox="0 0 48 48"><defs><linearGradient id="g1" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#22d3ee"/><stop offset=".55" stop-color="#38bdf8"/><stop offset="1" stop-color="#8b5cf6"/></linearGradient></defs><rect x="2" y="2" width="44" height="44" rx="13" fill="url(#g1)"/><polygon points="19,15 34,24 19,33" fill="#fff"/></svg>`,
};

// ---------- 6 Signature Style Presets ----------
const STYLE_THEMES = {
  ambient: {
    fonts: 'https://fonts.googleapis.com/css2?family=Sora:wght@300;600;700&family=Inter:wght@400;500;600&display=swap',
    bgCss: `radial-gradient(1200px 700px at 10% -5%, rgba(103,232,249,.45), transparent 62%),
            radial-gradient(1000px 650px at 105% 5%, rgba(196,181,253,.45), transparent 60%),
            radial-gradient(1200px 700px at 55% 115%, rgba(153,246,228,.45), transparent 62%), #f6f8fb`,
    textColor: '#1e293b',
    mutedColor: '#475569',
    headingFont: 'Sora, Inter, sans-serif',
    bodyFont: 'Inter, system-ui, sans-serif',
    gradText: 'linear-gradient(90deg, #06b6d4, #0ea5e9, #8b5cf6)',
    cardCss: `border-radius: 32px; background: rgba(255,255,255,.74); border: 1.5px solid rgba(255,255,255,.92);
              box-shadow: 0 24px 60px rgba(15,23,42,.10), 0 2px 6px rgba(15,23,42,.04); backdrop-filter: blur(24px);`,
    chipCss: `border-radius: 999px; color: #0e7490; background: rgba(207,250,254,.92); border: 1px solid rgba(103,232,249,.65);`,
    capCss:  `border-radius: 24px; background: rgba(15,23,42,.88); color: #f8fafc; box-shadow: 0 16px 40px rgba(15,23,42,.20);`,
    frameFill: '#0f172a',
    frameStroke: '#475569',
  },
  minimal: {
    fonts: 'https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap',
    bgCss: `linear-gradient(180deg, #090d16 0%, #111827 100%)`,
    textColor: '#f8fafc',
    mutedColor: '#94a3b8',
    headingFont: 'Inter, system-ui, sans-serif',
    bodyFont: 'Inter, system-ui, sans-serif',
    gradText: 'linear-gradient(90deg, #f8fafc, #94a3b8)',
    cardCss: `border-radius: 20px; background: rgba(17,24,39,.88); border: 1px solid rgba(255,255,255,.12);
              box-shadow: 0 20px 50px rgba(0,0,0,.45);`,
    chipCss: `border-radius: 8px; color: #e2e8f0; background: rgba(255,255,255,.08); border: 1px solid rgba(255,255,255,.16);`,
    capCss:  `border-radius: 14px; background: rgba(255,255,255,.94); color: #0f172a; box-shadow: 0 12px 32px rgba(0,0,0,.35);`,
    frameFill: '#1e293b',
    frameStroke: '#64748b',
  },
  cartoon: {
    fonts: 'https://fonts.googleapis.com/css2?family=Fredoka:wght@500;600;700&family=Plus+Jakarta+Sans:wght@500;700&display=swap',
    bgCss: `radial-gradient(#cbd5e1 2px, transparent 2px) 0 0 / 28px 28px, #fef08a`,
    textColor: '#0f172a',
    mutedColor: '#1e293b',
    headingFont: 'Fredoka, cursive, sans-serif',
    bodyFont: '"Plus Jakarta Sans", sans-serif',
    gradText: 'linear-gradient(90deg, #ef4444, #f97316, #8b5cf6)',
    cardCss: `border-radius: 28px; background: #ffffff; border: 4px solid #0f172a;
              box-shadow: 12px 12px 0px #0f172a;`,
    chipCss: `border-radius: 999px; color: #0f172a; background: #38bdf8; border: 3px solid #0f172a; box-shadow: 4px 4px 0px #0f172a;`,
    capCss:  `border-radius: 22px; background: #ffffff; color: #0f172a; border: 4px solid #0f172a; box-shadow: 8px 8px 0px #0f172a;`,
    frameFill: '#0f172a',
    frameStroke: '#0f172a',
  },
  storybook: {
    fonts: 'https://fonts.googleapis.com/css2?family=Fraunces:ital,wght@0,500;0,700;1,400&family=Quicksand:wght@500;600;700&display=swap',
    bgCss: `radial-gradient(900px 600px at 15% 15%, rgba(254,215,170,.45), transparent 65%),
            radial-gradient(900px 600px at 85% 85%, rgba(187,247,208,.40), transparent 65%), #fdf8f0`,
    textColor: '#432818',
    mutedColor: '#6f4e37',
    headingFont: 'Fraunces, Georgia, serif',
    bodyFont: 'Quicksand, sans-serif',
    gradText: 'linear-gradient(90deg, #b45309, #d97706, #15803d)',
    cardCss: `border-radius: 26px; background: rgba(255,251,242,.90); border: 2px solid #d6c3a5;
              box-shadow: 0 18px 45px rgba(107,70,40,.12), inset 0 0 0 6px rgba(214,195,165,.25);`,
    chipCss: `border-radius: 999px; color: #7c2d12; background: #ffedd5; border: 1.5px solid #fdba74;`,
    capCss:  `border-radius: 20px; background: #432818; color: #fef3c7; border: 2px solid #9a7b56; box-shadow: 0 12px 30px rgba(67,40,24,.22);`,
    frameFill: '#5c3a21',
    frameStroke: '#8c6239',
  },
  clay3d: {
    fonts: 'https://fonts.googleapis.com/css2?family=Nunito:wght@600;700;800&display=swap',
    bgCss: `linear-gradient(135deg, #e0e7ff 0%, #fce7f3 50%, #dcfce7 100%)`,
    textColor: '#1e1b4b',
    mutedColor: '#4338ca',
    headingFont: 'Nunito, sans-serif',
    bodyFont: 'Nunito, sans-serif',
    gradText: 'linear-gradient(90deg, #6366f1, #ec4899, #10b981)',
    cardCss: `border-radius: 42px; background: #f8fafc; border: none;
              box-shadow: 20px 25px 50px rgba(99,102,241,.18), -10px -10px 30px rgba(255,255,255,.9),
              inset -6px -8px 16px rgba(148,163,184,.25), inset 6px 8px 16px rgba(255,255,255,1);`,
    chipCss: `border-radius: 999px; color: #4338ca; background: #e0e7ff;
              box-shadow: 4px 6px 12px rgba(99,102,241,.16), inset -2px -3px 6px rgba(99,102,241,.15), inset 2px 3px 6px rgba(255,255,255,.9);`,
    capCss:  `border-radius: 32px; background: #312e81; color: #f8fafc;
              box-shadow: 12px 16px 32px rgba(49,46,129,.28), inset -4px -5px 10px rgba(0,0,0,.3), inset 4px 5px 10px rgba(255,255,255,.22);`,
    frameFill: '#4f46e5',
    frameStroke: '#818cf8',
  },
  cyberpunk: {
    fonts: 'https://fonts.googleapis.com/css2?family=Orbitron:wght@600;800&family=Rajdhani:wght@500;600;700&display=swap',
    bgCss: `linear-gradient(rgba(6,182,212,.07) 1px, transparent 1px) 0 0 / 40px 40px,
            linear-gradient(90deg, rgba(6,182,212,.07) 1px, transparent 1px) 0 0 / 40px 40px,
            radial-gradient(900px 600px at 80% 20%, rgba(217,70,239,.22), transparent 60%), #05050a`,
    textColor: '#e2e8f0',
    mutedColor: '#67e8f9',
    headingFont: 'Orbitron, sans-serif',
    bodyFont: 'Rajdhani, sans-serif',
    gradText: 'linear-gradient(90deg, #22d3ee, #f43f5e, #d946ef)',
    cardCss: `border-radius: 16px; background: rgba(10,12,24,.86); border: 2px solid #06b6d4;
              box-shadow: 0 0 32px rgba(6,182,212,.28), inset 0 0 20px rgba(217,70,239,.12);`,
    chipCss: `border-radius: 6px; color: #22d3ee; background: rgba(6,182,212,.14); border: 1px solid #22d3ee; box-shadow: 0 0 12px rgba(6,182,212,.35);`,
    capCss:  `border-radius: 12px; background: rgba(10,12,24,.94); color: #f0abfc; border: 1.5px solid #d946ef; box-shadow: 0 0 24px rgba(217,70,239,.35);`,
    frameFill: '#090d16',
    frameStroke: '#06b6d4',
  },
};

const T = STYLE_THEMES[STYLE] || STYLE_THEMES.ambient;
const isNarrowCard = L.card.w < 750;

const CSS = `
  @import url('${T.fonts}');
  * { box-sizing: border-box; margin: 0; }
  body { font-family: ${T.bodyFont}; color: ${T.textColor}; background: transparent; }
  .heading { font-family: ${T.headingFont}; }
  .grad { background: ${T.gradText}; -webkit-background-clip: text; background-clip: text; color: transparent; }
  .card { width: ${L.card.w}px; height: ${L.card.h}px; padding: ${isNarrowCard ? '32px 34px' : '40px 44px'}; position: relative; ${T.cardCss} }
  .chip { display: inline-block; padding: 8px 18px; font: 600 ${isNarrowCard ? '19px' : '22px'} ${T.bodyFont}; ${T.chipCss} }
  h2 { font: 700 ${isNarrowCard ? '36px' : '46px'}/1.18 ${T.headingFont}; letter-spacing: -.01em; margin: 18px 0 14px; color: ${T.textColor}; }
  p { font-size: ${isNarrowCard ? '23px' : '28px'}; line-height: 1.45; color: ${T.mutedColor}; }
  .row { display: flex; align-items: center; gap: 14px; font-size: ${isNarrowCard ? '21px' : '25px'}; color: ${T.textColor}; margin: 12px 0; }
  .ico { width: 42px; height: 42px; border-radius: 12px; display: grid; place-items: center; background: rgba(148,163,184,.18); font-size: 22px; flex: none; }
  .slot { position: absolute; left: ${L.zoom.x}px; top: ${L.zoom.y}px; width: ${L.zoom.w}px; height: ${L.zoom.h}px; border-radius: 22px;
    box-shadow: 0 0 0 1.5px rgba(148,163,184,.38), 0 12px 30px rgba(15,23,42,.12); background: transparent; }
  .side { position: absolute; ${isNarrowCard
    ? `left: 36px; right: 36px; top: ${L.zoom.y + L.zoom.h + 24}px;`
    : `left: ${L.zoom.x + L.zoom.w + 34}px; right: 38px; top: 96px;`} }
  code { font: 500 ${isNarrowCard ? '20px' : '24px'} 'JetBrains Mono', Consolas, monospace; background: rgba(148,163,184,.2); padding: 4px 10px; border-radius: 8px; }
  .cap { width: ${L.caption.w}px; padding: 20px 30px; font: 600 ${isNarrowCard ? '26px' : '30px'}/1.38 ${T.bodyFont}; text-align: center; ${T.capCss} }
`;

// ---------- Card Templates (Customize per project) ----------
const cards = {
  intro: () => `<div class="card">
      <div style="display:flex;align-items:center;gap:20px;margin-top:24px">
        <div style="width:92px;height:92px;flex:none">${BRAND.logoSvg}</div>
        <div class="heading" style="font-size:${isNarrowCard ? '44px' : '58px'};line-height:1.05">
          <span class="grad" style="font-weight:700">${BRAND.titleFirst}</span>
          <span style="font-weight:300">${BRAND.titleSecond}</span>
        </div>
      </div>
      <p style="margin-top:34px;font-size:${isNarrowCard ? '26px' : '32px'};color:${T.textColor}"><b>${BRAND.tagline}</b></p>
      <p style="margin-top:14px">Driven by one event log (<code>events.json</code>) so narration, actions, live zooms, and audio stay locked in sync.</p>
      <div style="margin-top:32px;display:flex;flex-wrap:wrap;gap:10px">
        <span class="chip">2× CDP Capture</span>
        <span class="chip">${STYLE} style</span>
        <span class="chip">${LAYOUT} layout</span>
      </div>
    </div>`,
  step1: (e) => `<div class="card">
      <span class="chip">${e.label || '1 · Feature Walkthrough'}</span>
      <h2 style="margin-top:36px">${e.text || 'Interactive Prototype Flow'}</h2>
      <p style="margin-top:18px">The recorder waits for each voice line to finish before performing the next tap or scroll.</p>
    </div>`,
  detail: () => `<div class="card">
      <span class="chip">🔍 Live Region Zoom</span>
      <div class="slot"></div>
      <div class="side">
        <div class="row"><span class="ico">🎯</span><span><b>Live Crop</b>: 2× sharp stream</span></div>
        <div class="row"><span class="ico">⚡</span><span><b>Zero Drift</b>: piped at 30fps</span></div>
        <div class="row"><span class="ico">🎵</span><span><b>Audio Mix</b>: auto-ducked BGM</span></div>
      </div>
    </div>`,
  outro: () => `<div class="card">
      <div style="display:flex;align-items:center;gap:18px;margin-top:16px">
        <div style="width:68px;height:68px;flex:none">${BRAND.logoSvg}</div>
        <div class="heading" style="font-size:40px">
          <span class="grad" style="font-weight:700">${BRAND.titleFirst}</span>
          <span style="font-weight:300">${BRAND.titleSecond}</span>
        </div>
      </div>
      <p style="margin-top:28px"><code>${BRAND.repo}</code></p>
      <p style="margin-top:22px">Built with Playwright CDP, edge-tts, numpy/scipy procedural audio, and FFmpeg.</p>
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

// ---------- Stage Background (Uses bg_ai.png if generated, otherwise pure CSS preset) ----------
const aiBgPath = path.join(OUT, 'bg_ai.png');
// Embedded as a data URI: a page made with setContent() cannot load file:// images.
const bgImageOverlay = fs.existsSync(aiBgPath)
  ? `background-image: url('data:image/png;base64,${fs.readFileSync(aiBgPath).toString('base64')}'); background-size: cover; background-position: center;`
  : `background: ${T.bgCss};`;

await render(`<div id="bg" style="width:${L.W}px;height:${L.H}px;position:relative;${bgImageOverlay}">
    <div style="position:absolute;left:${L.brand.x}px;top:${L.brand.y}px;display:flex;align-items:center;gap:14px">
      <div style="width:42px;height:42px">${BRAND.logoSvg}</div>
      <div class="heading" style="font-size:28px"><span class="grad" style="font-weight:700">${BRAND.titleFirst}</span> <span style="font-weight:300">${BRAND.titleSecond}</span></div>
      <span class="chip" style="padding:4px 14px;font-size:16px;margin-left:8px">${BRAND.badge}</span>
    </div>
  </div>`, 'bg.png', '#bg', false);

// ---------- Device Bezel Frame (Mobile Phone or Desktop Browser Window) ----------
const S = L.screen, B = L.bezel;
if (LAYOUT === 'desktop') {
  const topBar = 36;
  await render(`<div id="ph" style="width:${S.w + 2 * B}px;height:${S.h + 2 * B + topBar}px;position:relative">
      <svg width="${S.w + 2 * B}" height="${S.h + 2 * B + topBar}" style="position:absolute;inset:0;filter:drop-shadow(0 28px 48px rgba(0,0,0,.32))">
        <defs><mask id="m"><rect width="100%" height="100%" fill="#fff"/><rect x="${B}" y="${B + topBar}" width="${S.w}" height="${S.h}" rx="12" fill="#000"/></mask></defs>
        <rect width="100%" height="100%" rx="${16 + B}" fill="${T.frameFill}" mask="url(#m)"/>
        <rect x="1.5" y="1.5" width="${S.w + 2 * B - 3}" height="${S.h + 2 * B + topBar - 3}" rx="${15 + B}" fill="none" stroke="${T.frameStroke}" stroke-width="2.5" mask="url(#m)"/>
        <circle cx="${B + 22}" cy="${B + topBar / 2}" r="6.5" fill="#ef4444"/>
        <circle cx="${B + 44}" cy="${B + topBar / 2}" r="6.5" fill="#facc15"/>
        <circle cx="${B + 66}" cy="${B + topBar / 2}" r="6.5" fill="#22c55e"/>
      </svg></div>`, 'frame.png', '#ph');
  L.frameOffset = { x: S.x - B, y: S.y - B - topBar };
} else {
  await render(`<div id="ph" style="width:${S.w + 2 * B}px;height:${S.h + 2 * B}px;position:relative">
      <svg width="${S.w + 2 * B}" height="${S.h + 2 * B}" style="position:absolute;inset:0;filter:drop-shadow(0 30px 50px rgba(15,23,42,.28))">
        <defs><mask id="m"><rect width="100%" height="100%" fill="#fff"/><rect x="${B}" y="${B}" width="${S.w}" height="${S.h}" rx="40" fill="#000"/></mask></defs>
        <rect width="100%" height="100%" rx="${40 + B}" fill="${T.frameFill}" mask="url(#m)"/>
        <rect x="1.5" y="1.5" width="${S.w + 2 * B - 3}" height="${S.h + 2 * B - 3}" rx="${39 + B}" fill="none" stroke="${T.frameStroke}" stroke-width="2.5" mask="url(#m)"/>
        <rect x="${B + S.w / 2 - 58}" y="${B + 10}" width="116" height="28" rx="14" fill="${T.frameFill}"/>
      </svg></div>`, 'frame.png', '#ph');
  L.frameOffset = { x: S.x - B, y: S.y - B };
}

// ---------- Build Timeline from events.json ----------
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
    const fn = cards[e.id] || ((ev) => `<div class="card"><span class="chip">${ev.id}</span><h2>${ev.label || ev.id}</h2><p>${ev.text || ''}</p></div>`);
    await render(fn(e), `card_${it.n}.png`, '.card');
    it.file = `card_${it.n}.png`;
  } else {
    const capText = script.lines[it.id]?.cap || script.lines[it.id]?.say || it.id;
    await render(`<div class="cap">${capText}</div>`, `cap_${it.n}.png`, '.cap');
    it.file = `cap_${it.n}.png`;
  }
}

const START = cardItems.length > 0 ? Math.max(0, cardItems[0].start - 0.6) : 0;
fs.writeFileSync(
  path.join(OUT, 'timeline.json'),
  JSON.stringify({ L, style: STYLE, layout: LAYOUT, start: START, end: END, items, events }, null, 2)
);
await browser.close();
console.log(`[assets.mjs] Rendered ${cardItems.length} cards, ${voices.length} captions | style: ${STYLE} | layout: ${LAYOUT}`);
