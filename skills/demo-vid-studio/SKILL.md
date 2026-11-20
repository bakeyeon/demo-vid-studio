---
name: demo-vid-studio
description: >-
  Interactive demo video director and automated 1080p video production pipeline
  for web and mobile prototypes. Use when the user asks to record, shoot, or
  create a narrated demo video, product walkthrough, or research prototype
  showcase. Guides the user through feature discovery and a markdown storyboard
  review (demo/storyboard.md), supports 6 visual/audio style presets (ambient,
  minimal, cartoon, storybook, clay3d, cyberpunk), 2 layout presets (mobile,
  desktop), pluggable AI image/video generation (Gemini, Higgsfield, Adobe
  Firefly, Fal, OpenAI, or agent plugins), and a 5-stage pipeline (edge-tts
  narration, 2x CDP Playwright screencast with API caching, exact-30fps frame
  piping, HTML/CSS card & frame rendering, and ffmpeg composition with
  synthesized SFX, procedural background music, live region zooms, and audio
  ducking).
---

# Demo Vid Studio (`demo-vid-studio`)

## Overview

`demo-vid-studio` turns any running web or mobile prototype into a broadcast-ready, 1080p narrated demo video without manual screen recording or video editing software.

It combines:
1. **Interactive AI Directing**: Scans the project, recommends highlight features, asks for user preferences (script, style preset, layout, AI asset provider), and presents a full `demo/storyboard.md` for user approval before writing or running recording scripts.
2. **One Event Log Architecture (`events.json`)**: Narration durations drive the Playwright recorder so the screen waits for the voice, and every tap, zoom, result, card, and voice line is logged to `events.json` for zero-drift synchronization.
3. **6 Signature Visual & Audio Style Presets**: `ambient`, `minimal`, `cartoon`, `storybook`, `clay3d`, and `cyberpunk` — each theming both the HTML/CSS stage/cards/frames and the synthesized background music & sound effects.
4. **Pluggable AI Media Generation**: Optionally generates custom background illustrations, 3D clay/storybook card mascots, or cinematic intro/outro clips via agent plugins or API keys (`GEMINI_API_KEY`, `HIGGSFIELD_API_KEY`, `FIREFLY_API_KEY`, `FAL_KEY`, `OPENAI_API_KEY`), with a 100% free pure-CSS/SVG fallback.

---

## Dependencies

Reuse these installed skills whenever available in the agent environment:
- **`credentials`**: **MANDATORY** whenever checking or prompting for AI media generation API keys (`GEMINI_API_KEY`, `HIGGSFIELD_API_KEY`, `FIREFLY_API_KEY`, `ADOBE_CLIENT_ID`, `FAL_KEY`, `OPENAI_API_KEY`). Verify key presence quietly (`grep -sq "^KEY_NAME=" ~/.env`) and never print or ask the user to paste keys in chat.
- **`gemini-api-cli` / `gemini-api-dev` / `gemini-omni-flash-api`** (optional): When installed, use them for native Gemini TTS, Imagen background/card generation, or Gemini Omni video intro/outro generation.
- **Built-in `image-generator` / `browser` subagents** (optional, Antigravity): Use `image-generator` for zero-key visual asset creation and `browser` (or `read_file` on rendered PNGs) for visual QA of rendered cards and frames.

---

## Quick Start

```bash
# 1. Verify system prerequisites (ffmpeg, node, playwright, edge-tts, numpy, scipy)
uv run skills/demo-vid-studio/scripts/studio_cli.py check --output demo/check.json

# 2. Initialize pipeline templates in the target project's demo/ folder
uv run skills/demo-vid-studio/scripts/studio_cli.py init \
  --target demo \
  --layout mobile \
  --style ambient \
  --output demo/init.json

# 3. (Optional) Generate AI background or card illustration via configured provider
uv run skills/demo-vid-studio/scripts/studio_cli.py generate-asset \
  --provider gemini \
  --style clay3d \
  --prompt "Soft pastel 3D clay diorama background for a translation app studio stage" \
  --asset-out demo/build/bg_ai.png \
  --output demo/asset_result.json

# 4. Run the 5-stage production pipeline
uv run skills/demo-vid-studio/scripts/studio_cli.py tts --target demo --output demo/tts_result.json
node demo/record.mjs
uv run skills/demo-vid-studio/scripts/studio_cli.py frames2video --target demo --output demo/f2v_result.json
node demo/assets.mjs
uv run skills/demo-vid-studio/scripts/studio_cli.py compose --target demo --style ambient --output demo/compose_result.json
```

*(Note: When installed globally, invoke `studio_cli.py` from its installed skill directory, e.g., `~/.gemini/config/skills/demo-vid-studio/scripts/studio_cli.py` or `~/.claude/skills/demo-vid-studio/scripts/studio_cli.py`.)*

---

## Mandatory Directing Workflow

> [!CAUTION]
> **NEVER jump straight to recording or running `record.mjs`.** You MUST complete **Phase 1 (Interactive Discovery)** and **Phase 2 (Storyboard Approval)** with the user first.

### Phase 1: Project Scan & Interactive Discovery

1. **Scan the project codebase**: Quickly inspect `README.md`, main routes/pages, UI components, and backend/LLM API calls.
2. **Interview the user**: Present your findings and ask the user:
   - **Feature Highlights**: *"I scanned the project and found [Feature A, Feature B, Feature C]. I recommend highlighting these in the demo. Are there any other features or details you'd like to emphasize?"*
   - **Script vs. AI Directing**: *"Do you already have a script or scenario in mind, or would you like me to draft the storyline and narration script for you?"*
   - **Visual & Audio Style Preset (`--style`)**: Ask which style fits best:
     - `ambient` *(Default)*: Aurora mesh gradient, frosted glassmorphism cards (`Sora`/`Inter`), soft ambient pads & bell arpeggios.
     - `minimal`: Apple/Linear-inspired sleek slate & monochrome, crisp 1px borders, subtle minimal pulse BGM.
     - `cartoon`: Neo-brutalist pop-art, bold 4px black borders, hard offset shadows, comic speech-bubble captions, upbeat 8-bit chiptune arpeggio BGM.
     - `storybook`: Warm parchment paper texture, watercolor pastel accents, serif typography (`Fraunces`), music-box & harp waltz BGM.
     - `clay3d`: Soft 3D claymorphism with puffy inner/outer shadows, toy-like rounded bezel, marimba/wood-bell procedural BGM.
     - `cyberpunk`: Deep dark grid, neon cyan/magenta glowing HUD cards, monospace typography, synthwave bass arpeggio BGM.
   - **Layout & Voice (`--layout`)**:
     - `mobile` (`390×844` touch screen at 2× DPR on the left, `900×600` feature card + captions on the right)
     - `desktop` (`1280×800` wide browser window at 2× DPR on the left, `560×620` feature card on the right + bottom wide caption)
     - Narration language & voice (e.g., `en-US-AvaNeural`, `en-GB-SoniaNeural`, `ko-KR-SunHiNeural`, `ja-JP-NanamiNeural`).
   - **AI Asset Generation (Optional)**: Ask if they want pure HTML/CSS/SVG rendering (instant, free) or AI-generated background/illustrations via an installed plugin or API key (`Gemini`, `Higgsfield`, `Adobe Firefly`, `Fal`, `OpenAI`).
   - **Silent GIF / Silent MP4 Preview (Optional)**: Ask: *"Would you also like me to generate a silent auto-playing GIF (`preview.gif`) and silent MP4 (`*-silent.mp4`) so you can embed the demo directly in your GitHub `README.md`?"*

### Phase 2: Markdown Storyboard Review (`demo/storyboard.md`)

Before writing `record.mjs` or `assets.mjs`, create `demo/storyboard.md` using `templates/storyboard.md` as a reference and show it to the user:
- Summary of layout, style preset, voice, estimated duration, and pre-cached API endpoints.
- Scene-by-scene table:
  `| Scene # | ID | Screen Action & API Cache | Feature Card & Live Zoom | Narration (say) & Caption (cap) | Est. Duration |`
- **Wait for explicit user confirmation** (e.g., *"Looks good, shoot it!"*) and apply any requested tweaks.

### Phase 3: Scaffolding & Customization

1. Run `studio_cli.py init --target demo --layout <mobile|desktop> --style <style> --output demo/init.json`.
2. Update `demo/script.json` with the approved voice and lines (`say` and `cap`).
3. Customize `demo/record.mjs`:
   - If the app calls slow/flaky APIs (LLMs, external REST APIs), configure the `PREFETCH_CALLS` and `API_ROUTE_GLOB` at the top of `record.mjs` so responses are fetched upfront with retries and cached to `demo/api-cache.json`.
   - Implement the approved scene actions using the built-in helpers:
     - `await say('line_id')` — logs voice start and sets `voiceEnd` timer
     - `card('card_id', extra)` — logs card transition (pass `{ rect: await boxOf(selector) }` to trigger a live cropped zoom of that UI element inside the card!)
     - `await tap(locator, kind)` — scrolls into view, logs tap event (for click SFX), renders a visual touch/click ripple, and clicks/taps
     - `await typeText(locator, text)` — clears and types smoothly
     - `await hold(ms)` — waits for at least `ms` AND until the current voice line finishes
4. Customize `demo/assets.mjs`:
   - Edit `BRAND` (title, subtitle, logo SVG) and the `cards` dictionary to match each scene's card ID from `record.mjs`.
   - If AI assets were generated (`bg_ai.png` or card illustrations), reference them in `assets.mjs`.

### Phase 4: Execution & Visual Verification

Run the 5 stages sequentially:
1. **Stage 1 — Narration (`tts`)**:
   ```bash
   uv run <path-to-skill>/scripts/studio_cli.py tts --target demo --output demo/tts_result.json
   ```
2. **Stage 2 — 2× CDP Recording (`record.mjs`)**:
   Ensure the target app server is running (`npm run dev`, etc.), then execute:
   ```bash
   node demo/record.mjs
   ```
3. **Stage 3 — Constant 30fps Frame Piping (`frames2video`)**:
   ```bash
   uv run <path-to-skill>/scripts/studio_cli.py frames2video --target demo --output demo/f2v_result.json
   ```
4. **Stage 4 — Stage & Card Rendering (`assets.mjs`)**:
   ```bash
   node demo/assets.mjs
   ```
   *Tip*: Inspect 1–2 rendered PNGs (`demo/build/bg.png`, `demo/build/card_0.png`) using `read_file` to verify there is no text overflow or layout clipping.
5. **Stage 5 — Audio Synthesis & Final Composition (`compose`)**:
   ```bash
   uv run <path-to-skill>/scripts/studio_cli.py compose --target demo --style <style> --preview-gif --silent-mp4 --output demo/compose_result.json
   ```
   *(Pass `--preview-gif` and/or `--silent-mp4` when the user opted in during Phase 1 or Phase 2 to generate a GitHub README-ready `preview.gif` and `*-silent.mp4` alongside the narrated MP4.)*

---

## Utility Scripts (`scripts/studio_cli.py`)

Always run `studio_cli.py` via `uv run`. Every subcommand writes structured JSON results to `--output` (Rule: Default to File Output).

### Subcommands

1. **`check`**: Checks whether `ffmpeg`, `node`, `playwright`, `edge_tts`, `numpy`, and `scipy` are installed.
   ```bash
   uv run scripts/studio_cli.py check --output demo/check.json
   ```
2. **`init`**: Scaffolds `script.json`, `record.mjs`, `assets.mjs`, and `storyboard.md` into `--target`.
   ```bash
   uv run scripts/studio_cli.py init --target demo --layout mobile --style ambient --output demo/init.json
   ```
3. **`tts`**: Generates `.wav` files from `script.json` using `edge-tts`, trims leading/trailing silence with `ffmpeg`, and writes `voice/durations.json`.
   ```bash
   uv run scripts/studio_cli.py tts --target demo --rate "-2%" --output demo/tts_result.json
   ```
4. **`frames2video`**: Pipes raw 2× CDP JPEG screencast frames into `ffmpeg` (`image2pipe`) at an exact constant 30fps (`build/screen.mp4`).
   ```bash
   uv run scripts/studio_cli.py frames2video --target demo --fps 30 --output demo/f2v_result.json
   ```
5. **`music`**: Procedurally synthesizes a copyright-free stereo background track (`build/music.wav`) tailored to `--style` (`ambient`, `minimal`, `cartoon`, `storybook`, `clay3d`, `cyberpunk`).
   ```bash
   uv run scripts/studio_cli.py music --target demo --style clay3d --duration 65 --output demo/music_result.json
   ```
6. **`generate-asset`**: Generates an AI image or motion asset via `--provider` (`gemini`, `higgsfield`, `firefly`, `fal`, `openai`) using keys loaded automatically from `~/.env` or `.env`.
   ```bash
   uv run scripts/studio_cli.py generate-asset \
     --provider gemini \
     --style storybook \
     --prompt "Warm watercolor storybook illustration of a cosy library desk" \
     --asset-out demo/build/bg_ai.png \
     --output demo/asset_result.json
   ```
7. **`compose`**: Generates the `ffmpeg` filter graph (`build/filter.txt`) with card slide-up animations, live cropped UI zooms, style-matched synthesized SFX (`click`, `whoosh`, `ding`), ducked background music (`build/mix.wav`), and renders the final 1080p MP4 (`demo/demo-video.mp4`).
   ```bash
   uv run scripts/studio_cli.py compose --target demo --style ambient --video-out demo/demo-video.mp4 --output demo/compose_result.json
   ```

---

## Rate Limiting & Safe Credentials

- **Safe Credentials Protocol**: Before running `generate-asset` with an external API provider, follow the `credentials` skill:
  - Check `~/.env` or `.env` silently: `grep -sq "^GEMINI_API_KEY=" ~/.env` (or `HIGGSFIELD_API_KEY`, `FIREFLY_API_KEY`, `FAL_KEY`, `OPENAI_API_KEY`).
  - Never print keys or ask the user to paste keys in the chat. If missing, provide the hidden terminal prompt command from `credentials`.
- **Cross-Process File-Lock Rate Limiting**: `studio_cli.py` enforces a file-locked rate limiter (`time.monotonic()`) defaulting to 1 request/sec across concurrent runs, with exponential backoff on HTTP 429 / 5xx and full response-body diagnostics on 4xx errors.

---

## Common Mistakes to Avoid

1. **Using Playwright's built-in `recordVideo`**: It ignores `deviceScaleFactor` and produces blurry 1× videos. Always use the template's CDP `Page.startScreencast` with `--force-device-scale-factor=2`.
2. **Using `ffmpeg -f concat` on raw screencast frames**: The concat demuxer introduces per-frame timestamp rounding drift over hundreds of frames. Always use `studio_cli.py frames2video` which pipes exact 30fps ticks via `image2pipe`.
3. **Using `-filter_complex_script` on FFmpeg 7+**: Deprecated/removed in FFmpeg 7+. `studio_cli.py compose` automatically detects FFmpeg version and uses `-/filter_complex <file>` on FFmpeg 7+ (with fallback to `-filter_complex_script` on FFmpeg 6 and older).
4. **Hardcoding `sleep()` instead of waiting for voice duration**: Always call `await say('id')` and `await hold(ms)` so screen actions wait for `durations.json` (`voiceEnd`).
