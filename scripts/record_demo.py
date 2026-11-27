"""Phase 9: the demo video (about 3.5 minutes, 1920x1080, H.264 with a synthesized ambient bed).

The app runs as a local developer on a copy of an analysis history (--history: a runs folder,
such as the one scripts/take_screenshots.py leaves in the temp folder), with the real LLM: one
SECOM analysis (about a cent, fast-forwarded to 18 seconds) and one question. Chrome's own
frames are recorded through the DevTools screencast (sharper than Playwright's video), with
effects drawn in the page: a glowing cursor with click ripples, captions, smooth zooms and a
fast-forward badge with the real time.
Title cards (intro, the challenge, how it works, RAG, phone, deployment, results, outro) are
animated HTML pages in the app's look. ffmpeg joins everything with dissolves, a progress line
and the music.

    python scripts/record_demo.py --history <runs folder> [--mock] [--out <file.mp4>]
    python scripts/record_demo.py --cards-only   (just the cards, to check their look)
"""

from __future__ import annotations

import argparse
import base64
import contextlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import wave
from pathlib import Path

import numpy as np
from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from app import ui  # noqa: E402

PORT = 8597
BASE = f"http://localhost:{PORT}"
W, H, FPS = 1920, 1080, 30
XFADE = 0.7          # seconds of each dissolve
FAST_S = 18          # the analysis, however long it takes, fills this many seconds
QUESTION = "Which sensors differ most between failing and passing runs?"
SIGN_IN = "https://foresight-ai.up.railway.app"
NAME = "Ravid Eliav"
FONTS = ("https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&"
         "family=Space+Grotesk:wght@500;600;700&display=swap")
CYAN, VIOLET, AMBER, GREEN = "#22D3EE", "#A78BFA", "#FBBF24", "#34D399"

# --- the effects inside the app's page ---------------------------------------------------------

FX_JS = r"""
(() => {
  const css = `
  #fx-cursor { position: fixed; left: 0; top: 0; width: 26px; height: 26px; margin: -13px 0 0 -13px;
    border-radius: 50%; border: 2px solid rgba(255,255,255,.92); z-index: 2147483600;
    box-shadow: 0 0 14px rgba(34,211,238,.75), inset 0 0 8px rgba(34,211,238,.45);
    pointer-events: none; opacity: 0; transition: opacity .3s, width .15s, height .15s; }
  #fx-cursor::after { content: ""; position: absolute; left: 50%; top: 50%; width: 6px; height: 6px;
    margin: -3px 0 0 -3px; border-radius: 50%; background: #22D3EE; box-shadow: 0 0 8px #22D3EE; }
  .fx-ripple { position: fixed; width: 18px; height: 18px; margin: -9px 0 0 -9px;
    border-radius: 50%;
    border: 2px solid #22D3EE; z-index: 2147483599; pointer-events: none;
    animation: fx-ripple .65s ease-out forwards; }
  @keyframes fx-ripple { to { transform: scale(4.2); opacity: 0; } }
  #fx-cap { position: fixed; left: calc(50% + 140px); bottom: 54px; z-index: 2147483500;
    transform: translate(-50%, 30px); opacity: 0; pointer-events: none;
    display: flex; align-items: center; gap: 26px; padding: 22px 34px 22px 30px; min-width: 760px;
    max-width: 1320px; border-radius: 18px; overflow: hidden;
    background: linear-gradient(135deg, rgba(12,20,38,.92), rgba(9,14,28,.9));
    backdrop-filter: blur(16px); border: 1px solid rgba(34,211,238,.38);
    box-shadow: 0 18px 60px rgba(0,0,0,.55), 0 0 40px rgba(34,211,238,.16);
    transition: transform .7s cubic-bezier(.2,.8,.2,1), opacity .5s; }
  #fx-cap.on { transform: translate(-50%, 0); opacity: 1; }
  #fx-cap::before { content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 5px;
    background: linear-gradient(#22D3EE, #A78BFA); }
  #fx-cap::after { content: ""; position: absolute; top: 0; bottom: 0; left: -40%; width: 30%;
    background: linear-gradient(100deg, transparent, rgba(255,255,255,.10), transparent);
    transform: skewX(-18deg); }
  #fx-cap.on::after { animation: fx-shine 1.6s .35s ease-out; }
  @keyframes fx-shine { to { left: 130%; } }
  #fx-cap .n { font: 700 52px/1 'Space Grotesk', sans-serif; letter-spacing: -.02em;
    background: linear-gradient(135deg, #22D3EE, #A78BFA); -webkit-background-clip: text;
    color: transparent; }
  #fx-cap .k { font: 600 14px/1 Inter, sans-serif; letter-spacing: .22em; text-transform: uppercase;
    color: #7DD3FC; margin-bottom: 10px; }
  #fx-cap .l { font: 500 25px/1.3 Inter, sans-serif; color: #E2E8F0; }
  #fx-badge { position: fixed; top: 22px; left: calc(50% + 140px);
    transform: translate(-50%, -12px);
    z-index: 2147483500; opacity: 0; transition: opacity .4s, transform .4s; pointer-events: none;
    padding: 10px 20px; border-radius: 999px; font: 600 17px/1 Inter, sans-serif; color: #0B1220;
    background: linear-gradient(90deg, #22D3EE, #A78BFA); letter-spacing: .04em;
    box-shadow: 0 0 26px rgba(34,211,238,.55); }
  #fx-badge.on { opacity: 1; transform: translate(-50%, 0); }
  [data-testid="stApp"] { transition: transform 1.3s cubic-bezier(.65,0,.35,1); }
  [data-testid="stToast"] { display: none !important; }`;
  function hideLocalBadge() {
    for (const e of document.querySelectorAll('[data-testid="stSidebar"] .stMarkdownBadge'))
      if (e.innerText.startsWith('Environment')) {
        const box = e.closest('[data-testid="stElementContainer"]');
        if (box && box.style.display !== 'none') box.style.display = 'none';
      }
  }
  function setUp() {
    if (document.getElementById('fx-cursor')) return;
    const style = document.createElement('style'); style.textContent = css;
    document.head.appendChild(style);
    for (const id of ['fx-cursor', 'fx-cap', 'fx-badge']) {
      const e = document.createElement('div'); e.id = id; document.body.appendChild(e);
    }
    const cursor = document.getElementById('fx-cursor');
    document.addEventListener('mousemove', ev => {
      cursor.style.opacity = 1;
      cursor.style.transform = `translate(${ev.clientX}px, ${ev.clientY}px)`;
    }, true);
    document.addEventListener('mousedown', ev => {
      const r = document.createElement('div'); r.className = 'fx-ripple';
      r.style.left = ev.clientX + 'px'; r.style.top = ev.clientY + 'px';
      document.body.appendChild(r); setTimeout(() => r.remove(), 800);
    }, true);
    new MutationObserver(hideLocalBadge).observe(document.body, {childList: true, subtree: true});
    hideLocalBadge();
  }
  window.fxCaption = (n, k, l) => {
    const c = document.getElementById('fx-cap');
    if (!n) { c.classList.remove('on'); return; }
    c.innerHTML = `<div class="n">${n}</div>` +
      `<div><div class="k">${k}</div><div class="l">${l}</div></div>`;
    c.classList.remove('on'); void c.offsetWidth; c.classList.add('on');
  };
  window.fxBadge = (text) => {
    const b = document.getElementById('fx-badge');
    clearInterval(window.fxTick);
    if (text) { b.textContent = text; b.classList.add('on'); } else b.classList.remove('on');
  };
  window.fxClock = () => {  // fast-forward, with the real time that has passed
    const t0 = performance.now(), b = document.getElementById('fx-badge');
    const show = () => { const s = Math.floor((performance.now() - t0) / 1000);
      const clock = `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
      b.textContent = `▶▶  Fast-forward · ${clock} real time`; };
    show(); b.classList.add('on'); window.fxTick = setInterval(show, 200);
  };
  window.fxZoom = (s, x, y) => {
    const a = document.querySelector('[data-testid="stApp"]');
    if (s !== 1) a.style.transformOrigin = `${x}px ${y}px`;
    a.style.transform = s === 1 ? '' : `scale(${s})`;
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', setUp);
  else setUp();
})();
"""


class Recorder:
    """Chrome's frames through the DevTools screencast, kept at most FPS+ per second of the
    finished video. speed(k) shows what follows k times faster (0 leaves it out)."""

    def __init__(self, page: Page, work: Path):
        self.page, self.work = page, work
        self.cdp = page.context.new_cdp_session(page)
        self.cdp.on("Page.screencastFrame", self._frame)
        self.frames: list[tuple[float, Path]] = []
        self.marks: list[tuple[float, float]] = []   # (time, speed); speed 0 = paused
        self.dir: Path | None = None
        self.last_kept = -1e9
        self.clips: list[Path] = []

    def _speed_at(self, t: float) -> float:
        speed = 1.0
        for at, k in self.marks:
            if at <= t:
                speed = k
        return speed

    def _frame(self, event: dict) -> None:
        with_ack = {"sessionId": event["sessionId"]}
        t = float(event["metadata"]["timestamp"])
        speed = self._speed_at(t)
        if self.dir is not None and speed and (t - self.last_kept) / speed >= 1 / (FPS + 6):
            path = self.dir / f"{len(self.frames):06d}.jpg"
            path.write_bytes(base64.b64decode(event["data"]))
            self.frames.append((t, path))
            self.last_kept = t
        with contextlib.suppress(Exception):  # the page may be closing
            self.cdp.send("Page.screencastFrameAck", with_ack)

    def start(self, name: str) -> None:
        self.dir = self.work / f"frames-{name}"
        shutil.rmtree(self.dir, ignore_errors=True)
        self.dir.mkdir(parents=True)
        self.name, self.frames, self.marks, self.last_kept = name, [], [(0.0, 1.0)], -1e9
        self.labels: list[tuple[float, str]] = []
        self.started = time.time()
        self.cdp.send("Page.startScreencast", {"format": "jpeg", "quality": 93})
        self.page.wait_for_timeout(150)

    def speed(self, k: float) -> None:
        self.marks.append((time.time(), k))

    def label(self, text: str) -> None:
        self.labels.append((time.time(), text))

    def video_time(self, at: float) -> float:
        """Where a moment of the recording lands in its clip, after the speed changes."""
        points = sorted({self.started, at, *[a for a, _ in self.marks if self.started < a < at]})
        return sum((b - a) / k for a, b in zip(points, points[1:], strict=False)
                   if (k := self._speed_at(a)))

    def stop(self) -> Path:
        end = time.time()
        self.page.wait_for_timeout(100)
        self.cdp.send("Page.stopScreencast")
        frames, self.dir = self.frames, None
        lines = []
        for i, (t, path) in enumerate(frames):
            nxt = frames[i + 1][0] if i + 1 < len(frames) else end
            # the time this frame stays on screen, at the speeds in between (paused: none)
            span = 0.0
            points = sorted({t, nxt, *[a for a, _ in self.marks if t < a < nxt]})
            for a, b in zip(points, points[1:], strict=False):
                k = self._speed_at(a)
                span += (b - a) / k if k else 0.0
            if span <= 0:
                continue
            lines += [f"file '{path.as_posix()}'", f"duration {span:.4f}"]
        if lines:
            lines.append(lines[-2])  # the concat demuxer's last frame needs repeating
        listing = self.work / f"{self.name}.txt"
        listing.write_text("\n".join(lines), encoding="utf-8")
        clip = self.work / f"{self.name}.mp4"
        ffmpeg("-f", "concat", "-safe", "0", "-i", listing, "-vf",
               f"scale={W}:{H}:flags=lanczos,fps={FPS},format=yuv420p", "-c:v", "libx264",
               "-preset", "slow", "-crf", "15", "-an", clip)
        if frames:
            shutil.rmtree(frames[0][1].parent, ignore_errors=True)
        print(f"clip {self.name}: {duration(clip):.1f} s", flush=True)
        for at, text in self.labels:
            print(f"  {self.video_time(at):6.1f}  {text}", flush=True)
        self.clips.append(clip)
        return clip


def ffmpeg(*args) -> None:
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *map(str, args)], check=True)


def duration(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                          "csv=p=0", str(path)], capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


# --- moving through the app --------------------------------------------------------------------

class Hand:
    """The visible cursor: eased moves and clicks."""

    def __init__(self, page: Page, rec: Recorder):
        self.page, self.rec, self.x, self.y = page, rec, W * 0.62, H * 0.55

    def move(self, x: float, y: float, ms: int = 750) -> None:
        """An eased move that takes ms, however long each step takes to send."""
        x0, y0, start = self.x, self.y, time.time()
        while True:
            t = min(1.0, (time.time() - start) * 1000 / ms)
            e = 4 * t ** 3 if t < .5 else 1 - (-2 * t + 2) ** 3 / 2
            self.page.mouse.move(x0 + (x - x0) * e, y0 + (y - y0) * e)
            if t >= 1:
                break
            self.page.wait_for_timeout(12)
        self.x, self.y = x, y

    def to(self, locator, ms: int = 750, dx: float = 0.5, dy: float = 0.5) -> tuple[float, float]:
        box = locator.bounding_box()
        x, y = box["x"] + box["width"] * dx, box["y"] + box["height"] * dy
        self.move(x, y, ms)
        return x, y

    def click(self, locator, ms: int = 750) -> None:
        x, y = self.to(locator, ms)
        self.page.wait_for_timeout(180)
        self.page.mouse.click(x, y)

    def show(self) -> None:
        self.page.mouse.move(self.x, self.y)


def settle(page: Page, wait_ms: int = 1500) -> None:
    page.wait_for_timeout(500)
    page.wait_for_selector('.stApp[data-test-script-state="notRunning"]', timeout=120_000)
    page.wait_for_timeout(wait_ms)


def caption(page: Page, n: str = "", k: str = "", line: str = "") -> None:
    page.evaluate("([n, k, l]) => fxCaption(n, k, l)", [n, k, line])


def zoom(page: Page, s: float, x: float = 0, y: float = 0, hold_ms: int = 0) -> None:
    page.evaluate("([s, x, y]) => fxZoom(s, x, y)", [s, x, y])
    page.wait_for_timeout(1400 + hold_ms)


def nav(page: Page, hand: Hand, title: str) -> None:
    """Open a page from the menu; its loading is shown 4x faster."""
    hand.rec.label(title)
    link = page.locator('[data-testid="stSidebar"]').get_by_role("link", name=title)
    hand.click(link, 800)
    hand.rec.speed(4)
    settle(page, 1200)
    hand.rec.speed(1)


def tab(page: Page, hand: Hand, name: str, wait_ms: int = 2600) -> None:
    hand.click(page.get_by_role("tab", name=name), 650)
    page.wait_for_timeout(wait_ms)


def walkthrough(page: Page, rec: Recorder, scenes: list[str]) -> None:
    """Sign-in (main), then the local app from Home to Ask Foresight in one take."""
    hand = Hand(page, rec)

    page.goto(SIGN_IN)
    button = page.get_by_role("button", name="Continue with Google")
    button.wait_for(timeout=90_000)
    page.wait_for_timeout(2500)
    rec.start("sign-in")
    caption(page, "01", "Secure access", "Google sign-in. A developer approves every account.")
    page.wait_for_timeout(1200)
    hand.to(button, 1400)
    page.wait_for_timeout(3600)
    caption(page)
    page.wait_for_timeout(700)
    scenes.append(str(rec.stop()))

    page.goto(f"{BASE}/")
    settle(page, 2500)
    hand.show()
    rec.start("app")
    caption(page, "02", "Home",
            "The latest analysis at a glance, with recent analyses and questions.")
    hand.move(560, 300, 1100)
    hand.move(1300, 300, 1500)
    page.wait_for_timeout(1500)
    caption(page)

    # a real SECOM analysis, shown at 8x speed
    nav(page, hand, "New analysis")
    caption(page, "03", "One-click analysis",
            "Five stages run as a CrewAI Flow: four AI agents, with checks in between.")
    page.wait_for_timeout(1500)
    hand.click(page.get_by_role("button", name="Run analysis"), 900)
    rec.label("analysis started")
    page.locator(".fs-stage").first.wait_for(timeout=90_000)
    page.wait_for_timeout(2500)
    hand.move(1100, 640, 900)
    page.wait_for_timeout(1200)
    caption(page)
    page.evaluate("fxClock()")
    page.wait_for_timeout(500)
    fast, began = len(rec.marks), time.time()
    rec.speed(8)  # replaced below, once the analysis's length is known
    page.wait_for_function("""() => {
        const s = [...document.querySelectorAll('.fs-stage')];
        return s.length === 5 && s.every(e => e.classList.contains('fs-done')); }""",
                           timeout=900_000, polling=500)
    rec.speed(1)
    rec.marks[fast] = (rec.marks[fast][0], max(4.0, (time.time() - began) / FAST_S))
    rec.label(f"analysis done ({time.time() - began:.0f} s real, x{rec.marks[fast][1]:.1f})")
    page.evaluate("fxBadge(null)")
    settle(page, 3000)

    nav(page, hand, "Data quality")
    caption(page, "04", "Data quality",
            "A Data Contract checks every column before any AI sees the data.")
    page.wait_for_timeout(3200)
    caption(page)
    zoom(page, 1.35, 360, 170, 2200)
    zoom(page, 1)

    nav(page, hand, "Data insights")
    caption(page, "05", "Data insights",
            "The AI data analyst explores 590 sensors and engineers features.")
    page.wait_for_timeout(2800)
    tab(page, hand, "Sensors that differ", 3000)
    caption(page)
    page.wait_for_timeout(800)

    nav(page, hand, "Model")
    caption(page, "06", "Model",
            "The AI data scientist trains and compares models, then ranks the riskiest runs.")
    page.wait_for_timeout(3000)
    tab(page, hand, "Alarms vs outcomes", 2500)
    caption(page)
    zoom(page, 1.3, 1880, 320, 2000)
    zoom(page, 1)

    nav(page, hand, "Findings")
    caption(page, "07", "Findings",
            "The AI investigator flags anomalies and tests hypotheses; the report cites the "
            "evidence.")
    page.wait_for_timeout(3000)
    tab(page, hand, "Anomalies and run map", 3000)
    caption(page)
    zoom(page, 1.3, 400, 1000, 2400)
    zoom(page, 1)

    nav(page, hand, "Line replay")
    caption(page, "08", "Line replay",
            "Replay the test period run by run, with the alarms the model would have raised.")
    hand.click(page.get_by_text("30 runs/s", exact=True), 800)
    settle(page, 600)
    hand.click(page.get_by_role("button", name="Play", exact=True), 800)
    rec.label("replay playing")
    page.wait_for_timeout(3500)
    caption(page)
    hand.move(1300, 700, 1200)
    page.wait_for_timeout(5500)
    pause = page.get_by_role("button", name="Pause", exact=True)
    if pause.is_visible():  # still playing
        hand.click(pause, 700)
    page.wait_for_timeout(800)

    nav(page, hand, "Trends")
    caption(page, "09", "Trends",
            "Model quality, LLM tokens and run time across every analysis.")
    page.wait_for_timeout(2200)
    tab(page, hand, "LLM tokens per run", 2600)
    tab(page, hand, "Where the run time goes", 2600)
    caption(page)
    page.wait_for_timeout(600)

    nav(page, hand, "Ask Foresight")
    caption(page, "10", "Ask Foresight",
            "Answers from the analysis's reports and data, with their sources.")
    page.wait_for_timeout(3200)
    caption(page)
    chat = page.get_by_test_id("stChatInputTextArea")
    hand.click(chat, 900)
    chat.press_sequentially(QUESTION, delay=38)
    page.wait_for_timeout(500)
    chat.press("Enter")
    rec.label("question sent")
    page.wait_for_timeout(1200)
    rec.speed(3)
    page.get_by_test_id("stChatMessage").nth(1).wait_for(timeout=180_000)
    settle(page, 300)
    rec.speed(1)
    rec.label("answer shown")
    hand.move(1000, 640, 1200)
    page.wait_for_timeout(6500)
    rec.label("end")
    scenes.append(str(rec.stop()))


# --- the title cards ---------------------------------------------------------------------------

CARD = """<!doctype html><html><head><meta charset="utf-8">
<link rel="stylesheet" href="{fonts}"><style>{app_css}</style><style>
html, body {{ margin: 0; width: {w}px; height: {h}px; overflow: hidden; background: #070B14; }}
body {{ font-family: Inter, sans-serif; color: #DCE4F0; position: relative; }}
.paused *, .paused *::before, .paused *::after {{ animation-play-state: paused !important; }}
.bg {{ position: absolute; inset: -10%; pointer-events: none; }}
.glow {{ position: absolute; border-radius: 50%; filter: blur(30px); }}
.g1 {{ width: 1100px; height: 700px; left: -6%; top: -18%;
  background: radial-gradient(closest-side, rgba(34,211,238,.20), transparent);
  animation: drift1 14s ease-in-out infinite alternate; }}
.g2 {{ width: 1000px; height: 700px; right: -8%; top: 2%;
  background: radial-gradient(closest-side, rgba(167,139,250,.18), transparent);
  animation: drift2 16s ease-in-out infinite alternate; }}
.g3 {{ width: 900px; height: 520px; left: 34%; bottom: -16%;
  background: radial-gradient(closest-side, rgba(251,191,36,.08), transparent);
  animation: drift1 18s ease-in-out infinite alternate-reverse; }}
@keyframes drift1 {{ to {{ transform: translate(120px, 60px) scale(1.08); }} }}
@keyframes drift2 {{ to {{ transform: translate(-140px, 50px) scale(1.1); }} }}
.grid {{ position: absolute; inset: 0;
  background: linear-gradient(rgba(148,163,184,.05) 1px, transparent 1px) 0 0 / 48px 48px,
              linear-gradient(90deg, rgba(148,163,184,.05) 1px, transparent 1px) 0 0 / 48px 48px;
  animation: grid 30s linear infinite; }}
@keyframes grid {{ to {{ background-position: 0 480px, 480px 0; }} }}
.scan {{ position: absolute; left: 0; right: 0; height: 160px; top: -200px;
  background: linear-gradient(transparent, rgba(34,211,238,.06), transparent);
  animation: scan 6s 1s ease-in-out infinite; }}
@keyframes scan {{ to {{ top: 110%; }} }}
.dot {{ position: absolute; width: 3px; height: 3px; border-radius: 50%; background: #7DD3FC;
  box-shadow: 0 0 8px #22D3EE; opacity: 0; animation: rise linear infinite; }}
@keyframes rise {{ 0% {{ transform: translateY(0); opacity: 0; }} 15% {{ opacity: .7; }}
  100% {{ transform: translateY(-420px); opacity: 0; }} }}
.stage {{ position: absolute; inset: 0; display: flex; flex-direction: column;
  align-items: center; justify-content: center; text-align: center; }}
.in {{ opacity: 0; animation: in 1s cubic-bezier(.2,.8,.2,1) forwards; }}
@keyframes in {{ from {{ opacity: 0; transform: translateY(26px); filter: blur(8px); }}
  to {{ opacity: 1; transform: none; filter: none; }} }}
.kicker {{ font: 600 18px/1 Inter, sans-serif; letter-spacing: .32em; text-transform: uppercase;
  color: #7DD3FC; }}
.title {{ font: 700 58px/1.12 'Space Grotesk', sans-serif; color: #F1F5F9; letter-spacing: -.01em;
  margin: 22px 0 0; max-width: 1500px; text-wrap: balance; }}
.grad {{ background: linear-gradient(90deg, #22D3EE, #A78BFA); -webkit-background-clip: text;
  color: transparent; }}
.sub {{ font: 400 26px/1.45 Inter, sans-serif; color: #94A3B8; margin-top: 22px; max-width: 1300px;
  text-wrap: balance; }}
.glass {{ background: var(--fs-glass); border: 1px solid var(--fs-glass-border);
  border-top-color: var(--fs-glass-top); box-shadow: var(--fs-glass-shadow); border-radius: 22px; }}
.art {{ margin-top: 46px; position: relative; border-radius: 22px; overflow: hidden;
  box-shadow: 0 30px 90px rgba(0,0,0,.6), 0 0 60px rgba(34,211,238,.12); }}
.art img {{ display: block; animation: slowzoom 12s ease-out forwards; }}
@keyframes slowzoom {{ from {{ transform: scale(1.0); }} to {{ transform: scale(1.04); }} }}
.art::after {{ content: ""; position: absolute; top: 0; bottom: 0; left: -30%; width: 22%;
  background: linear-gradient(100deg, transparent, rgba(255,255,255,.09), transparent);
  transform: skewX(-16deg); animation: shine 2.2s 1.6s ease-in-out forwards; }}
@keyframes shine {{ to {{ left: 130%; }} }}
{extra}
</style></head><body class="paused"><div class="bg"><div class="glow g1"></div>
<div class="glow g2"></div><div class="glow g3"></div><div class="grid"></div>
<div class="scan"></div>{dots}</div><div class="stage">{body}</div>
<script>{script}</script></body></html>"""


def dots(n: int = 34) -> str:
    rng = np.random.default_rng(7)
    return "".join(
        f'<i class="dot" style="left:{rng.uniform(0, 100):.1f}%;top:{rng.uniform(55, 105):.1f}%;'
        f'animation-duration:{rng.uniform(7, 13):.1f}s;animation-delay:-{rng.uniform(0, 9):.1f}s">'
        f"</i>" for _ in range(n))


def img_uri(name: str) -> str:
    data = (ROOT / "docs" / "images" / f"{name}.webp").read_bytes()
    return "data:image/webp;base64," + base64.b64encode(data).decode()


def delay(s: float) -> str:
    return f'style="animation-delay:{s}s"'


def wordmark(size: int) -> str:
    return (f'<div class="fs-wordmark wm" style="font-size:{size}px">F'
            f'<img class="fs-o" style="width:{size * 1.42:.0f}px;height:{size * 1.42:.0f}px" '
            f'src="{ui._logo_uri()}">resight</div>')


def card_intro() -> tuple[str, str, str, float]:
    body = f"""
<div class="logo-wrap">{wordmark(150)}</div>
<div class="tag in" {delay(1.5)}>Semiconductor yield intelligence</div>
<div class="line"></div>
<div class="sub in" {delay(2.3)}>Multi-agent AI that finds failing production runs early,
and explains why.</div>"""
    extra = """.logo-wrap { animation: logo 1.6s cubic-bezier(.2,.8,.2,1) forwards; opacity: 0; }
@keyframes logo { from { opacity: 0; transform: scale(.82); filter: blur(14px); }
  to { opacity: 1; transform: none; filter: none; } }
.wm { justify-content: center; letter-spacing: -.005em; }
.wm .fs-o { animation: spin 2.2s cubic-bezier(.2,.8,.2,1) both, fs-brand-glow 3s 2s ease-in-out
  infinite; }
@keyframes spin { from { transform: rotate(-200deg) scale(.4); } to { transform: none; } }
.tag { margin-top: 26px; font: 600 24px/1 Inter, sans-serif; letter-spacing: .42em;
  text-transform: uppercase; color: #7DD3FC; }
.line { height: 2px; width: 0; margin: 34px auto 0;
  background: linear-gradient(90deg, transparent, #22D3EE, #A78BFA, transparent);
  animation: grow 1.4s 1.9s cubic-bezier(.2,.8,.2,1) forwards; }
@keyframes grow { to { width: 900px; } }"""
    return body, extra, "", 6.8


def card_challenge() -> tuple[str, str, str, float]:
    stats = [("1567", "", "production runs", "SECOM fab data"),
             ("590", "", "sensor signals", "per run"),
             ("6.6", "%", "of runs fail", "104 of 1,567")]
    tiles = "".join(
        f'<div class="glass stat in" {delay(1.1 + i * .35)}><div class="v" data-to="{v}"'
        f' data-suffix="{suf}">0{suf}</div><div class="s">{label}</div><div class="f">{foot}</div>'
        f"</div>" for i, (v, suf, label, foot) in enumerate(stats))
    body = f"""
<div class="kicker in">The challenge</div>
<div class="title in" {delay(.25)}>Every production run logs hundreds of sensor signals.<br>
Few runs fail, and the cause hides in the noise.</div>
<div class="stats">{tiles}</div>
<div class="answer in" {delay(4.6)}><span class="grad">Foresight</span> finds the risky runs early,
shows the sensors behind them, and writes a cited report.</div>"""
    extra = """.stats { display: flex; gap: 34px; margin-top: 54px; }
.stat { width: 330px; padding: 28px 24px 26px; }
.v { font: 700 64px/1 'Space Grotesk', sans-serif; color: #F1F5F9; }
.s { margin-top: 12px; font: 600 19px/1 Inter, sans-serif; letter-spacing: .14em;
  text-transform: uppercase; color: #7DD3FC; }
.f { margin-top: 10px; font-size: 18px; color: #94A3B8; }
.answer { margin-top: 56px; font: 500 32px/1.4 Inter, sans-serif; color: #E2E8F0;
  max-width: 1600px; }
.answer .grad { font-family: 'Space Grotesk', sans-serif; font-weight: 700; }"""
    script = """window.go = () => { for (const e of document.querySelectorAll('[data-to]')) {
  const to = parseFloat(e.dataset.to), dec = e.dataset.to.includes('.') ? 1 : 0;
  const t0 = performance.now() + 1300, digits = {minimumFractionDigits: dec,
    maximumFractionDigits: dec};
  const step = now => { const p = Math.min(1, Math.max(0, (now - t0) / 1600));
    const q = 1 - Math.pow(1 - p, 3);
    e.textContent = (to * q).toLocaleString('en-US', digits) + e.dataset.suffix;
    if (p < 1) requestAnimationFrame(step); };
  requestAnimationFrame(step); } };"""
    return body, extra, script, 9.0


def card_art(kicker: str, title: str, art: str, width: int, seconds: float):
    def make() -> tuple[str, str, str, float]:
        body = f"""
<div class="kicker in">{kicker}</div>
<div class="title in" {delay(.25)}>{title}</div>
<div class="art in" {delay(.7)}><img src="{img_uri(art)}" style="width:{width}px"></div>"""
        return body, "", "", seconds
    return make


def card_phone() -> tuple[str, str, str, float]:
    phones = ["phone-sign-in", "phone-new-analysis", "phone-insights", "phone-replay"]
    shots = "".join(f'<div class="phone in" {delay(.7 + i * .25)}><img src="{img_uri(p)}"></div>'
                    for i, p in enumerate(phones))
    body = f"""
<div class="kicker in">On the phone</div>
<div class="title in" {delay(.25)}>The same app, made for a small screen</div>
<div class="phones">{shots}</div>"""
    extra = """.phones { display: flex; gap: 40px; margin-top: 46px; }
.phone { padding: 10px; border-radius: 46px; background: #0B1220;
  border: 1px solid rgba(255,255,255,.14);
  box-shadow: 0 30px 80px rgba(0,0,0,.6), 0 0 40px rgba(34,211,238,.14); }
.phone img { display: block; width: 318px; border-radius: 36px; }"""
    return body, extra, "", 8.0


def card_results() -> tuple[str, str, str, float]:
    tiles = [("Failing runs caught", "5", " of 24", "with 40 alarms", CYAN),
             ("Alarm precision", "12.5", "%", "2× the fail rate", CYAN),
             ("Report checks", "26", " of 26", "passed", GREEN),
             ("A full analysis", "2.5", " min", "under 1 US cent", VIOLET)]
    cells = "".join(
        f'<div class="glass kpi in" {delay(.8 + i * .3)}><div class="lab">{label}</div>'
        f'<div class="v" data-to="{v}" data-suffix="{suf}">0{suf}</div>'
        f'<div class="chip" style="--c:{c}">{sub}</div></div>'
        for i, (label, v, suf, sub, c) in enumerate(tiles))
    body = f"""
<div class="kicker in">Results</div>
<div class="title in" {delay(.25)}>The reference analysis on SECOM</div>
<div class="kpis">{cells}</div>
<div class="sub in" {delay(2.4)}>Alarms go to the riskiest 10% of runs, a budget the
line can handle; the report passed all 26 of its safety checks.</div>"""
    extra = """.kpis { display: grid; grid-template-columns: repeat(4, 340px); gap: 30px;
  margin-top: 54px; }
.kpi { padding: 28px 26px 30px; text-align: left; }
.lab { font: 600 16px/1 Inter, sans-serif; letter-spacing: .16em; text-transform: uppercase;
  color: #94A3B8; }
.v { font: 700 66px/1 'Space Grotesk', sans-serif; color: #F1F5F9; margin: 18px 0 18px; }
.chip { display: inline-block; font-size: 18px; padding: 5px 14px; border-radius: 9px;
  color: var(--c); background: color-mix(in srgb, var(--c) 15%, transparent); }"""
    _, _, script, _ = card_challenge()
    return body, extra, script.replace("+ 1300", "+ 1000"), 8.5


def card_outro() -> tuple[str, str, str, float]:
    names = ["CrewAI", "OpenAI", "Streamlit", "Supabase · pgvector", "Railway", "Google sign-in"]
    chips = "".join(f'<span class="chip in" {delay(1.6 + i * .12)}>{c}</span>'
                    for i, c in enumerate(names))
    body = f"""
<div class="logo-wrap in">{wordmark(110)}</div>
<div class="links">
  <div class="glass link in" {delay(.7)}><div class="k">Try it</div>
    <div class="u">foresight-ai.up.railway.app</div></div>
  <div class="glass link in" {delay(.95)}><div class="k">Code</div>
    <div class="u">github.com/RavidEliav/foresight</div></div></div>
<div class="chips">{chips}</div>
<div class="by in" {delay(2.4)}>{NAME} · 2026</div>"""
    extra = """.wm { justify-content: center; }
.links { display: flex; gap: 34px; margin-top: 54px; }
.link { padding: 24px 40px; min-width: 520px; }
.link .k { font: 600 16px/1 Inter, sans-serif; letter-spacing: .26em; text-transform: uppercase;
  color: #7DD3FC; }
.link .u { margin-top: 14px; font: 600 32px/1 'Space Grotesk', sans-serif; color: #F1F5F9; }
.chips { display: flex; gap: 14px; margin-top: 44px; }
.chip { padding: 9px 18px; border-radius: 999px; font-size: 19px; color: #CBD5E1;
  border: 1px solid rgba(148,163,184,.28); background: rgba(255,255,255,.03); }
.by { margin-top: 46px; font-size: 22px; color: #94A3B8; letter-spacing: .06em; }"""
    return body, extra, "", 8.0


CARDS = {
    "intro": card_intro,
    "challenge": card_challenge,
    "pipeline": card_art("How it works", "A CrewAI Flow: four AI agents, checked between stages",
                         "pipeline", 1560, 10.0),
    "rag": card_art("RAG and embeddings",
                    "Answers grounded in each analysis, with their sources", "rag", 1500, 9.5),
    "phone": card_phone,
    "deployment": card_art("Deployment", "From GitHub to Railway, tested after every deploy",
                           "deployment", 1620, 8.5),
    "results": card_results,
    "outro": card_outro,
}


def record_card(page: Page, rec: Recorder, name: str) -> Path:
    body, extra, script, seconds = CARDS[name]()
    css = ui.STYLE.split("<style>", 1)[1].rsplit("</style>", 1)[0]
    page.set_content(CARD.format(fonts=FONTS, app_css=css, w=W, h=H, extra=extra, body=body,
                                 dots=dots(), script=script), wait_until="networkidle")
    page.evaluate("document.fonts.ready")
    page.wait_for_timeout(400)
    rec.start(f"card-{name}")
    page.evaluate("() => { document.body.classList.remove('paused'); if (window.go) go(); }")
    page.wait_for_timeout(int(seconds * 1000))
    return rec.stop()


# --- music and the final cut -------------------------------------------------------------------

def music(seconds: float, path: Path, rate: int = 44100) -> None:
    """A calm ambient bed: slow seventh chords, a soft bass and sparse bell notes, with reverb."""
    n = int(seconds * rate)
    t = np.arange(n) / rate
    left, right = np.zeros(n), np.zeros(n)
    chords = [[57, 64, 67, 71, 72], [53, 60, 64, 69, 72], [48, 55, 62, 64, 67],
              [55, 59, 62, 66, 69]]
    seg, fade = 8.0, 3.0

    def hz(m):
        return 440.0 * 2 ** ((m - 69) / 12)

    for k, start in enumerate(np.arange(-fade, seconds, seg)):
        a, b = max(0, int(start * rate)), min(n, int((start + seg + fade) * rate))
        if a >= b:
            continue
        tt = t[a:b]
        local = tt - start
        env = np.clip(local / fade, 0, 1) * np.clip((seg + fade - local) / fade, 0, 1)
        env = np.sin(env * np.pi / 2) ** 2
        notes = chords[k % len(chords)]
        for m in notes:
            f = hz(m)
            for det, side in ((-0.0016, left), (0.0016, right)):
                tone = (np.sin(2 * np.pi * f * (1 + det) * tt)
                        + 0.18 * np.sin(2 * np.pi * 2 * f * tt + 0.7)
                        + 0.05 * np.sin(2 * np.pi * 3 * f * tt))
                side[a:b] += 0.05 * env * tone * (1 + 0.15 * np.sin(2 * np.pi * 0.11 * tt + m))
        bass = 0.11 * env * np.sin(2 * np.pi * hz(notes[0] - 12) * tt)
        left[a:b] += bass
        right[a:b] += bass
        for j in range(4):  # bell notes, an octave up, two seconds apart
            at = start + fade + j * 2.0 + 0.5
            if at >= seconds:
                break
            i0, i1 = int(at * rate), min(n, int((at + 2.6) * rate))
            if i0 >= n:
                break
            bt = t[i0:i1] - at
            f = hz(notes[(j * 2 + k) % len(notes)] + 12)
            fm = 1.2 * np.exp(-bt * 3) * np.sin(2 * np.pi * 2 * f * bt)
            bell = np.sin(2 * np.pi * f * bt + fm)
            bell *= 0.045 * np.exp(-bt * 1.6) * np.clip(bt / 0.01, 0, 1)
            pan = 0.35 + 0.3 * (j % 2)
            left[i0:i1] += bell * (1 - pan)
            right[i0:i1] += bell * pan
    rng = np.random.default_rng(3)
    ir_t = np.arange(int(2.4 * rate)) / rate
    out = []
    for side in (left, right):
        ir = rng.standard_normal(ir_t.size) * np.exp(-ir_t / 0.55)
        ir /= np.sqrt((ir ** 2).sum())
        size = 1 << int(np.ceil(np.log2(n + ir.size)))
        wet = np.fft.irfft(np.fft.rfft(side, size) * np.fft.rfft(ir, size), size)[:n]
        out.append(0.75 * side + 0.55 * wet)
    stereo = np.stack(out, axis=1)
    stereo *= np.clip(t / 2.0, 0, 1)[:, None] * np.clip((seconds - t) / 3.5, 0, 1)[:, None]
    stereo *= 0.30 / np.abs(stereo).max()  # about -21 LUFS: a quiet bed under a talk
    with wave.open(str(path), "wb") as f:
        f.setnchannels(2)
        f.setsampwidth(2)
        f.setframerate(rate)
        f.writeframes((stereo * 32767).astype("<i2").tobytes())


def progress_line(path: Path) -> None:
    from PIL import Image
    x = np.linspace(0, 1, W)[None, :, None]
    cyan, violet = np.array([34, 211, 238]), np.array([167, 139, 250])
    rgb = (cyan * (1 - x) + violet * x).repeat(4, axis=0).astype(np.uint8)
    alpha = np.full((4, W, 1), 210, np.uint8)
    Image.fromarray(np.concatenate([rgb, alpha], axis=2), "RGBA").save(path)


def assemble(clips: list[Path], out: Path, work: Path) -> None:
    lengths = [duration(c) for c in clips]
    total = sum(lengths) - XFADE * (len(clips) - 1)
    inputs, parts = [], []
    for i, c in enumerate(clips):
        inputs += ["-i", c]
        parts.append(f"[{i}:v]fps={FPS},format=yuv420p,settb=AVTB,setpts=PTS-STARTPTS[v{i}]")
    last, offset = "v0", 0.0
    for i in range(1, len(clips)):
        offset += lengths[i - 1] - XFADE
        parts.append(f"[{last}][v{i}]xfade=transition=fade:duration={XFADE}:"
                     f"offset={offset:.3f}[x{i}]")
        last = f"x{i}"
    bar = work / "progress.png"
    progress_line(bar)
    n = len(clips)
    parts.append(f"[{n}:v]format=rgba[bar]")
    parts.append(f"[{last}][bar]overlay=x='-w+w*t/{total:.3f}':y=H-4:eval=frame,"
                 f"fade=t=in:st=0:d=0.8,fade=t=out:st={total - 1.2:.3f}:d=1.2[vout]")
    song = work / "music.wav"
    music(total, song)
    graph = work / "graph.txt"
    graph.write_text(";\n".join(parts), encoding="utf-8")
    common = ["-filter_complex_script", graph, "-map", "[vout]", "-c:v", "libx264",
              "-preset", "slow", "-crf", "17", "-pix_fmt", "yuv420p", "-movflags", "+faststart"]
    ffmpeg(*inputs, "-loop", "1", "-i", bar, "-i", song, *common, "-map", f"{n + 1}:a",
           "-c:a", "aac", "-b:a", "192k", "-shortest", "-t", f"{total:.3f}", out)
    quiet = out.with_name(out.stem + " (no music).mp4")
    ffmpeg(*inputs, "-loop", "1", "-i", bar, *common, "-t", f"{total:.3f}", quiet)
    print(f"saved {out} ({total:.1f} s, {out.stat().st_size / 1e6:.1f} MB) and {quiet.name}")


ORDER = ["intro", "challenge", "pipeline", "sign-in", "app", "rag", "phone", "deployment",
         "results", "outro"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--history", type=Path, help="a runs folder to copy (Trends' history)")
    parser.add_argument("--mock", action="store_true", help="the mock LLM (no API calls)")
    parser.add_argument("--cards-only", action="store_true", help="record just the cards")
    parser.add_argument("--reuse-cards", action="store_true",
                        help="keep the cards recorded last time (in --work)")
    parser.add_argument("--work", type=Path, default=ROOT / "runs" / "demo-video")
    parser.add_argument("--out", type=Path,
                        default=Path.home() / "Videos" / "Foresight demo.mp4")
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    args.out.parent.mkdir(parents=True, exist_ok=True)

    clips: dict[str, Path] = {}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        cards = browser.new_page(viewport={"width": W, "height": H})
        rec = Recorder(cards, args.work)
        for name in CARDS:
            kept = args.work / f"card-{name}.mp4"
            clips[name] = kept if args.reuse_cards and kept.exists() else record_card(
                cards, rec, name)
        cards.close()
        if args.cards_only:
            browser.close()
            print(json.dumps({k: round(duration(v), 1) for k, v in clips.items()}))
            return 0

        runs = Path(tempfile.mkdtemp(prefix="foresight-demo-"))
        if args.history:
            for item in args.history.iterdir():
                (shutil.copytree if item.is_dir() else shutil.copy2)(item, runs / item.name)
        env = dict(os.environ, MOCK_LLM="true" if args.mock else "false", GOOGLE_CLIENT_ID="",
                   SUPABASE_DB_URL="", SUPABASE_URL="", SUPABASE_SECRET_KEY="",
                   FORESIGHT_RUNS_DIR=str(runs),
                   FORESIGHT_MODELS_DIR=str(ROOT / "runs" / ".models"),
                   FORESIGHT_LOCAL_NAME=NAME, PYTHONUNBUFFERED="1")
        env.pop("RAILWAY_ENVIRONMENT_NAME", None)
        server = subprocess.Popen(
            [sys.executable, "-m", "streamlit", "run", "app/streamlit_app.py", "--server.port",
             str(PORT), "--server.headless", "true"], cwd=ROOT, env=env,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        page = None
        try:
            for _ in range(60):
                try:
                    urllib.request.urlopen(f"{BASE}/_stcore/health", timeout=2)
                    break
                except OSError:
                    time.sleep(1)
            page = browser.new_page(viewport={"width": W, "height": H})
            page.add_init_script(FX_JS)
            rec = Recorder(page, args.work)
            scenes: list[str] = []
            try:
                walkthrough(page, rec, scenes)
            finally:  # never leave an analysis running
                with_stop = page.get_by_role("button", name="Stop analysis")
                if page.url.endswith("/new") and with_stop.count():
                    with_stop.click()
                    page.wait_for_timeout(4000)
            clips["sign-in"], clips["app"] = map(Path, scenes)
        finally:
            server.terminate()
            browser.close()
    assemble([clips[k] for k in ORDER], args.out, args.work)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
