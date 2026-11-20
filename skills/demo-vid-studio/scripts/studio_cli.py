#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["edge-tts", "numpy", "scipy"]
# ///
"""
Demo Vid Studio CLI (studio_cli.py)
Unified production pipeline for narrated 1080p demo videos across Antigravity and Claude Code.
All subcommands write JSON results to --output and print a concise status message.
"""

import argparse
import base64
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import wave


SKILL_ROOT = pathlib.Path(__file__).resolve().parent.parent
TEMPLATES_DIR = SKILL_ROOT / "templates"
RATE_LIMIT_LOCK = pathlib.Path(tempfile.gettempdir()) / "demo_vid_studio_ratelimit.lock"


class RateLimitError(Exception):
    """Raised when an external API responds with HTTP 429 Too Many Requests."""


def load_dotenv_files():
    """Loads environment variables from ~/.env and local .env without printing any values."""
    for env_path in [pathlib.Path.home() / ".env", pathlib.Path(".env")]:
        if not env_path.exists():
            continue
        try:
            for raw_line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip("'").strip('"')
                if k and k not in os.environ:
                    os.environ[k] = v
        except Exception:
            pass


def enforce_rate_limit(min_interval_sec: float = 1.0):
    """Cross-process rate limiter using a timestamp file in the system temp directory."""
    now = time.monotonic()
    last_ts = 0.0
    if RATE_LIMIT_LOCK.exists():
        try:
            last_ts = float(RATE_LIMIT_LOCK.read_text(encoding="utf-8").strip())
        except Exception:
            last_ts = 0.0
    elapsed = now - last_ts
    if 0 < elapsed < min_interval_sec:
        time.sleep(min_interval_sec - elapsed)
    try:
        RATE_LIMIT_LOCK.write_text(str(time.monotonic()), encoding="utf-8")
    except Exception:
        pass


def redact_url(url: str) -> str:
    """Removes credential-like query parameters so URLs are safe to print."""
    return re.sub(r"([?&](?:key|api_key|apikey|token|access_token)=)[^&]+", r"\1REDACTED", url, flags=re.I)


def api_request_json(url: str, payload: dict, headers: dict, rate_limit_rps: float = 1.0, max_retries: int = 4) -> dict:
    """Performs an HTTP POST JSON request with rate limiting, exponential backoff on 5xx, and full body error reporting."""
    min_interval = 1.0 / max(0.1, rate_limit_rps)
    data = json.dumps(payload).encode("utf-8")
    req_headers = {"Content-Type": "application/json", **headers}

    for attempt in range(1, max_retries + 1):
        enforce_rate_limit(min_interval)
        req = urllib.request.Request(url, data=data, headers=req_headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                body = resp.read().decode("utf-8", errors="replace")
                return json.loads(body) if body else {}
        except urllib.error.HTTPError as e:
            err_body = ""
            try:
                err_body = e.read().decode("utf-8", errors="replace")
            except Exception:
                pass
            if e.code == 429:
                raise RateLimitError(
                    f"HTTP 429 RateLimitError at {redact_url(url)} (rate_limit={rate_limit_rps} req/s). Response: {err_body[:400]}"
                )
            if 500 <= e.code < 600 and attempt < max_retries:
                backoff = 2 ** attempt
                print(f"[retry] HTTP {e.code} from {redact_url(url)}, retrying in {backoff}s (attempt {attempt}/{max_retries})...", file=sys.stderr)
                time.sleep(backoff)
                continue
            raise RuntimeError(f"HTTP {e.code} error calling {redact_url(url)} (rate_limit={rate_limit_rps} req/s): {err_body[:600]}")
        except urllib.error.URLError as e:
            if attempt < max_retries:
                backoff = 2 ** attempt
                print(f"[retry] Network error ({e.reason}) calling {redact_url(url)}, retrying in {backoff}s...", file=sys.stderr)
                time.sleep(backoff)
                continue
            raise RuntimeError(f"Network error calling {redact_url(url)}: {e.reason}")
    raise RuntimeError(f"Exhausted retries calling {redact_url(url)}")


def find_blender():
    """Finds the Blender executable: BLENDER_PATH, PATH, then the usual install folders."""
    env = os.environ.get("BLENDER_PATH")
    if env and pathlib.Path(env).exists():
        return env
    hit = shutil.which("blender")
    if hit:
        return hit
    candidates = [pathlib.Path("/Applications/Blender.app/Contents/MacOS/Blender")]
    for root in [os.environ.get("ProgramFiles", r"C:\Program Files"), os.environ.get("LOCALAPPDATA", "")]:
        if root:
            candidates += sorted(pathlib.Path(root).glob("Blender Foundation/Blender*/blender.exe"), reverse=True)
            candidates += sorted(pathlib.Path(root).glob("Programs/Blender Foundation/Blender*/blender.exe"), reverse=True)
    for c in candidates:
        if c.exists():
            return str(c)
    return None


def run_blender(extra_args: list, timeout: int = 1800):
    exe = find_blender()
    if not exe:
        print("Error: Blender not found. Install it from blender.org (free, open source) or set BLENDER_PATH.", file=sys.stderr)
        sys.exit(1)
    script = SKILL_ROOT / "scripts" / "blender_scene.py"
    cmd = [exe, "-b", "--factory-startup", "-noaudio", "-P", str(script), "--", *extra_args]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if res.returncode != 0 or "[blender_scene]" not in (res.stdout or ""):
        tail = "\n".join(((res.stdout or "") + (res.stderr or "")).splitlines()[-25:])
        raise RuntimeError(f"Blender render failed (exit {res.returncode}):\n{tail}")
    return exe


def write_json_output(output_path: str, data: dict):
    out_file = pathlib.Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Success! Data written to: {out_file}")


def get_ffmpeg_filter_flag() -> str:
    """Detects FFmpeg major version; returns '-/filter_complex' for FFmpeg 7+ and '-filter_complex_script' for older."""
    try:
        res = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True, check=False)
        first_line = (res.stdout or "").splitlines()[0] if res.stdout else ""
        m = re.search(r"ffmpeg version (\d+)", first_line)
        if m and int(m.group(1)) < 7:
            return "-filter_complex_script"
    except Exception:
        pass
    return "-/filter_complex"


# ============================================================================
# Subcommand 1: check
# ============================================================================
def cmd_check(args):
    checks = {
        "ffmpeg": shutil.which("ffmpeg") is not None,
        "node": shutil.which("node") is not None,
        "python_modules": {},
    }
    for mod in ["edge_tts", "numpy", "scipy"]:
        try:
            __import__(mod)
            checks["python_modules"][mod] = True
        except ImportError:
            checks["python_modules"][mod] = False

    checks["blender"] = find_blender()
    load_dotenv_files()
    checks["configured_api_providers"] = {
        "gemini": bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")),
        "higgsfield": bool(os.environ.get("HIGGSFIELD_API_KEY")),
        "firefly": bool(os.environ.get("FIREFLY_API_KEY") and os.environ.get("ADOBE_CLIENT_ID")),
        "fal": bool(os.environ.get("FAL_KEY")),
        "openai": bool(os.environ.get("OPENAI_API_KEY")),
    }
    checks["ready"] = checks["ffmpeg"] and checks["node"] and all(checks["python_modules"].values())
    write_json_output(args.output, checks)


# ============================================================================
# Subcommand 2: init
# ============================================================================
def cmd_init(args):
    target = pathlib.Path(args.target)
    target.mkdir(parents=True, exist_ok=True)
    created = []

    for fname in ["script.json", "record.mjs", "assets.mjs", "storyboard.md"]:
        src = TEMPLATES_DIR / fname
        dst = target / fname
        if dst.exists() and not args.overwrite:
            continue
        content = src.read_text(encoding="utf-8")
        if fname == "script.json":
            cfg = json.loads(content)
            cfg["layout"] = args.layout
            cfg["style"] = args.style
            cfg["voice"] = args.voice
            content = json.dumps(cfg, indent=2, ensure_ascii=False)
        elif fname == "storyboard.md":
            content = (
                content.replace("{{PROJECT_NAME}}", target.resolve().parent.name)
                .replace("{{LAYOUT}}", args.layout)
                .replace("{{STYLE}}", args.style)
                .replace("{{VOICE}}", args.voice)
                .replace("{{AI_PROVIDER}}", "Pure CSS/SVG (or Gemini / Higgsfield / Firefly)")
            )
        dst.write_text(content, encoding="utf-8")
        created.append(str(dst))

    write_json_output(args.output, {
        "status": "initialized",
        "target": str(target),
        "layout": args.layout,
        "style": args.style,
        "voice": args.voice,
        "files_written": created,
    })


# ============================================================================
# Subcommand 3: tts
# ============================================================================
def cmd_tts(args):
    base = pathlib.Path(args.target)
    script_file = base / "script.json"
    if not script_file.exists():
        print(f"Error: {script_file} not found. Run 'init' first.", file=sys.stderr)
        sys.exit(1)

    cfg = json.loads(script_file.read_text(encoding="utf-8"))
    voice = args.voice or cfg.get("voice", "en-US-AvaNeural")
    out_dir = base / "voice"
    out_dir.mkdir(parents=True, exist_ok=True)
    dur = {}

    for k, line in cfg["lines"].items():
        mp3 = out_dir / f"{k}.mp3"
        wav = out_dir / f"{k}.wav"
        subprocess.run(
            [sys.executable, "-m", "edge_tts", "--voice", voice, "--rate", args.rate, "--text", line["say"], "--write-media", str(mp3)],
            check=True,
        )
        subprocess.run(
            [
                "ffmpeg", "-y", "-v", "error", "-i", str(mp3),
                "-af", "silenceremove=start_periods=1:start_threshold=-50dB,areverse,silenceremove=start_periods=1:start_threshold=-50dB,areverse",
                "-ar", "44100", "-ac", "1", str(wav),
            ],
            check=True,
        )
        with wave.open(str(wav)) as w:
            dur[k] = round(w.getnframes() / w.getframerate(), 3)

    dur_file = out_dir / "durations.json"
    dur_file.write_text(json.dumps(dur, indent=2), encoding="utf-8")
    write_json_output(args.output, {
        "status": "ok",
        "voice": voice,
        "durations_file": str(dur_file),
        "durations": dur,
        "total_speech_seconds": round(sum(dur.values()), 2),
    })


# ============================================================================
# Subcommand 4: frames2video
# ============================================================================
def cmd_frames2video(args):
    base = pathlib.Path(args.target)
    raw = base / "raw"
    events_file = raw / "events.json"
    list_file = raw / "frames" / "list.txt"
    if not events_file.exists() or not list_file.exists():
        print(f"Error: Missing {events_file} or {list_file}. Run 'node {base}/record.mjs' first.", file=sys.stderr)
        sys.exit(1)

    events = json.loads(events_file.read_text(encoding="utf-8"))
    end = events[-1]["t"]
    lines = list_file.read_text(encoding="utf-8").splitlines()
    frames, t = [], 0.0
    for i in range(0, len(lines) - 1, 2):
        name = lines[i].split("'")[1]
        d = float(lines[i + 1].split()[1])
        frames.append((t, raw / "frames" / name))
        t += d

    fps = args.fps
    build_dir = base / "build"
    build_dir.mkdir(parents=True, exist_ok=True)
    out_mp4 = build_dir / "screen.mp4"

    p = subprocess.Popen(
        [
            "ffmpeg", "-y", "-v", "error", "-f", "image2pipe", "-framerate", str(fps),
            "-c:v", "mjpeg", "-i", "-", "-vf", "format=yuv420p",
            "-c:v", "libx264", "-preset", "medium", "-crf", "14", str(out_mp4),
        ],
        stdin=subprocess.PIPE,
    )
    k, cache_path, cache = 0, None, b""
    total_ticks = int(end * fps) + 1
    for n in range(total_ticks):
        now = n / fps
        while k + 1 < len(frames) and frames[k + 1][0] <= now:
            k += 1
        if frames[k][1] != cache_path:
            cache_path = frames[k][1]
            cache = cache_path.read_bytes()
        p.stdin.write(cache)
    p.stdin.close()
    p.wait()
    if p.returncode != 0:
        print("Error: ffmpeg image2pipe failed", file=sys.stderr)
        sys.exit(1)

    write_json_output(args.output, {
        "status": "ok",
        "screen_video": str(out_mp4),
        "fps": fps,
        "duration_seconds": round(end, 2),
        "total_frames_piped": total_ticks,
    })


# ============================================================================
# Subcommand 5: music (Multi-Style Procedural Audio Synthesis)
# ============================================================================
def synthesize_music(style: str, dur: float, out_wav: pathlib.Path):
    import numpy as np

    sr = 44100
    n = int(dur * sr)
    out = np.zeros((n, 2), dtype=np.float64)

    def hz(m):
        return 440.0 * (2.0 ** ((m - 69.0) / 12.0))

    def env(length, a, r):
        e = np.ones(length)
        ai, ri = min(length // 2, int(a * sr)), min(length // 2, int(r * sr))
        if ai > 0:
            e[:ai] = np.linspace(0, 1, ai) ** 2
        if ri > 0:
            e[-ri:] *= np.linspace(1, 0, ri) ** 2
        return e

    style_cfg = {
        "ambient":   {"bpm": 72,  "chords": [[48, 55, 64, 67], [45, 52, 60, 64], [41, 48, 57, 60], [43, 50, 59, 62]], "wave": "pad",      "arp_prob": 0.55},
        "minimal":   {"bpm": 84,  "chords": [[45, 52, 59, 64], [41, 48, 57, 60], [43, 50, 57, 62], [40, 47, 55, 59]], "wave": "pure",     "arp_prob": 0.30},
        "cartoon":   {"bpm": 112, "chords": [[53, 60, 65, 69], [50, 57, 62, 65], [46, 53, 58, 62], [48, 55, 60, 64]], "wave": "chiptune", "arp_prob": 0.85},
        "storybook": {"bpm": 76,  "chords": [[50, 57, 62, 66], [47, 54, 59, 62], [43, 50, 55, 59], [45, 52, 57, 61]], "wave": "musicbox", "arp_prob": 0.70},
        "clay3d":    {"bpm": 96,  "chords": [[48, 55, 60, 64], [53, 57, 60, 65], [50, 55, 59, 62], [43, 50, 55, 59]], "wave": "marimba",  "arp_prob": 0.75},
        "cyberpunk": {"bpm": 100, "chords": [[45, 52, 57, 60], [41, 48, 53, 57], [48, 55, 60, 64], [40, 47, 52, 56]], "wave": "synth",    "arp_prob": 0.80},
    }
    cfg = style_cfg.get(style, style_cfg["ambient"])
    bpm = cfg["bpm"]
    beat = 60.0 / bpm
    bar = 4.0 * beat
    chords = cfg["chords"]
    wtype = cfg["wave"]

    rng = np.random.default_rng(7)
    k = 0
    start = 0.0
    while start < dur:
        ch = chords[k % len(chords)]
        length = 2 * bar + 1.2
        i0 = int(start * sr)
        i1 = min(n, i0 + int(length * sr))
        seg = np.arange(i1 - i0) / sr
        e = env(int(length * sr), 1.4, 1.6)[: i1 - i0]

        for j, m in enumerate(ch):
            f = hz(m)
            if wtype == "chiptune":
                v = np.sign(np.sin(2 * np.pi * f * seg)) * 0.25 + np.sin(2 * np.pi * f * seg) * 0.75
                v *= e * 0.025
            elif wtype == "synth":
                v = (np.sin(2 * np.pi * f * seg) + 0.5 * np.sin(2 * np.pi * 2 * f * seg) + 0.25 * np.sin(2 * np.pi * 3 * f * seg)) * e * 0.035
            elif wtype == "pure":
                v = np.sin(2 * np.pi * f * seg) * e * 0.035
            else:
                v = (np.sin(2 * np.pi * f * seg) + 0.35 * np.sin(2 * np.pi * 2 * f * seg + 0.3) + 0.6 * np.sin(2 * np.pi * f * 1.004 * seg)) * e * 0.042
            pan = 0.35 + 0.1 * j
            out[i0:i1, 0] += v * (1 - pan)
            out[i0:i1, 1] += v * pan

        # Melodic / Arpeggio layer
        for b in range(8):
            if rng.random() < cfg["arp_prob"]:
                m = ch[rng.integers(1, len(ch))] + 12 + (12 if rng.random() < 0.25 else 0)
                s = start + b * beat
                j0 = int(s * sr)
                if j0 >= n:
                    break
                L = min(n - j0, int(2.0 * sr))
                st = np.arange(L) / sr
                f = hz(m)
                if wtype == "marimba":
                    bell = (np.sin(2 * np.pi * f * st) + 0.2 * np.sin(2 * np.pi * 4.0 * f * st) * np.exp(-st * 12.0)) * np.exp(-st * 4.5) * 0.065
                elif wtype == "musicbox":
                    bell = (np.sin(2 * np.pi * f * st) + 0.35 * np.sin(2 * np.pi * 3.0 * f * st)) * np.exp(-st * 2.8) * 0.055
                elif wtype == "chiptune":
                    bell = np.tanh(2.5 * np.sin(2 * np.pi * f * st)) * np.exp(-st * 5.0) * 0.045
                else:
                    bell = (np.sin(2 * np.pi * f * st) + 0.25 * np.sin(2 * np.pi * 3.01 * f * st)) * np.exp(-st * 2.2) * 0.05
                attack = min(L, int(0.004 * sr))
                if attack > 0:
                    bell[:attack] *= np.linspace(0, 1, attack)
                p = rng.uniform(0.25, 0.75)
                out[j0 : j0 + L, 0] += bell * (1 - p)
                out[j0 : j0 + L, 1] += bell * p

        # Bass pulse
        for b in range(2):
            s = start + b * bar
            j0 = int(s * sr)
            if j0 >= n:
                break
            L = min(n - j0, int(bar * sr))
            st = np.arange(L) / sr
            bf = hz(ch[0] - 12)
            bass = np.sin(2 * np.pi * bf * st) * np.exp(-st * 0.9) * 0.06 * env(L, 0.05, 0.4)
            out[j0 : j0 + L] += bass[:, None] * 0.5

        start += 2 * bar
        k += 1

    # Stereo echo
    d = int(beat * 0.75 * sr)
    if d < n:
        wet = np.zeros_like(out)
        wet[d:, 0] = out[:-d, 1]
        wet[d:, 1] = out[:-d, 0]
        out = out + 0.28 * wet

    fi, fo = min(n // 3, int(2.0 * sr)), min(n // 3, int(3.5 * sr))
    if fi > 0:
        out[:fi] *= np.linspace(0, 1, fi)[:, None]
    if fo > 0:
        out[-fo:] *= np.linspace(1, 0, fo)[:, None]
    peak = np.max(np.abs(out)) + 1e-9
    out *= 0.5 / peak
    pcm = (out * 32767).astype(np.int16)

    out_wav.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out_wav), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())


def cmd_music(args):
    base = pathlib.Path(args.target)
    out_wav = base / "build" / "music.wav"
    synthesize_music(args.style, args.duration, out_wav)
    write_json_output(args.output, {
        "status": "ok",
        "style": args.style,
        "duration_seconds": args.duration,
        "music_file": str(out_wav),
    })


# ============================================================================
# Subcommand 6: generate-asset (Pluggable AI Image/Video Generation)
# ============================================================================
STYLE_PROMPT_SUFFIX = {
    "ambient": "soft pastel aurora mesh gradient, clean modern glassmorphism aesthetic, subtle depth of field, 4k studio background",
    "minimal": "sleek minimal dark slate monochrome aesthetic, Linear and Apple design style, soft geometric lighting",
    "cartoon": "vibrant 2D cartoon pop-art illustration, bold black ink outlines, cel-shaded vibrant colors",
    "storybook": "warm storybook watercolor and gouache illustration on textured cream paper, cosy whimsical aesthetic",
    "clay3d": "cute soft 3D claymorphism diorama, handmade matte plasticine clay texture, soft studio lighting, tilt-shift",
    "cyberpunk": "futuristic cyberpunk neon grid stage, glowing cyan and magenta holographic accents, dark sci-fi aesthetic",
}


def cmd_generate_asset(args):
    load_dotenv_files()
    provider = args.provider.lower()
    if provider == "blender":
        return generate_blender_asset(args)
    if not args.prompt:
        print("Error: --prompt is required for AI providers.", file=sys.stderr)
        sys.exit(1)
    style_hint = STYLE_PROMPT_SUFFIX.get(args.style, "")
    full_prompt = f"{args.prompt}. Style: {style_hint}" if style_hint else args.prompt
    asset_out = pathlib.Path(args.asset_out)
    asset_out.parent.mkdir(parents=True, exist_ok=True)

    if provider == "gemini":
        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            print("Error: GEMINI_API_KEY is missing in ~/.env or .env. Add it there without pasting it into chat.", file=sys.stderr)
            sys.exit(1)
        model = args.model or "imagen-3.0-generate-002"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:predict"
        payload = {
            "instances": [{"prompt": full_prompt}],
            "parameters": {"sampleCount": 1, "aspectRatio": "16:9"},
        }
        resp = api_request_json(url, payload, headers={"x-goog-api-key": api_key}, rate_limit_rps=1.0)
        preds = resp.get("predictions", [])
        if not preds or "bytesBase64Encoded" not in preds[0]:
            raise RuntimeError(f"Unexpected Gemini Imagen response structure: {json.dumps(resp)[:400]}")
        asset_out.write_bytes(base64.b64decode(preds[0]["bytesBase64Encoded"]))

    elif provider == "firefly":
        api_key = os.environ.get("FIREFLY_API_KEY")
        client_id = os.environ.get("ADOBE_CLIENT_ID")
        if not api_key or not client_id:
            print("Error: Firefly needs FIREFLY_API_KEY (an OAuth access token) and ADOBE_CLIENT_ID in ~/.env or .env. Experimental provider.", file=sys.stderr)
            sys.exit(1)
        url = "https://firefly-api.adobe.io/v3/images/generate"
        payload = {"prompt": full_prompt, "size": {"width": 1920, "height": 1080}}
        headers = {"Authorization": f"Bearer {api_key}", "x-api-key": client_id}
        resp = api_request_json(url, payload, headers=headers, rate_limit_rps=1.0)
        img_url = resp.get("outputs", [{}])[0].get("image", {}).get("url")
        if not img_url:
            raise RuntimeError(f"Unexpected Adobe Firefly response: {json.dumps(resp)[:400]}")
        urllib.request.urlretrieve(img_url, str(asset_out))

    elif provider == "higgsfield":
        api_key = os.environ.get("HIGGSFIELD_API_KEY")
        if not api_key:
            print("Error: HIGGSFIELD_API_KEY is missing in ~/.env or .env. Add it there without pasting it into chat.", file=sys.stderr)
            sys.exit(1)
        url = os.environ.get("HIGGSFIELD_API_URL", "https://api.higgsfield.ai/v1/generations")
        payload = {"prompt": full_prompt, "aspect_ratio": "16:9"}
        headers = {"Authorization": f"Bearer {api_key}"}
        resp = api_request_json(url, payload, headers=headers, rate_limit_rps=0.5)
        media_url = resp.get("url") or resp.get("output_url") or (resp.get("data", [{}])[0].get("url"))
        if not media_url:
            raise RuntimeError(f"Higgsfield generation response did not contain direct media URL: {json.dumps(resp)[:400]}")
        urllib.request.urlretrieve(media_url, str(asset_out))

    elif provider == "fal":
        api_key = os.environ.get("FAL_KEY")
        if not api_key:
            print("Error: FAL_KEY is missing in ~/.env or .env. Add it there without pasting it into chat.", file=sys.stderr)
            sys.exit(1)
        model = args.model or "fal-ai/flux/schnell"
        url = f"https://fal.run/{model}"
        payload = {"prompt": full_prompt, "image_size": "landscape_16_9"}
        headers = {"Authorization": f"Key {api_key}"}
        resp = api_request_json(url, payload, headers=headers, rate_limit_rps=1.0)
        img_url = resp.get("images", [{}])[0].get("url")
        if not img_url:
            raise RuntimeError(f"Unexpected Fal.ai response: {json.dumps(resp)[:400]}")
        urllib.request.urlretrieve(img_url, str(asset_out))

    elif provider == "openai":
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            print("Error: OPENAI_API_KEY is missing in ~/.env or .env. Add it there without pasting it into chat.", file=sys.stderr)
            sys.exit(1)
        url = "https://api.openai.com/v1/images/generations"
        payload = {"model": args.model or "gpt-image-1", "prompt": full_prompt, "size": "1536x1024"}
        headers = {"Authorization": f"Bearer {api_key}"}
        resp = api_request_json(url, payload, headers=headers, rate_limit_rps=1.0)
        item = resp.get("data", [{}])[0]
        if "b64_json" in item:
            asset_out.write_bytes(base64.b64decode(item["b64_json"]))
        elif "url" in item:
            urllib.request.urlretrieve(item["url"], str(asset_out))
        else:
            raise RuntimeError(f"Unexpected OpenAI image response: {json.dumps(resp)[:400]}")
    else:
        print(f"Error: Unsupported provider '{provider}'", file=sys.stderr)
        sys.exit(1)

    write_json_output(args.output, {
        "status": "ok",
        "provider": provider,
        "style": args.style,
        "prompt": full_prompt,
        "asset_out": str(asset_out),
    })


def generate_blender_asset(args):
    """Renders a 3D stage background (PNG) or a 3D title intro/outro clip (MP4) in Blender."""
    asset_out = pathlib.Path(args.asset_out)
    asset_out.parent.mkdir(parents=True, exist_ok=True)
    common = ["--style", args.style, "--width", str(args.width), "--height", str(args.height), "--seed", str(args.seed)]
    if args.kind == "background":
        if asset_out.suffix.lower() != ".png":
            asset_out = asset_out.with_suffix(".png")
        exe = run_blender(["--kind", "background", "--out", str(asset_out.resolve()), *common])
    else:
        if asset_out.suffix.lower() != ".mp4":
            asset_out = asset_out.with_suffix(".mp4")
        frames = asset_out.parent / f"{asset_out.stem}_frames"
        if frames.exists():
            shutil.rmtree(frames)
        frames.mkdir(parents=True)
        exe = run_blender(["--kind", args.kind, "--title", args.title or "", "--subtitle", args.subtitle or "",
                           "--seconds", str(args.seconds), "--fps", "30",
                           "--out", str((frames / "f_####").resolve()), *common])
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-framerate", "30", "-i", str(frames / "f_%04d.png"),
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-movflags", "+faststart", str(asset_out)],
                       check=True)
        shutil.rmtree(frames, ignore_errors=True)
    write_json_output(args.output, {
        "status": "ok", "provider": "blender", "blender": exe, "kind": args.kind,
        "style": args.style, "asset_out": str(asset_out),
    })


def video_size(path) -> tuple:
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                          "-of", "csv=p=0", str(path)], capture_output=True, text=True, check=True).stdout.strip()
    w, h = out.split(",")[:2]
    return int(w), int(h)


def attach_clips(master: pathlib.Path, out: pathlib.Path, intro, outro, fps: int = 30):
    """Puts optional intro/outro clips (silent or not) around the narrated master, fitted to the master's size."""
    W, H = video_size(master)
    clips = [c for c in [intro, master, outro] if c]
    inputs, f = [], []
    for k, c in enumerate(clips):
        inputs += ["-i", str(c)]
        f.append(f"[{k}:v]scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,"
                 f"fps={fps},setsar=1,format=yuv420p[v{k}]")
        if pathlib.Path(c) == master:
            f.append(f"[{k}:a]aformat=sample_rates=44100:channel_layouts=stereo[a{k}]")
        else:
            dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(c)],
                                       capture_output=True, text=True, check=True).stdout.strip() or 0)
            f.append(f"anullsrc=r=44100:cl=stereo,atrim=0:{dur:.3f}[a{k}]")
    f.append("".join(f"[v{k}][a{k}]" for k in range(len(clips))) + f"concat=n={len(clips)}:v=1:a=1[vout][aout]")
    subprocess.run(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", ";".join(f), "-map", "[vout]", "-map", "[aout]",
                    "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-c:a", "aac", "-b:a", "192k",
                    "-movflags", "+faststart", str(out)], check=True)


# ============================================================================
# Social formats: re-frame the 1920x1080 master into vertical / square
# ============================================================================
def _even(v):
    return max(2, int(v) // 2 * 2)


def _clamp_box(x, y, w, h, W=1920, H=1080, r=0):
    x, y = max(0, int(x)), max(0, int(y))
    w, h = min(int(w), W - x), min(int(h), H - y)
    return {"x": x // 2 * 2, "y": y // 2 * 2, "w": _even(w), "h": _even(h), "r": r}


# Corner radii of the rendered cards / captions per style (match templates/assets.mjs).
CARD_RADIUS = {"ambient": 32, "minimal": 20, "cartoon": 28, "storybook": 26, "clay3d": 42, "cyberpunk": 16}
CAP_RADIUS = {"ambient": 24, "minimal": 14, "cartoon": 22, "storybook": 20, "clay3d": 32, "cyberpunk": 12}


def stage_boxes(L: dict, style: str = "ambient") -> dict:
    """The three regions of the landscape stage worth keeping, cropped to their exact outlines."""
    S, BZ, C, CAP = L["screen"], L["bezel"], L["card"], L["caption"]
    fo = L.get("frameOffset", {"x": S["x"] - BZ, "y": S["y"] - BZ})
    phone = S["h"] > S["w"]
    device = _clamp_box(fo["x"], fo["y"], S["w"] + 2 * BZ, S["y"] + S["h"] + BZ - fo["y"], r=(40 + BZ) if phone else (16 + BZ))
    card = _clamp_box(C["x"], C["y"], C["w"], C["h"], r=CARD_RADIUS.get(style, 28))
    cap_h = CAP.get("h") or min(130, 1080 - CAP["y"] - 6)
    caption = _clamp_box(CAP["x"], CAP["y"], CAP["w"], cap_h, r=CAP_RADIUS.get(style, 20))
    return {"device": device, "card": card, "caption": caption}


def plan_reframe(boxes: dict, W: int, H: int, margin: int = 48, gap: int = 32) -> list:
    """Places device + card stacked or side by side, caption underneath.
    If both would end up too small to read (wide desktop stage in a square), drops the card
    and gives the device the room; the caption still carries the message."""
    place, s = _plan(boxes, W, H, margin, gap, with_card=True)
    if s < 0.6:
        alt, s2 = _plan(boxes, W, H, margin, gap, with_card=False)
        if s2 > s * 1.3:
            return alt
    return place


def _plan(boxes, W, H, margin, gap, with_card):
    d, p = boxes["device"], boxes["caption"]
    c = boxes["card"] if with_card else {"x": 0, "y": 0, "w": 2, "h": 0, "r": 0}
    sp = min(1.0, (W - 2 * margin) / p["w"])
    ph = p["h"] * sp
    area_h = H - 2 * margin - ph - gap
    stacked = min(1.0, (W - 2 * margin) / max(d["w"], c["w"]), (area_h - gap) / (d["h"] + c["h"]))
    side = min(1.0, (W - 2 * margin - gap) / (d["w"] + c["w"]), area_h / max(d["h"], c["h"]))
    if not with_card:
        stacked = side = min(1.0, (W - 2 * margin) / d["w"], area_h / d["h"])
    s = max(stacked, side)
    dw, dh, cw, ch = _even(d["w"] * s), _even(d["h"] * s), _even(c["w"] * s), _even(c["h"] * s)
    pw, phe = _even(p["w"] * sp), _even(ph)
    if stacked >= side:
        block_h = dh + gap + ch
        top = margin + max(0, (area_h - block_h) // 2)
        place = [(d, dw, dh, (W - dw) // 2, top, s), (c, cw, ch, (W - cw) // 2, top + dh + gap, s)]
        bottom = top + block_h
    else:
        block_w, block_h = dw + gap + cw, max(dh, ch)
        left = (W - block_w) // 2
        top = margin + max(0, (area_h - block_h) // 2)
        place = [(d, dw, dh, left, top + (block_h - dh) // 2, s), (c, cw, ch, left + dw + gap, top + (block_h - ch) // 2, s)]
        bottom = top + block_h
    if not with_card:
        place = place[:1]
        bottom = place[0][4] + dh
    place.append((p, pw, phe, (W - pw) // 2, min(H - margin - phe, bottom + gap), sp))
    return place, s


def _round_mask(w: int, h: int, r: int) -> str:
    """ffmpeg source for a white rounded rectangle on black, used as an alpha mask."""
    r = max(1, min(r, w // 2, h // 2))
    inside = (f"if(gt(abs(X-{w}/2)\\,{w}/2-{r})*gt(abs(Y-{h}/2)\\,{h}/2-{r})\\,"
              f"if(lte(hypot(abs(X-{w}/2)-({w}/2-{r})\\,abs(Y-{h}/2)-({h}/2-{r}))\\,{r})\\,255\\,0)\\,255)")
    # one frame of geq, then looped: evaluating geq on every frame is very slow
    return f"color=c=white:s={w}x{h}:r=30:d=0.034,format=gray,geq=lum={inside},loop=loop=-1:size=1:start=0"


def render_reframe(master: pathlib.Path, L: dict, W: int, H: int, out: pathlib.Path, audio: bool = True,
                   style: str = "ambient", backdrop=None, blur: int = 10):
    """Lays the device, card and caption of the 16:9 master onto a W x H canvas.
    Each piece is cut to its exact outline with rounded corners; the backdrop is the stage
    background (blurred), or a blurred copy of the video when no background image is given."""
    place = plan_reframe(stage_boxes(L, style), W, H)
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(master)],
                               capture_output=True, text=True, check=True).stdout.strip())
    inputs = ["-i", str(master)]
    n = len(place)
    if backdrop and pathlib.Path(backdrop).exists():
        inputs += ["-loop", "1", "-framerate", "30", "-t", f"{dur:.3f}", "-i", str(backdrop)]
        f = [f"[0:v]split={n}" + "".join(f"[r{k}]" for k in range(n)),
             f"[1:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}" + (f",gblur=sigma={blur}" if blur else "") + ",format=rgba[l0]"]
    else:
        f = [f"[0:v]split={1 + n}[bgsrc]" + "".join(f"[r{k}]" for k in range(n)),
             f"[bgsrc]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},gblur=sigma=36,eq=brightness=-0.06,format=rgba[l0]"]
    cur = "l0"
    for k, (b, w, h, x, y, s) in enumerate(place):
        f.append(f"{_round_mask(w, h, int(b['r'] * s))}[mk{k}]")
        f.append(f"[r{k}]crop={b['w']}:{b['h']}:{b['x']}:{b['y']},scale={w}:{h}:flags=lanczos,format=rgba[c{k}]")
        f.append(f"[c{k}][mk{k}]alphamerge[p{k}]")
        f.append(f"[{cur}][p{k}]overlay={x}:{y}:shortest=1[l{k + 1}]")
        cur = f"l{k + 1}"
    f.append(f"[{cur}]format=yuv420p[vout]")
    cmd = ["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", ";".join(f), "-map", "[vout]"]
    if audio:
        cmd += ["-map", "0:a?", "-c:a", "aac", "-b:a", "192k"]
    else:
        cmd += ["-an"]
    cmd += ["-t", f"{dur:.3f}", "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-movflags", "+faststart", str(out)]
    subprocess.run(cmd, check=True)


def make_gif(src: pathlib.Path, out: pathlib.Path, width: int, fps: int):
    vf = f"fps={fps},scale={width}:-1:flags=lanczos,split[s0][s1];[s0]palettegen=max_colors=128[p];[s1][p]paletteuse=dither=bayer"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-vf", vf, str(out)], check=True)


def fit_caption_height(T: dict, build_dir: pathlib.Path) -> dict:
    """Sets L.caption.h to the tallest rendered caption PNG so crops hug the caption bar."""
    L = T["L"]
    if L["caption"].get("h"):
        return L
    hs = []
    for it in T.get("items", []):
        if it.get("kind") != "caption":
            continue
        png = build_dir / it["file"]
        try:
            with open(png, "rb") as fh:
                head = fh.read(24)
            if head[:4] == bytes([0x89, 0x50, 0x4E, 0x47]):  # PNG signature
                hs.append(int.from_bytes(head[20:24], "big"))
        except OSError:
            pass
    if hs:
        L["caption"]["h"] = max(hs)
    return L


def export_social(master: pathlib.Path, L: dict, vertical: bool, square_gif: bool, gif_width: int, gif_fps: int,
                  square: bool = False, style: str = "ambient", build_dir=None, backdrop=None) -> dict:
    res = {}
    blur = 0 if backdrop else 10
    if not backdrop and build_dir:
        for name in ("bg_ai.png", "bg.png"):
            if (pathlib.Path(build_dir) / name).exists():
                backdrop = pathlib.Path(build_dir) / name
                break
    kw = {"style": style, "backdrop": backdrop, "blur": blur}
    if square:
        s_out = master.with_name(f"{master.stem}-square.mp4")
        render_reframe(master, L, 1080, 1080, s_out, audio=True, **kw)
        res["square_mp4_out"] = str(s_out)
    if vertical:
        v_out = master.with_name(f"{master.stem}-vertical.mp4")
        render_reframe(master, L, 1080, 1920, v_out, audio=True, **kw)
        res["vertical_mp4_out"] = str(v_out)
    if square_gif:
        sq_tmp = master.with_name(f"{master.stem}-square-tmp.mp4")
        render_reframe(master, L, 1080, 1080, sq_tmp, audio=False, **kw)
        g_out = master.with_name(f"{master.stem}-square.gif")
        make_gif(sq_tmp, g_out, gif_width, gif_fps)
        sq_tmp.unlink(missing_ok=True)
        res["square_gif_out"] = str(g_out)
    return res


def cmd_wrap(args):
    video = pathlib.Path(args.video)
    if not video.exists():
        print(f"Error: {video} not found.", file=sys.stderr)
        sys.exit(1)
    for c in (args.intro, args.outro):
        if c and not pathlib.Path(c).exists():
            print(f"Error: {c} not found.", file=sys.stderr)
            sys.exit(1)
    out = pathlib.Path(args.video_out or video.with_name(f"{video.stem}-wrapped.mp4"))
    attach_clips(video, out, args.intro, args.outro)
    res = {"status": "ok", "video_in": str(video), "video_out": str(out), "intro": args.intro, "outro": args.outro}
    if args.gif:
        g = out.with_suffix(".gif")
        make_gif(out, g, args.gif_width, args.gif_fps)
        res["gif_out"] = str(g)
    write_json_output(args.output, res)


def cmd_reframe(args):
    base = pathlib.Path(args.target)
    timeline_file = base / "build" / "timeline.json"
    if not timeline_file.exists():
        print(f"Error: {timeline_file} not found. Run the pipeline through 'assets.mjs' first.", file=sys.stderr)
        sys.exit(1)
    T = json.loads(timeline_file.read_text(encoding="utf-8"))
    L = fit_caption_height(T, base / "build")
    master = pathlib.Path(args.video or (base / "demo-video.mp4"))
    if not master.exists():
        print(f"Error: {master} not found. Run 'compose' first or pass --video.", file=sys.stderr)
        sys.exit(1)
    want = {x.strip() for x in args.formats.split(",") if x.strip()}
    unknown = want - {"vertical", "square", "square-gif"}
    if unknown:
        print(f"Error: unknown format(s): {', '.join(sorted(unknown))}. Use vertical, square, square-gif.", file=sys.stderr)
        sys.exit(1)
    res = export_social(master, L, "vertical" in want, "square-gif" in want, args.gif_width, args.gif_fps, "square" in want,
                        style=args.style or T.get("style", "ambient"), build_dir=base / "build",
                        backdrop=args.backdrop)
    write_json_output(args.output, {"status": "ok", "video_in": str(master), **res})


# ============================================================================
# Subcommand 7: compose
# ============================================================================
def cmd_compose(args):
    import numpy as np
    from scipy import signal

    base = pathlib.Path(args.target)
    B = base / "build"
    timeline_file = B / "timeline.json"
    if not timeline_file.exists():
        print(f"Error: {timeline_file} not found. Run 'node {base}/assets.mjs' first.", file=sys.stderr)
        sys.exit(1)

    T = json.loads(timeline_file.read_text(encoding="utf-8"))
    L, END, items, events = T["L"], T["end"], T["items"], T["events"]
    style = args.style or T.get("style", "ambient")
    S, BZ, C, Z, CAP = L["screen"], L["bezel"], L["card"], L["zoom"], L["caption"]
    frame_off = L.get("frameOffset", {"x": S["x"] - BZ, "y": S["y"] - BZ})
    fps = 30

    screen_mp4 = B / "screen.mp4"
    if not screen_mp4.exists() and (B / "phone.mp4").exists():
        screen_mp4 = B / "phone.mp4"

    # ---------------- Video Filter Graph ----------------
    inputs = [
        "-loop", "1", "-framerate", str(fps), "-t", f"{END:.3f}", "-i", str(B / "bg.png"),
        "-i", str(screen_mp4),
        "-loop", "1", "-framerate", str(fps), "-t", f"{END:.3f}", "-i", str(B / "frame.png"),
    ]
    zoom_cards = [it for it in items if it["kind"] == "card" and it.get("rect")]
    f = []
    f.append(f"[1:v]split={1 + len(zoom_cards)}[ph]" + "".join(f"[z{k}]" for k in range(len(zoom_cards))))
    f.append(f"[ph]scale={S['w']}:{S['h']}:flags=lanczos[phs]")
    f.append(f"[0:v][phs]overlay={S['x']}:{S['y']}:eof_action=repeat[v0]")
    f.append(f"[v0][2:v]overlay={frame_off['x']}:{frame_off['y']}[v1]")

    cur, idx = "v1", 3
    for it in items:
        d = it["end"] - it["start"]
        if d <= 0.2:
            continue
        inputs += ["-loop", "1", "-framerate", str(fps), "-t", f"{d:.3f}", "-i", str(B / it["file"])]
        fo = max(0.0, d - 0.3)
        f.append(
            f"[{idx}:v]format=rgba,fade=in:st=0:d=0.35:alpha=1,fade=out:st={fo:.3f}:d=0.3:alpha=1,setpts=PTS+{it['start']:.3f}/TB[i{idx}]"
        )
        if it["kind"] == "card":
            x, y0 = C["x"], C["y"]
            rise = f"{y0}+28*max(0\\,1-(t-{it['start']:.3f})/0.35)"
            f.append(f"[{cur}][i{idx}]overlay=x={x}:y='{rise}':eval=frame:eof_action=pass[c{idx}]")
        else:
            f.append(f"[{cur}][i{idx}]overlay={CAP['x']}:{CAP['y']}:eof_action=pass[c{idx}]")
        cur = f"c{idx}"
        idx += 1

    # Live region zooms cropped from the 2x screen video
    for k, it in enumerate(zoom_cards):
        r = it["rect"]
        pad = 0
        cx, cy = max(0, round((r["x"] - pad) * 2)), max(0, round((r["y"] - pad) * 2))
        cw, ch = max(4, round((r["w"] + 2 * pad) * 2)), max(4, round((r["h"] + 2 * pad) * 2))
        sc = min(Z["w"] / cw, Z["h"] / ch)
        ow, oh = max(2, int(cw * sc) // 2 * 2), max(2, int(ch * sc) // 2 * 2)
        ox, oy = C["x"] + Z["x"] + (Z["w"] - ow) // 2, C["y"] + Z["y"] + (Z["h"] - oh) // 2
        a, b = it.get("zoomStart", it["start"]) + 0.35, it["end"]
        f.append(
            f"[z{k}]crop={cw}:{ch}:{cx}:{cy},scale={ow}:{oh}:flags=lanczos,format=rgba,"
            f"fade=in:st={a:.3f}:d=0.3:alpha=1,fade=out:st={max(a, b - 0.3):.3f}:d=0.3:alpha=1[zz{k}]"
        )
        f.append(f"[{cur}][zz{k}]overlay={ox}:{oy}:enable='between(t,{a:.3f},{b:.3f})'[m{k}]")
        cur = f"m{k}"

    f.append(f"[{cur}]format=yuv420p[vout]")
    filter_file = B / "filter.txt"
    filter_file.write_text(";\n".join(f), encoding="utf-8")

    # ---------------- Audio Synthesis & Ducking Mix ----------------
    sr = 44100
    N = int(END * sr) + sr

    def read_wav(p):
        with wave.open(str(p)) as w:
            a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768.0
            return a.reshape(-1, 2) if w.getnchannels() == 2 else np.repeat(a[:, None], 2, axis=1)

    def add_clip(buf, clip, t_sec, gain):
        i = int(t_sec * sr)
        if 0 <= i < len(buf):
            j = min(len(buf), i + len(clip))
            buf[i:j] += clip[: j - i] * gain

    rng = np.random.default_rng(5)

    def stereo(m):
        return np.stack([m, m], axis=1)

    def click_sfx():
        t = np.arange(int(0.05 * sr)) / sr
        freq = 1800 if style in ("clay3d", "cartoon") else 2600
        n_part = signal.sosfilt(signal.butter(2, 1800, "hp", fs=sr, output="sos"), rng.standard_normal(len(t)) * np.exp(-t * 400) * 0.35)
        return stereo(np.sin(2 * np.pi * freq * t) * np.exp(-t * 140) * 0.6 + n_part)

    def whoosh_sfx(d=0.55, f0=500, f1=3200):
        L_ = int(d * sr)
        t = np.arange(L_) / sr
        fr, tt, Zs = signal.stft(rng.standard_normal(L_), sr, nperseg=1024)
        c = f0 * (f1 / f0) ** (tt / d)
        Zs *= np.exp(-0.5 * ((fr[:, None] - c[None, :]) / (0.35 * c[None, :])) ** 2)
        x = signal.istft(Zs, sr, nperseg=1024)[1][:L_] * np.sin(np.pi * np.clip(t / d, 0, 1)) ** 1.5
        return stereo(x / (np.abs(x).max() + 1e-9))

    def ding_sfx():
        t = np.arange(int(1.1 * sr)) / sr
        def bell(fq, s0):
            s = np.clip(t - s0, 0, None)
            on = (t >= s0).astype(float)
            return on * (np.sin(2 * np.pi * fq * s) + 0.3 * np.sin(2 * np.pi * 2.76 * fq * s) * np.exp(-s * 6)) * np.exp(-s * 4.5)
        x = bell(1568, 0) + 0.9 * bell(1175, 0.12)
        return stereo(x / (np.abs(x).max() + 1e-9))

    CL, WH, DG = click_sfx(), whoosh_sfx(), ding_sfx()
    sfx = np.zeros((N, 2), np.float32)
    for e in events:
        if e["type"] in ("tap", "translate", "click"):
            add_clip(sfx, CL, e["t"], 0.20)
        elif e["type"] in ("map", "zoom"):
            add_clip(sfx, CL, e["t"], 0.20)
            add_clip(sfx, WH, e["t"] + 0.05, 0.15)
        elif e["type"] == "result":
            add_clip(sfx, DG, e["t"], 0.12)

    dur = json.loads((base / "voice" / "durations.json").read_text(encoding="utf-8"))
    voice = np.zeros((N, 2), np.float32)
    speaking = np.zeros(N, bool)
    for e in events:
        if e["type"] != "voice":
            continue
        v_wav = base / "voice" / f"{e['id']}.wav"
        if not v_wav.exists():
            continue
        clip = read_wav(v_wav)
        clip /= np.abs(clip).max() + 1e-9
        add_clip(voice, clip, e["t"], 0.62)
        speaking[int(e["t"] * sr) : int((e["t"] + dur.get(e["id"], 2.0)) * sr)] = True

    music_wav = B / "music.wav"
    synthesize_music(style, END + 1.5, music_wav)
    music = read_wav(music_wav)[:N]
    if len(music) < N:
        music = np.pad(music, ((0, N - len(music)), (0, 0)))

    duck = np.convolve(np.where(speaking, 0.38, 1.0), np.ones(int(0.25 * sr)) / int(0.25 * sr), mode="same")
    mix = music * duck[:, None] * 0.75 + voice + sfx
    mix *= min(1.0, 0.98 / (np.abs(mix).max() + 1e-9))

    mix_wav = B / "mix.wav"
    with wave.open(str(mix_wav), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((mix * 32767).astype(np.int16).tobytes())

    # ---------------- Render Final 1080p MP4 ----------------
    out_mp4 = pathlib.Path(args.video_out or (base / "demo-video.mp4"))
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    filter_flag = get_ffmpeg_filter_flag()
    start_offset = T.get("start", 0.0)
    final_len = max(0.5, END - start_offset)

    cmd = [
        "ffmpeg", "-y", "-v", "error", *inputs, "-i", str(mix_wav),
        filter_flag, str(filter_file), "-map", "[vout]", "-map", f"{idx}:a",
        "-r", str(fps), "-ss", f"{start_offset:.3f}", "-t", f"{final_len:.3f}",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out_mp4),
    ]
    subprocess.run(cmd, check=True)

    social = {}
    if args.vertical or args.square_gif or args.square:
        fit_caption_height(T, B)
        social = export_social(out_mp4, L, args.vertical, args.square_gif, args.square_gif_width, args.gif_fps, args.square,
                               style=style, build_dir=B, backdrop=args.social_backdrop)
    if args.intro_clip or args.outro_clip:
        master = B / "master.mp4"
        shutil.move(str(out_mp4), str(master))
        attach_clips(master, out_mp4, args.intro_clip, args.outro_clip, fps)

    result_data = {
        "status": "ok",
        "video_out": str(out_mp4),
        "style": style,
        "layout": T.get("layout", "mobile"),
        "duration_seconds": round(final_len, 2),
        "intro_clip": args.intro_clip,
        "outro_clip": args.outro_clip,
    }

    if args.silent_mp4:
        silent_mp4 = out_mp4.with_name(f"{out_mp4.stem}-silent.mp4")
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-i", str(out_mp4), "-an", "-c:v", "copy", "-movflags", "+faststart", str(silent_mp4)],
            check=True,
        )
        result_data["silent_mp4_out"] = str(silent_mp4)

    if args.preview_gif:
        gif_out = out_mp4.parent / "preview.gif"
        vf = f"fps={args.gif_fps},scale={args.gif_width}:-1:flags=lanczos,split[s0][s1];[s0]palettegen=max_colors=128[p];[s1][p]paletteuse=dither=bayer"
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-i", str(out_mp4), "-vf", vf, str(gif_out)],
            check=True,
        )
        result_data["preview_gif_out"] = str(gif_out)

    result_data.update(social)

    write_json_output(args.output, result_data)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Demo Vid Studio — Automated 1080p Narrated Demo Video Pipeline")
    sub = parser.add_subparsers(dest="command", required=True)

    p_check = sub.add_parser("check", help="Check system prerequisites and configured AI asset keys")
    p_check.add_argument("--output", required=True, help="Output JSON file path")
    p_check.set_defaults(func=cmd_check)

    p_init = sub.add_parser("init", help="Initialize demo/ directory with templates")
    p_init.add_argument("--target", default="demo", help="Target demo directory (default: demo)")
    p_init.add_argument("--layout", choices=["mobile", "desktop"], default="mobile", help="Stage layout preset")
    p_init.add_argument("--style", choices=["ambient", "minimal", "cartoon", "storybook", "clay3d", "cyberpunk"], default="ambient", help="Visual & audio style preset")
    p_init.add_argument("--voice", default="en-US-AvaNeural", help="edge-tts neural voice name")
    p_init.add_argument("--overwrite", action="store_true", help="Overwrite existing template files")
    p_init.add_argument("--output", required=True, help="Output JSON file path")
    p_init.set_defaults(func=cmd_init)

    p_tts = sub.add_parser("tts", help="Generate narration WAVs and measure exact durations")
    p_tts.add_argument("--target", default="demo", help="Target demo directory")
    p_tts.add_argument("--voice", default=None, help="Override voice from script.json")
    p_tts.add_argument("--rate", default="-2%", help="Speech rate adjustment (default: -2%%)")
    p_tts.add_argument("--output", required=True, help="Output JSON file path")
    p_tts.set_defaults(func=cmd_tts)

    p_f2v = sub.add_parser("frames2video", help="Pipe 2x CDP screencast frames to constant-fps MP4")
    p_f2v.add_argument("--target", default="demo", help="Target demo directory")
    p_f2v.add_argument("--fps", type=int, default=30, help="Target constant frame rate (default: 30)")
    p_f2v.add_argument("--output", required=True, help="Output JSON file path")
    p_f2v.set_defaults(func=cmd_frames2video)

    p_mus = sub.add_parser("music", help="Synthesize style-matched procedural background music")
    p_mus.add_argument("--target", default="demo", help="Target demo directory")
    p_mus.add_argument("--style", choices=["ambient", "minimal", "cartoon", "storybook", "clay3d", "cyberpunk"], default="ambient")
    p_mus.add_argument("--duration", type=float, required=True, help="Track length in seconds")
    p_mus.add_argument("--output", required=True, help="Output JSON file path")
    p_mus.set_defaults(func=cmd_music)

    p_gen = sub.add_parser("generate-asset", help="Generate AI background or illustration via configured API key")
    p_gen.add_argument("--provider", choices=["blender", "gemini", "higgsfield", "firefly", "fal", "openai"], required=True,
                       help="blender = free local 3D render (no API key); the rest are AI image APIs")
    p_gen.add_argument("--style", choices=["ambient", "minimal", "cartoon", "storybook", "clay3d", "cyberpunk"], default="ambient")
    p_gen.add_argument("--model", default=None, help="Optional specific model ID override")
    p_gen.add_argument("--prompt", default=None, help="Prompt describing the background or card illustration (AI providers)")
    p_gen.add_argument("--kind", choices=["background", "intro", "outro"], default="background", help="Blender: what to render")
    p_gen.add_argument("--title", default=None, help="Blender intro/outro: title in 3D text")
    p_gen.add_argument("--subtitle", default=None, help="Blender intro/outro: smaller line under the title")
    p_gen.add_argument("--seconds", type=float, default=3.0, help="Blender intro/outro length (default: 3)")
    p_gen.add_argument("--width", type=int, default=1920, help="Blender render width (default: 1920)")
    p_gen.add_argument("--height", type=int, default=1080, help="Blender render height (default: 1080)")
    p_gen.add_argument("--seed", type=int, default=7, help="Blender: layout seed for the props")
    p_gen.add_argument("--asset-out", required=True, help="Path to write the generated image/video asset")
    p_gen.add_argument("--output", required=True, help="Output JSON file path")
    p_gen.set_defaults(func=cmd_generate_asset)

    p_cmp = sub.add_parser("compose", help="Compose 1080p video with cards, live zooms, SFX, and ducked audio")
    p_cmp.add_argument("--target", default="demo", help="Target demo directory")
    p_cmp.add_argument("--style", choices=["ambient", "minimal", "cartoon", "storybook", "clay3d", "cyberpunk"], default=None)
    p_cmp.add_argument("--video-out", default=None, help="Output MP4 path (default: <target>/demo-video.mp4)")
    p_cmp.add_argument("--preview-gif", action="store_true", help="Also generate a silent auto-playing preview.gif for GitHub READMEs")
    p_cmp.add_argument("--silent-mp4", action="store_true", help="Also generate a silent *-silent.mp4 alongside the narrated MP4")
    p_cmp.add_argument("--gif-width", type=int, default=840, help="Width in pixels for preview.gif (default: 840)")
    p_cmp.add_argument("--gif-fps", type=int, default=12, help="Frame rate for preview.gif and the square GIF (default: 12)")
    p_cmp.add_argument("--vertical", action="store_true", help="Also export a 1080x1920 (9:16) narrated MP4 for Reels, Shorts and TikTok")
    p_cmp.add_argument("--square", action="store_true", help="Also export a 1080x1080 (1:1) narrated MP4 for feeds")
    p_cmp.add_argument("--square-gif", action="store_true", help="Also export a silent square (1:1) GIF for social feeds")
    p_cmp.add_argument("--social-backdrop", default=None, help="Image behind the pieces in the vertical/square cuts (default: blurred stage background)")
    p_cmp.add_argument("--intro-clip", default=None, help="MP4 to play before the demo (e.g. a Blender intro)")
    p_cmp.add_argument("--outro-clip", default=None, help="MP4 to play after the demo (e.g. a Blender outro)")
    p_cmp.add_argument("--square-gif-width", type=int, default=720, help="Side length in pixels for the square GIF (default: 720)")
    p_cmp.add_argument("--output", required=True, help="Output JSON file path")
    p_cmp.set_defaults(func=cmd_compose)

    p_rf = sub.add_parser("reframe", help="Re-frame an existing 1080p demo into vertical 9:16 MP4 and/or square GIF")
    p_rf.add_argument("--target", default="demo", help="Target demo directory (needs build/timeline.json)")
    p_rf.add_argument("--video", default=None, help="Landscape master MP4 (default: <target>/demo-video.mp4)")
    p_rf.add_argument("--formats", default="vertical,square-gif", help="Comma list: vertical, square, square-gif (default: vertical,square-gif)")
    p_rf.add_argument("--backdrop", default=None, help="Image behind the re-framed pieces, e.g. a square Blender background (default: blurred stage background)")
    p_rf.add_argument("--style", choices=["ambient", "minimal", "cartoon", "storybook", "clay3d", "cyberpunk"], default=None,
                      help="Style of the master (default: from timeline.json); sets the corner radii")
    p_rf.add_argument("--gif-width", type=int, default=720, help="Side length in pixels for the square GIF (default: 720)")
    p_rf.add_argument("--gif-fps", type=int, default=12, help="Frame rate for the square GIF (default: 12)")
    p_rf.add_argument("--output", required=True, help="Output JSON file path")
    p_rf.set_defaults(func=cmd_reframe)

    p_wr = sub.add_parser("wrap", help="Add intro/outro clips (e.g. Blender titles) around any cut, fitted to its size")
    p_wr.add_argument("--video", required=True, help="The cut to wrap (16:9, 9:16 or 1:1 MP4)")
    p_wr.add_argument("--intro", default=None, help="Intro MP4")
    p_wr.add_argument("--outro", default=None, help="Outro MP4")
    p_wr.add_argument("--video-out", default=None, help="Output MP4 (default: <video>-wrapped.mp4)")
    p_wr.add_argument("--gif", action="store_true", help="Also write a silent GIF of the wrapped cut")
    p_wr.add_argument("--gif-width", type=int, default=720, help="GIF width (default: 720)")
    p_wr.add_argument("--gif-fps", type=int, default=12, help="GIF frame rate (default: 12)")
    p_wr.add_argument("--output", required=True, help="Output JSON file path")
    p_wr.set_defaults(func=cmd_wrap)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.func(args)
    except Exception as exc:
        print(f"Error executing '{args.command}': {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
