"""Phase 9: the demo video (about 4 minutes, 1920x1080 at 60 fps, narrated, with music).

The app runs as a local developer on a copy of an analysis history (--history: a runs folder,
such as the one scripts/take_screenshots.py leaves in the temp folder), with the real LLM: one
SECOM analysis (about a cent, fast-forwarded to 18 seconds) and one question.

Chrome runs full screen on a second monitor (--screen), and ffmpeg records that screen at
60 fps through the Desktop Duplication API (ddagrab): smooth, unlike the DevTools screencast,
which gave 10 to 25 frames a second. Keep the mouse and other windows off that screen while
it records, and Windows unlocked (locked, the capture is black). Effects are drawn in the
page: a glowing cursor with click ripples, captions, smooth zooms and fast-forward badges.

Title cards (intro, the challenge, how it works, RAG, phone, deployment, results, outro) are
animated HTML pages in the app's look. The narration (NARRATION, NARRATION_HE) is ready before
the recording, so each scene waits for its line (the longer of the two languages); each
language gets its own mix. It is Ravid's own reading when there is one beside --voice-sample:
voice-lines-<lang>.* (cut into lines at its pauses) or a folder of voice-<lang>-NN.* files.
Otherwise a cloned voice (Chatterbox, scripts/demo_voice.py) or OpenAI's text to speech. The
music (scripts/demo_music.py) follows the video's sections and dips under the voice. ffmpeg
joins everything with dissolves and a progress line.

    python scripts/record_demo.py --history <runs folder> [--mock] [--out <file.mp4>]
    python scripts/record_demo.py --cards-only   (just the cards, to check their look)
"""

from __future__ import annotations

import argparse
import base64
import hashlib
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
sys.path[:0] = [str(ROOT), str(ROOT / "src"), str(ROOT / "scripts")]

from demo_music import compose  # noqa: E402

from app import ui  # noqa: E402

PORT = 8597
BASE = f"http://localhost:{PORT}"
W, H, FPS = 1920, 1080, 60
RATE = 44100         # audio samples a second
XFADE = 0.7          # seconds of each dissolve
FAST_S = 18          # the analysis, however long it takes, fills this many seconds
REPLAY_X = 10        # Line replay plays at 3 runs/s and is shown this many times faster
CHATTERBOX = Path.home() / ".venvs" / "chatterbox" / "Scripts" / "python.exe"
TTS_VOICE = "ash"    # OpenAI's voice when there is no voice sample to clone
# the cloned voice's delivery: Chatterbox's defaults. cfg_weight 0.3 reads slower and more
# deliberately, but the defaults sounded more natural
CLONE = {"exaggeration": 0.5, "cfg_weight": 0.5}
QUESTION = "Which sensors differ most between failing and passing runs?"
SIGN_IN = "https://foresight-ai.up.railway.app"
NAME = "Ravid Eliav"
FONTS = ("https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&"
         "family=Space+Grotesk:wght@500;600;700&display=swap")
CYAN, VIOLET, AMBER, GREEN = "#22D3EE", "#A78BFA", "#FBBF24", "#34D399"

# the narration, a line a scene (numbers in words, so the voice reads them right)
NARRATION = {
    "intro": "Hi, I'm Ravid Eliav, and this is Foresight: multi-agent AI that finds failing "
             "production runs early, and explains why.",
    "challenge": "In a chip fab, every production run logs hundreds of sensor signals. Only a "
                 "few runs fail, and the cause hides in the noise.",
    "pipeline": "Python computes every number, and four AI agents interpret them: a data "
                "analyst, a data scientist, an investigator and a report writer, with automatic "
                "checks between every stage.",
    "sign-in": "Access is secure: users sign in with Google, and I approve every new account.",
    "home": "The home page shows the latest analysis at a glance.",
    "analysis": "Starting an analysis takes one click. The flow checks the data, trains and "
                "compares models, investigates the riskiest runs and writes a cited report, "
                "all for under a cent.",
    "quality": "First, a data contract checks every column, so bad data never reaches the AI.",
    "insights": "The data analyst explores all five hundred and ninety sensors, and finds the "
                "ones that differ most between failing and passing runs.",
    "model": "The data scientist trains and compares models, then scores every run by risk.",
    "model-sensors": "These are the sensors the model relies on most.",
    "model-alarms": "Here are its alarms against the real outcomes.",
    "model-pr": "And the trade-off between precision and recall.",
    "findings": "The investigator flags unusual runs, and maps runs with similar sensor "
                "profiles.",
    "findings-3d": "Here, in three dimensions.",
    "findings-wafer": "And the simulated wafer shows how a run's risk could look on the die.",
    "replay": "Line replay plays the test period back run by run, with the alarms the model "
              "would have raised.",
    "trends": "Trends tracks model quality, token use and run time across every analysis.",
    "ask": "And you can ask Foresight about any analysis. It answers from the reports and the "
           "data, and cites its sources.",
    "rag": "Each analysis is split into chunks, embedded with a local model, and indexed with "
           "P G vector, so every answer stays grounded in the data.",
    "phone": "The same app works on a phone, redesigned for a small screen.",
    "deployment": "Every change goes from GitHub to Railway, and automated tests check the live "
                  "app after every deploy.",
    "results": "On the SECOM data, forty alarms catch five of the twenty-four failing runs, twice "
               "the base fail rate, and the report passed all twenty-six of its checks.",
    "outro": "Foresight is live, and the code is open. Thanks for watching.",
}

# the narration in Hebrew (numbers in words; English names spelled as they sound). The video is
# recorded once: each scene waits for the longer of its two lines.
NARRATION_HE = {
    "intro": "היי, אני רביד אליאב, וזה פורסייט: בינה מלאכותית מרובת סוכנים שמזהה מוקדם ריצות "
             "ייצור שנכשלות, ומסבירה למה.",
    "challenge": "במפעל שבבים, כל ריצת ייצור רושמת מאות אותות של חיישנים. רק מעט ריצות נכשלות, "
                 "והסיבה מסתתרת בתוך הרעש.",
    "pipeline": "פייתון מחשב את כל המספרים, וארבעה סוכני בינה מלאכותית מפרשים אותם: אנליסט "
                "נתונים, מדען נתונים, חוקר וכותב דוחות, עם בדיקות אוטומטיות בין כל שלב.",
    "sign-in": "הגישה מאובטחת: משתמשים נכנסים עם גוגל, ואני מאשר כל חשבון חדש.",
    "home": "דף הבית מציג את הניתוח האחרון במבט אחד.",
    "analysis": "ניתוח חדש מתחיל בלחיצה אחת. התהליך בודק את הנתונים, מאמן ומשווה מודלים, חוקר "
                "את הריצות המסוכנות ביותר וכותב דוח עם מקורות, והכול בפחות מחמש אגורות.",
    "quality": "קודם כול, חוזה נתונים בודק כל עמודה, כך שנתונים פגומים לא מגיעים לבינה "
               "המלאכותית.",
    "insights": "אנליסט הנתונים סורק את כל חמש מאות ותשעים החיישנים, ומוצא את אלה השונים "
                "ביותר בין ריצות שנכשלו לריצות שעברו.",
    "model": "מדען הנתונים מאמן ומשווה מודלים, ואז נותן לכל ריצה ציון סיכון.",
    "model-sensors": "אלה החיישנים שהמודל נשען עליהם הכי הרבה.",
    "model-alarms": "כאן, ההתראות שלו מול התוצאות האמיתיות.",
    "model-pr": "והאיזון בין דיוק לרגישות.",
    "findings": "החוקר מסמן ריצות חריגות, וממפה ריצות עם פרופיל חיישנים דומה.",
    "findings-3d": "וכאן, בתלת ממד.",
    "findings-wafer": "והפרוסה המדומה מראה איך הסיכון של ריצה יכול להיראות על פני השבבים.",
    "replay": "השחזור מריץ את תקופת המבחן ריצה אחר ריצה, עם ההתראות שהמודל היה מעלה.",
    "trends": "מסך המגמות עוקב אחרי איכות המודל, צריכת הטוקנים וזמן הריצה בכל הניתוחים.",
    "ask": "ואפשר לשאול את פורסייט על כל ניתוח. הוא עונה מתוך הדוחות והנתונים, ומציין את "
           "המקורות.",
    "rag": "כל ניתוח מחולק לקטעים, מומר לווקטורים במודל מקומי, ונשמר באינדקס של פי ג'י וקטור, "
           "כך שכל תשובה נשענת על הנתונים.",
    "phone": "אותה אפליקציה עובדת גם בטלפון, בעיצוב שמותאם למסך קטן.",
    "deployment": "כל שינוי עובר מגיטהאב לריילווי, ובדיקות אוטומטיות בודקות את האפליקציה החיה "
                  "אחרי כל פריסה.",
    "results": "על נתוני סיקום, ארבעים התראות תופסות חמש מתוך עשרים וארבע הריצות שנכשלו, פי "
               "שניים משיעור הכישלון הבסיסי, והדוח עבר את כל עשרים ושש הבדיקות שלו.",
    "outro": "פורסייט באוויר, והקוד פתוח. תודה שצפיתם.",
}
NARRATIONS = {"en": NARRATION, "he": NARRATION_HE}
LANGUAGE_NAMES = {"en": "", "he": " (Hebrew)"}   # added to the video's file name
# Hebrew words read with these vowel marks, not the ones Dicta guesses: the name (Dicta made
# רביד "Rabid"), 590 (with its ve), and English names and loanwords
PRONOUNCE_HE = {
    "רביד": "רָבִיד", "אליאב": "אֱלִיאָב",
    "חמש": "חֲמֵשׁ", "מאות": "מֵאוֹת", "ותשעים": "וְתִשְׁעִים",
    "פורסייט": "פוֹרְסַיְיט", "בינה": "בִּינָה", "פייתון": "פַּייתוֹן", "גוגל": "גּוּגֶל", "גיטהאב": "גִּיטְהָאבּ",
    "מגיטהאב": "מִגִּיטְהָאבּ", "לריילווי": "לְרֵיילְוֵוי", "סיקום": "סִיקוֹם",
    "הטוקנים": "הַטּוֹקֵנִים", "וקטור": "וֶקְטוֹר", "לווקטורים": "לְוֶקְטוֹרִים",
    "פי": "פִּי", "ג'י": "ג'ִי", "אנליסט": "אָנָלִיסְט", "באינדקס": "בְּאִינְדֶּקְס",
    "מודלים": "מוֹדֶלִים", "המודל": "הַמּוֹדֶל", "שהמודל": "שֶׁהַמּוֹדֶל",
}

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
    // the mouse moves about 30 times a second; the cursor glides after it at every frame
    let tx = null, ty = null, cx = 0, cy = 0;
    document.addEventListener('mousemove', ev => {
      if (tx === null) { cx = ev.clientX; cy = ev.clientY; }
      tx = ev.clientX; ty = ev.clientY; cursor.style.opacity = 1;
    }, true);
    const glide = () => {
      if (tx !== null) {
        cx += (tx - cx) * 0.4; cy += (ty - cy) * 0.4;
        cursor.style.transform = `translate(${cx}px, ${cy}px)`;
      }
      requestAnimationFrame(glide);
    };
    requestAnimationFrame(glide);
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


# the 3D run map's camera glides to the points and turns a little. It opens edge-on and far
# away; the mouse wheel zooms toward the middle of the box, which left the points behind.
GLIDE_3D = """([sel, ms]) => new Promise(done => {
  const gd = document.querySelector(sel), scene = gd._fullLayout.scene;
  const median = v => { const s = [...v].sort((a, b) => a - b); return s[s.length >> 1]; };
  const mid = {};
  for (const [k, ax] of [['x', 'xaxis'], ['y', 'yaxis'], ['z', 'zaxis']]) {
    const [lo, hi] = scene[ax].range, values = [];
    for (const t of gd._fullData || gd.data) {
      const arr = t[k];  // (Plotly 6 may keep the given data encoded: the full data is decoded)
      if (!arr || typeof arr[Symbol.iterator] !== 'function') continue;
      for (const v of arr) if (v >= lo && v <= hi) values.push(+v);
    }
    mid[k] = ((median(values) - (lo + hi) / 2) / (hi - lo)) * scene.aspectratio[k];
  }
  const c0 = scene.camera.center, e0 = scene.camera.eye, up = scene.camera.up;
  const d = {x: e0.x - c0.x, y: e0.y - c0.y, z: e0.z - c0.z}, turn = 0.75;
  const end = {x: (d.x * Math.cos(turn) - d.y * Math.sin(turn)) * 0.42,
               y: (d.x * Math.sin(turn) + d.y * Math.cos(turn)) * 0.42, z: d.z * 0.42 + 0.12};
  const t0 = performance.now();
  const step = now => {
    const p = Math.min(1, (now - t0) / ms), e = p < .5 ? 4 * p ** 3 : 1 - (-2 * p + 2) ** 3 / 2;
    const center = {x: c0.x + (mid.x - c0.x) * e, y: c0.y + (mid.y - c0.y) * e,
                    z: c0.z + (mid.z - c0.z) * e};
    const a = turn * e, k = 1 - 0.58 * e;
    const off = {x: (d.x * Math.cos(a) - d.y * Math.sin(a)) * k,
                 y: (d.x * Math.sin(a) + d.y * Math.cos(a)) * k, z: d.z * k + 0.12 * e};
    const camera = {center, up, eye: {x: center.x + off.x, y: center.y + off.y,
                                      z: center.z + off.z}};
    if (window.Plotly) window.Plotly.relayout(gd, {'scene.camera': camera});
    else scene._scene.setViewport({camera, aspectratio: scene.aspectratio});
    if (p < 1) requestAnimationFrame(step); else done(end);
  };
  requestAnimationFrame(step);
})"""


SYNC_ON = """() => new Promise(done => { const d = document.createElement('div'); d.id = 'fx-sync';
  d.style.cssText = 'position:fixed;left:0;top:0;width:12px;height:12px;background:#ff00ff;' +
    'z-index:2147483647';
  document.documentElement.appendChild(d);
  requestAnimationFrame(() => requestAnimationFrame(done)); })"""
SYNC_OFF = """() => new Promise(done => { document.getElementById('fx-sync').remove();
  requestAnimationFrame(() => requestAnimationFrame(done)); })"""


TRIM = ("silenceremove=start_periods=1:start_threshold=-48dB,areverse,"
        "silenceremove=start_periods=1:start_threshold=-48dB,areverse")
# after the model, by language. English: only a low cut (a full voice-over chain with
# compression and de-essing made it less clear). Hebrew: a gentle denoise and EQ (less mud at
# 300 Hz, more presence at 3 kHz, a little air), which sounded best of three versions
POLISH = {"en": "highpass=f=70",
          "he": "highpass=f=80,afftdn=nr=12:nf=-42:tn=1,equalizer=f=300:t=q:w=1:g=-2,"
                "equalizer=f=3000:t=q:w=1.4:g=2.5,highshelf=f=8000:g=1.5"}
# how the voice sample is prepared for the model. v2: a plain gain; v1's single-pass loudnorm
# raised the room noise in the pauses, and the clones carried it. (English lines are v1.)
SAMPLE_PREP = "v2"
# a line read by a person (Ravid recorded both narrations): only a low cut
REC_POLISH = "highpass=f=70"
SPLIT = "v2"   # how a reading is cut into lines (v2: each line tightened to its own sounds)


class Voice:
    """The narration in one language, made before the recording so each scene can wait for its
    line: a WAV a line (44.1 kHz mono, trimmed and polished), cached by its text and voice; the
    raw lines are kept, so a change to POLISH doesn't make them again."""

    def __init__(self, mode: str, sample: Path | None, work: Path, lang: str = "en"):
        self.mode, self.sample, self.dir, self.lang = mode, sample, work / "voice", lang
        self.lines = NARRATIONS[lang]
        self.dir.mkdir(parents=True, exist_ok=True)
        self.audio: dict[str, np.ndarray] = {}

    def _tag(self, key: str) -> str:
        default = CLONE == {"exaggeration": 0.5, "cfg_weight": 0.5}  # (tagged without it)
        clone = [json.dumps(CLONE)] if self.mode == "clone" and not default else []
        # (English was tagged without its language and the sample preparation)
        lang = [] if self.lang == "en" else [self.lang, SAMPLE_PREP]
        if self.lang == "he":   # a line is made again when its vowel marks change
            lang.append(json.dumps({w: v for w, v in PRONOUNCE_HE.items()
                                    if w in self.lines[key]}, ensure_ascii=False))
        tag = "|".join([*lang, self.mode, *clone,
                        str(self.sample.stat().st_size if self.sample else ""), self.lines[key]])
        return hashlib.sha1(tag.encode()).hexdigest()[:10]

    def _name(self, key: str) -> str:
        return key if self.lang == "en" else f"{self.lang}-{key}"

    def _retake(self, key: str) -> Path | None:
        """A line read again on its own: voice-<lang>-NN.* beside the reading."""
        n = list(self.lines).index(key) + 1
        folder = self.sample if self.sample.is_dir() else self.sample.parent
        found = sorted(folder.glob(f"voice-{self.lang}-{n:02d}.*"))
        return found[0] if found else None

    def _source(self, key: str) -> str:
        """For a recorded line: which recording it comes from, as a cache tag."""
        retake = self._retake(key)
        source = retake or self.sample
        tag = (f"{source.name}|{source.stat().st_size}|{source.stat().st_mtime_ns}|{key}|"
               f"{SPLIT}")
        return hashlib.sha1(tag.encode()).hexdigest()[:10]

    def _polish(self) -> str:
        """The filters after the model or the split. A recorded line is already tightened, with
        a little room before and after it: no silence trim, which cut that room off."""
        return REC_POLISH if self.mode == "recorded" else f"{TRIM},{POLISH[self.lang]}"

    def raw(self, key: str) -> Path:
        if self.mode == "recorded":
            return self.dir / f"rec-raw-{self._name(key)}-{self._source(key)}.wav"
        return self.dir / f"raw-{self._name(key)}-{self._tag(key)}.wav"

    def path(self, key: str) -> Path:
        fx = hashlib.sha1(self._polish().encode()).hexdigest()[:6]
        if self.mode == "recorded":
            return self.dir / f"rec-{self._name(key)}-{self._source(key)}-{fx}.wav"
        return self.dir / f"{self._name(key)}-{self._tag(key)}-{fx}.wav"

    def prepare(self, keys: list[str] | None = None) -> None:
        if self.mode == "none":
            return
        keys = keys or list(self.lines)
        missing = [k for k in keys if not self.raw(k).exists()]
        if missing and self.mode == "recorded":
            self._split(missing)
        elif missing:
            (self._clone if self.mode == "clone" else self._openai)(
                missing, {k: self.raw(k) for k in missing})
        for k in keys:
            if not self.path(k).exists():
                ffmpeg("-i", self.raw(k), "-af", self._polish(), "-ar", RATE,
                       "-ac", 1, self.path(k))
            x = read_wav(self.path(k))[:, 0]
            loud = x[np.abs(x) > 0.02]
            x = x * 0.1 / np.sqrt((loud ** 2).mean())  # every line at one level
            self.audio[k] = x / max(1.0, np.abs(x).max() / 0.95)
        said = sum(a.size for a in self.audio.values()) / RATE
        print(f"narration ({self.lang}, {self.mode}): {len(self.audio)} lines, {said:.0f} s",
              flush=True)

    def _split(self, keys: list[str]) -> None:
        """Cut the reading (every line in order, about 2 seconds between them) into lines; a
        retake replaces its line. A folder instead of a reading: a file for every line."""
        order = list(self.lines)
        if self.sample.is_dir():
            missing = [f"{order.index(k) + 1:02d}" for k in order if not self._retake(k)]
            if missing:
                raise SystemExit(f"{self.sample}: no voice-{self.lang}-NN file for line(s) "
                                 f"{', '.join(missing)}")
            reading, spans = np.zeros(0), [(0, 0)] * len(order)
        else:
            reading = decode(self.sample, self.dir)
            spans = speech_spans(reading)
        if len(spans) != len(order):
            found = "\n".join(f"  {i + 1:2d}. {a / RATE:6.1f} s to {b / RATE:6.1f} s "
                               f"({(b - a) / RATE:.1f} s)" for i, (a, b) in enumerate(spans))
            raise SystemExit(f"{self.sample.name}: found {len(spans)} lines, not "
                             f"{len(order)}. A pause inside a line longer than a second splits "
                             f"it; lines read without a pause join. What was found:\n{found}")
        for key in keys:
            retake = self._retake(key)
            if retake:
                audio = decode(retake, self.dir)
                parts = speech_spans(audio)
                line = tighten(audio[parts[0][0]:parts[-1][1]])
            else:
                a, b = spans[order.index(key)]
                line = tighten(reading[a:b])
            write_wav(self.raw(key), line)
            print(f"  {key}: {line.size / RATE:.1f} s" + (f" (from {retake.name})"
                                                         if retake else ""), flush=True)

    def _clone(self, keys: list[str], raw: dict[str, Path]) -> None:
        if not (self.sample and CHATTERBOX.exists()):
            raise SystemExit("--voice clone needs --voice-sample and Chatterbox in "
                             f"{CHATTERBOX.parents[1]}")
        # the model listens to the first 10 seconds: continuous speech, at a set level by a
        # plain gain (no denoise or loudnorm, whose artifacts and raised noise it copied)
        sample = self.dir / f"sample-{self.lang}-{SAMPLE_PREP}.wav"
        cut = self.dir / "sample-cut.wav"
        ffmpeg("-i", self.sample, "-af", "silenceremove=start_periods=1:start_threshold=-45dB,"
               "highpass=f=60", "-t", 12, "-ar", 24000, "-ac", 1, cut)
        x = read_wav(cut)[:, 0]
        loud = x[np.abs(x) > 0.02]
        x = x * 0.1 / np.sqrt((loud ** 2).mean())
        write_wav(sample, x / max(1.0, np.abs(x).max() / 0.95), rate=24000)
        cut.unlink()
        spec = self.dir / "spec.json"
        pronounce = PRONOUNCE_HE if self.lang == "he" else {}
        spec.write_text(json.dumps({"sample": str(sample), "language": self.lang, **CLONE,
                                    "pronounce": pronounce,
                                    "lines": [{"text": self.lines[k], "out": str(raw[k])}
                                              for k in keys]}), encoding="utf-8")
        print(f"cloning the voice for {len(keys)} lines in {self.lang} (minutes, on the CPU)",
              flush=True)
        subprocess.run([str(CHATTERBOX), str(ROOT / "scripts" / "demo_voice.py"), str(spec)],
                       check=True)

    def _openai(self, keys: list[str], raw: dict[str, Path]) -> None:
        from dotenv import load_dotenv
        from openai import OpenAI
        load_dotenv(ROOT / ".env")
        client = OpenAI()
        for k in keys:
            with client.audio.speech.with_streaming_response.create(
                    model="gpt-4o-mini-tts", voice=TTS_VOICE, input=self.lines[k],
                    instructions="A confident, warm narrator of a product demo: clear, upbeat, "
                                 "unhurried.", response_format="wav") as reply:
                reply.stream_to_file(raw[k])

    def length(self, key: str) -> float:
        return self.audio[key].size / RATE if key in self.audio else 0.0


class Narration:
    """The narration in every language: a scene waits for its longest line."""

    def __init__(self, voices: list[Voice]):
        self.voices = voices

    def length(self, key: str) -> float:
        return max((v.length(key) for v in self.voices), default=0.0)


class Recorder:
    """The screen Chrome is on, recorded by ffmpeg at 60 fps. speed(k) shows what follows k
    times faster (0 leaves it out); cue(key) starts a narration line, hold() waits for its end;
    energy(level) sets the music's energy from here."""

    def __init__(self, page: Page, work: Path, screen: int, voice: Narration):
        self.page, self.work, self.screen, self.voice = page, work, screen, voice
        self.cues: dict[str, list[tuple[float, str]]] = {}     # clip: (video time, line)
        self.energies: dict[str, list[tuple[float, int]]] = {}  # clip: (video time, level)

    def start(self, name: str, energy: int = 2) -> None:
        self.name, self.raw = name, self.work / f"{name}-raw.mkv"
        self.proc = subprocess.Popen(
            ["ffmpeg", "-y", "-loglevel", "error", "-filter_complex",
             f"ddagrab=output_idx={self.screen}:framerate={FPS}:draw_mouse=0,hwdownload,"
             "format=bgra", "-fps_mode", "cfr", "-r", str(FPS), "-c:v", "libx264", "-preset",
             "ultrafast", "-crf", "12", str(self.raw)], stdin=subprocess.PIPE)
        self.page.wait_for_timeout(1500)  # ffmpeg is capturing
        # a magenta corner, then its removal: the clip starts at the first frame without it
        self.page.evaluate(SYNC_ON)
        self.page.wait_for_timeout(400)
        self.page.evaluate(SYNC_OFF)
        self.started = time.time()
        self.marks: list[tuple[float, float]] = [(self.started, 1.0)]   # (time, speed)
        self.labels: list[tuple[float, str]] = []
        self.cues[name], self.energies[name] = [], [(0.0, energy)]
        self.voice_end = 0.0

    def speed(self, k: float) -> None:
        self.marks.append((time.time(), k))

    def label(self, text: str) -> None:
        self.labels.append((time.time(), text))

    def now(self) -> float:
        return self.video_time(time.time())

    def cue(self, key: str) -> None:
        at = self.now()
        self.cues[self.name].append((at, key))
        self.voice_end = at + self.voice.length(key)

    def hold(self, pad: float = 0.4) -> None:
        """Wait until the last line has been said, and pad seconds more (of the video)."""
        while self.now() < self.voice_end + pad:
            self.page.wait_for_timeout(80)

    def energy(self, level: int) -> None:
        self.energies[self.name].append((self.now(), level))

    def _speed_at(self, t: float) -> float:
        speed = 1.0
        for at, k in self.marks:
            if at <= t:
                speed = k
        return speed

    def video_time(self, at: float) -> float:
        """Where a moment of the recording lands in its clip, after the speed changes."""
        points = sorted({self.started, at, *[a for a, _ in self.marks if self.started < a < at]})
        return sum((b - a) / k for a, b in zip(points, points[1:], strict=False)
                   if (k := self._speed_at(a)))

    def stop(self) -> Path:
        end = time.time()
        self.page.wait_for_timeout(300)
        self.proc.communicate(b"q")
        first = sync_frame(self.raw) / FPS  # where self.started is in the raw recording
        ends = [a for a, _ in self.marks[1:]] + [end]
        parts = []
        for i, ((a, k), b) in enumerate(zip(self.marks, ends, strict=True)):
            if not k or b - a < 1 / FPS:
                continue
            part = self.work / f"{self.name}-{i:03d}.mp4"
            ffmpeg("-ss", f"{first + a - self.started:.3f}", "-to",
                   f"{first + b - self.started:.3f}", "-i", self.raw, "-vf",
                   f"setpts=(PTS-STARTPTS)/{k},fps={FPS},format=yuv420p", "-c:v", "libx264",
                   "-preset", "medium", "-crf", "14", "-an", part)
            parts.append(part)
        listing = self.work / f"{self.name}.txt"
        listing.write_text("\n".join(f"file '{p.as_posix()}'" for p in parts), encoding="utf-8")
        clip = self.work / f"{self.name}.mp4"
        ffmpeg("-f", "concat", "-safe", "0", "-i", listing, "-c", "copy", clip)
        for p in [*parts, self.raw, listing]:
            p.unlink()
        print(f"clip {self.name}: {duration(clip):.1f} s", flush=True)
        for at, text in self.labels:
            print(f"  {self.video_time(at):6.1f}  {text}", flush=True)
        for at, key in self.cues[self.name]:
            print(f"  {at:6.1f}  says {key} ({self.voice.length(key):.1f} s)", flush=True)
        (self.work / f"{self.name}.json").write_text(json.dumps(
            {"cues": self.cues[self.name], "energies": self.energies[self.name]}),
            encoding="utf-8")
        return clip


def sync_frame(raw: Path) -> int:
    """The first frame after the magenta sync mark in a raw recording."""
    out = subprocess.run(["ffmpeg", "-v", "error", "-t", "10", "-i", str(raw), "-vf",
                          "crop=6:6:3:3", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         capture_output=True, check=True).stdout
    px = np.frombuffer(out, np.uint8).reshape(-1, 36, 3).mean(axis=1)
    magenta = (px[:, 0] > 180) & (px[:, 1] < 90) & (px[:, 2] > 180)
    if not magenta.any():
        raise SystemExit("The sync mark wasn't recorded: is Chrome full screen on --screen, and "
                         "is Windows unlocked? (Locked, the screen capture is black.)")
    return int(np.flatnonzero(magenta)[-1]) + 1


def decode(path: Path, work: Path) -> np.ndarray:
    """Any audio file as 44.1 kHz mono samples."""
    out = work / "decoded.wav"
    ffmpeg("-i", path, "-ar", RATE, "-ac", 1, out)
    samples = read_wav(out)[:, 0]
    out.unlink()
    return samples


def speech_spans(x: np.ndarray, gap: float = 1.1, pad: float = 0.12) -> list[tuple[int, int]]:
    """Where someone speaks in a recording: stretches of sound at least 0.3 s long, split by
    pauses longer than ``gap`` seconds, padded a little on both sides."""
    step = RATE // 50   # 20 ms
    db = 10 * np.log10(np.array([(x[i:i + step] ** 2).mean()
                                 for i in range(0, x.size - step, step)]) + 1e-10)
    threshold = max(np.percentile(db, 10) + 12, db.max() - 45)
    spans: list[list[int]] = []
    for i in np.flatnonzero(db > threshold):
        if spans and i - spans[-1][1] <= gap * 50:
            spans[-1][1] = i
        else:
            spans.append([i, i])
    keep = [(a, b) for a, b in spans if (b - a + 1) / 50 >= 0.3]
    margin = int(pad * RATE)
    return [(max(0, a * step - margin), min(x.size, (b + 1) * step + margin)) for a, b in keep]


def tighten(x: np.ndarray, before: float = 0.12, after: float = 0.18) -> np.ndarray:
    """A recorded line from its first to its last sustained sound (5 of 8 frames within 35 dB
    of its peak, starting within 30 dB): breaths and clicks before or after it are left out."""
    step = RATE // 50
    db = 10 * np.log10(np.array([(x[i:i + step] ** 2).mean()
                                 for i in range(0, x.size - step, step)]) + 1e-10)
    loud, near = db > db.max() - 30, db > db.max() - 35

    def first(flags_loud: np.ndarray, flags_near: np.ndarray) -> int:
        for i in np.flatnonzero(flags_loud):
            if flags_near[i:i + 8].sum() >= 5:
                return int(i)
        return 0

    start = first(loud, near)
    end = db.size - first(loud[::-1], near[::-1])
    return x[max(0, start * step - int(before * RATE)):min(x.size, end * step + int(after * RATE))]


def read_wav(path: Path) -> np.ndarray:
    """A 16-bit WAV as float samples, one column a channel."""
    with wave.open(str(path), "rb") as f:
        data = np.frombuffer(f.readframes(f.getnframes()), "<i2")
        return data.reshape(-1, f.getnchannels()).astype(float) / 32768


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
    """Open a page from the menu once the line before has been said; its loading is shown 4x
    faster."""
    hand.rec.hold()
    hand.rec.label(title)
    link = page.locator('[data-testid="stSidebar"]').get_by_role("link", name=title)
    hand.click(link, 800)
    hand.rec.speed(4)
    settle(page, 1200)
    hand.rec.speed(1)


def tab(page: Page, hand: Hand, name: str, wait_ms: int = 0, line: str = "") -> None:
    """Open a tab, and say its line (after the one before)."""
    if line:
        hand.rec.hold(0.3)
    hand.click(page.get_by_role("tab", name=name), 650)
    if line:
        page.wait_for_timeout(250)
        hand.rec.cue(line)
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
    page.wait_for_timeout(600)
    rec.cue("sign-in")
    page.wait_for_timeout(600)
    hand.to(button, 1400)
    rec.hold(1.0)
    caption(page)
    page.wait_for_timeout(700)
    scenes.append(str(rec.stop()))

    page.goto(f"{BASE}/")
    settle(page, 2500)
    hand.show()
    rec.start("app")
    caption(page, "02", "Home",
            "The latest analysis at a glance, with recent analyses and questions.")
    page.wait_for_timeout(300)
    rec.cue("home")
    hand.move(560, 300, 1100)
    hand.move(1300, 300, 1500)
    rec.hold(0.8)
    caption(page)

    # a real SECOM analysis, fast-forwarded to FAST_S seconds (the music lifts meanwhile)
    nav(page, hand, "New analysis")
    caption(page, "03", "One-click analysis",
            "Five stages run as a CrewAI Flow: four AI agents, with checks in between.")
    page.wait_for_timeout(1200)
    rec.cue("analysis")
    hand.click(page.get_by_role("button", name="Run analysis"), 900)
    rec.label("analysis started")
    page.locator(".fs-stage").first.wait_for(timeout=90_000)
    page.wait_for_timeout(2500)
    hand.move(1100, 640, 900)
    page.wait_for_timeout(1200)
    page.evaluate("fxClock()")
    page.wait_for_timeout(500)
    rec.energy(3)
    fast, began = len(rec.marks), time.time()
    rec.speed(8)  # replaced below, once the analysis's length is known
    page.wait_for_function("""() => {
        const s = [...document.querySelectorAll('.fs-stage')];
        return s.length === 5 && s.every(e => e.classList.contains('fs-done')); }""",
                           timeout=900_000, polling=500)
    rec.speed(1)
    rec.marks[fast] = (rec.marks[fast][0], max(4.0, (time.time() - began) / FAST_S))
    rec.label(f"analysis done ({time.time() - began:.0f} s real, x{rec.marks[fast][1]:.1f})")
    rec.energy(2)
    page.evaluate("fxBadge(null)")
    caption(page)
    settle(page, 2500)

    nav(page, hand, "Data quality")
    caption(page, "04", "Data quality",
            "A Data Contract checks every column before any AI sees the data.")
    page.wait_for_timeout(300)
    rec.cue("quality")
    page.wait_for_timeout(2600)
    caption(page)
    zoom(page, 1.35, 360, 170, 1800)
    zoom(page, 1)

    nav(page, hand, "Data insights")
    caption(page, "05", "Data insights",
            "The AI data analyst explores 590 sensors and engineers features.")
    page.wait_for_timeout(300)
    rec.cue("insights")
    page.wait_for_timeout(2500)
    tab(page, hand, "Sensors that differ", 2500)
    caption(page)

    # every chart tab of the Model page, each with its line
    nav(page, hand, "Model")
    caption(page, "06", "Model",
            "The AI data scientist trains and compares models, then ranks the riskiest runs.")
    page.wait_for_timeout(300)
    rec.cue("model")
    hand.move(1350, 560, 1200)
    tab(page, hand, "Important sensors", 1200, "model-sensors")
    caption(page)
    tab(page, hand, "Alarms vs outcomes", 200, "model-alarms")
    zoom(page, 1.3, 1880, 320, 800)
    rec.hold(0.2)
    zoom(page, 1)
    tab(page, hand, "Precision-recall", 1500, "model-pr")

    # Findings: the anomalies and the run map, its 3D view zoomed in, then the simulated wafer
    nav(page, hand, "Findings")
    caption(page, "07", "Findings",
            "The AI investigator flags anomalies and tests hypotheses; the report cites the "
            "evidence.")
    page.wait_for_timeout(1200)
    tab(page, hand, "Anomalies and run map", 1500, "findings")
    caption(page)
    zoom(page, 1.3, 400, 1000, 1000)
    zoom(page, 1)
    rec.hold(0.2)
    hand.click(page.get_by_text("3D view", exact=True), 800)
    settle(page, 700)
    rec.cue("findings-3d")
    chart = page.locator(".st-key-card-chart-runmap .js-plotly-plot").first
    hand.to(chart, 900, 0.55, 0.45)
    page.evaluate(GLIDE_3D, [".st-key-card-chart-runmap .js-plotly-plot", 3000])
    page.wait_for_timeout(1400)
    tab(page, hand, "Simulated wafer", 2000, "findings-wafer")

    # Line replay: 3 runs/s to the end of the test period, shown REPLAY_X times faster
    nav(page, hand, "Line replay")
    caption(page, "08", "Line replay",
            "Replay the test period run by run, with the alarms the model would have raised.")
    page.wait_for_timeout(1500)
    hand.click(page.get_by_role("button", name="Play", exact=True), 800)
    rec.label("replay playing")
    page.get_by_role("button", name="Pause", exact=True).wait_for(timeout=30_000)
    page.evaluate(f"fxBadge('▶▶  {REPLAY_X}× speed')")
    rec.cue("replay")
    rec.energy(3)
    rec.speed(REPLAY_X)
    page.get_by_role("button", name="Play", exact=True).wait_for(timeout=600_000)
    page.wait_for_timeout(600)
    rec.speed(1)
    rec.energy(2)
    rec.label("replay done")
    page.evaluate("fxBadge(null)")
    caption(page)
    hand.move(1300, 700, 1200)
    page.wait_for_timeout(1500)

    nav(page, hand, "Trends")
    caption(page, "09", "Trends",
            "Model quality, LLM tokens and run time across every analysis.")
    page.wait_for_timeout(300)
    rec.cue("trends")
    page.wait_for_timeout(2000)
    tab(page, hand, "LLM tokens per run", 2400)
    tab(page, hand, "Where the run time goes", 2400)
    caption(page)

    nav(page, hand, "Ask Foresight")
    caption(page, "10", "Ask Foresight",
            "Answers from the analysis's reports and data, with their sources.")
    page.wait_for_timeout(300)
    rec.cue("ask")
    page.wait_for_timeout(2600)
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
    page.wait_for_timeout(6000)
    rec.hold(0.8)
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


VOICE_AT = 0.7   # seconds into a card before its line starts
# the music's energy in each part of the video (1 calm, 2 the groove, 3 the full band)
ENERGY = {"intro": 1, "challenge": 2, "pipeline": 2, "sign-in": 2, "app": 2, "rag": 3,
          "phone": 3, "deployment": 3, "results": 3, "outro": 1}


def record_card(page: Page, rec: Recorder, name: str) -> Path:
    body, extra, script, seconds = CARDS[name]()
    seconds = max(seconds, VOICE_AT + rec.voice.length(name) + 1.4)
    css = ui.STYLE.split("<style>", 1)[1].rsplit("</style>", 1)[0]
    page.set_content(CARD.format(fonts=FONTS, app_css=css, w=W, h=H, extra=extra, body=body,
                                 dots=dots(), script=script), wait_until="networkidle")
    page.evaluate("document.fonts.ready")
    page.wait_for_timeout(400)
    rec.start(f"card-{name}", ENERGY[name])
    page.evaluate("() => { document.body.classList.remove('paused'); if (window.go) go(); }")
    page.wait_for_timeout(int(VOICE_AT * 1000))
    rec.cue(name)
    page.wait_for_timeout(int((seconds - VOICE_AT) * 1000))
    return rec.stop()


def full_screen(page: Page, left: int) -> None:
    """Chrome's window full screen on the monitor that starts at x = left."""
    cdp = page.context.new_cdp_session(page)
    window = cdp.send("Browser.getWindowForTarget")["windowId"]
    cdp.send("Browser.setWindowBounds", {"windowId": window, "bounds": {"left": left, "top": 0}})
    page.wait_for_timeout(400)
    cdp.send("Browser.setWindowBounds", {"windowId": window,
                                         "bounds": {"windowState": "fullscreen"}})
    page.wait_for_timeout(4500)  # Chrome's "Press Esc to exit full screen" fades away
    size = page.evaluate("[innerWidth, innerHeight]")
    if size != [W, H]:
        raise SystemExit(f"Chrome is {size[0]}x{size[1]}, not {W}x{H}: is that screen "
                         f"{W}x{H} at 100% scaling?")


# --- the sound and the final cut ---------------------------------------------------------------

def lufs(samples: np.ndarray, work: Path) -> float:
    """Integrated loudness (EBU R128), measured by ffmpeg."""
    path = work / "measure.wav"
    write_wav(path, samples)
    out = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-af",
                          "ebur128=framelog=quiet", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    path.unlink()
    return float(out.rsplit("I:", 1)[1].split("LUFS")[0])


def write_wav(path: Path, samples: np.ndarray, rate: int = RATE) -> None:
    stereo = samples if samples.ndim == 2 else np.stack([samples, samples], axis=1)
    with wave.open(str(path), "wb") as f:
        f.setnchannels(2)
        f.setsampwidth(2)
        f.setframerate(rate)
        f.writeframes((np.clip(stereo, -1, 1) * 32767).astype("<i2").tobytes())


def limit(x: np.ndarray, knee: float = 0.8) -> np.ndarray:
    """A soft limiter: peaks above the knee are rounded off below 1."""
    over = np.abs(x) > knee
    y = x.copy()
    y[over] = np.sign(x[over]) * (knee + (1 - knee) * np.tanh((np.abs(x[over]) - knee)
                                                               / (1 - knee)))
    return y


def soundtrack(starts: list[float], meta: list[dict], music: np.ndarray, voice: Voice | None,
               work: Path) -> Path:
    """The music with the narration over it, the music dipping 10 dB under the voice (no
    voice: the music alone)."""
    music = music * 10 ** ((-19 - lufs(music, work)) / 20)   # the music alone at -19 LUFS
    if voice is None:
        bare = work / "music-only.wav"
        write_wav(bare, limit(music))
        return bare
    n = music.shape[0]
    speech, talking = np.zeros(n), np.zeros(n // 441 + 1)   # talking: 100 steps a second
    for i, m in enumerate(meta):
        for at, key in m["cues"]:
            if key not in voice.audio:
                continue
            a = int((starts[i] + at) * RATE)
            line = voice.audio[key][:max(0, n - a)]
            speech[a:a + line.size] += line
            talking[max(0, a // 441 - 20):(a + line.size) // 441 + 45] = 1
    ease = np.hanning(31)
    talking = np.convolve(talking, ease / ease.sum(), "same")
    duck = 1 - (1 - 10 ** (-10 / 20)) * np.interp(np.arange(n) / 441, np.arange(talking.size),
                                                  talking)
    mixed = music * duck[:, None]
    if speech.any():
        speech *= 10 ** ((-16 - lufs(speech, work)) / 20)   # the voice at -16 LUFS
        mixed += speech[:, None]
    full = work / f"mix-{voice.lang}.wav"
    write_wav(full, limit(mixed))
    print(f"sound ({voice.lang}): {lufs(limit(mixed), work):.1f} LUFS", flush=True)
    return full


def progress_line(path: Path) -> None:
    from PIL import Image
    x = np.linspace(0, 1, W)[None, :, None]
    cyan, violet = np.array([34, 211, 238]), np.array([167, 139, 250])
    rgb = (cyan * (1 - x) + violet * x).repeat(4, axis=0).astype(np.uint8)
    alpha = np.full((4, W, 1), 210, np.uint8)
    Image.fromarray(np.concatenate([rgb, alpha], axis=2), "RGBA").save(path)


def clip_name(part: str) -> str:
    return part if part in ("sign-in", "app") else f"card-{part}"


def assemble(work: Path, out: Path, voices: list[Voice]) -> None:
    clips = [work / f"{clip_name(k)}.mp4" for k in ORDER]
    meta = [json.loads((work / f"{clip_name(k)}.json").read_text(encoding="utf-8"))
            for k in ORDER]
    lengths = [duration(c) for c in clips]
    starts = [sum(lengths[:i]) - XFADE * i for i in range(len(clips))]
    total = sum(lengths) - XFADE * (len(clips) - 1)
    inputs, parts = [], []
    for i, c in enumerate(clips):
        inputs += ["-i", c]
        parts.append(f"[{i}:v]fps={FPS},format=yuv420p,settb=AVTB,setpts=PTS-STARTPTS[v{i}]")
    last = "v0"
    for i in range(1, len(clips)):
        parts.append(f"[{last}][v{i}]xfade=transition=fade:duration={XFADE}:"
                     f"offset={starts[i]:.3f}[x{i}]")
        last = f"x{i}"
    bar = work / "progress.png"
    progress_line(bar)
    n = len(clips)
    parts.append(f"[{n}:v]format=rgba[bar]")
    parts.append(f"[{last}][bar]overlay=x='-w+w*t/{total:.3f}':y=H-4:eval=frame,"
                 f"fade=t=in:st=0:d=0.8,fade=t=out:st={total - 1.2:.3f}:d=1.2[vout]")
    graph = work / "graph.txt"
    graph.write_text(";\n".join(parts), encoding="utf-8")
    video = work / "video.mp4"
    ffmpeg(*inputs, "-loop", "1", "-i", bar, "-filter_complex_script", graph, "-map", "[vout]",
           "-c:v", "libx264", "-preset", "medium", "-crf", "17", "-pix_fmt", "yuv420p",
           "-t", f"{total:.3f}", video)
    sections = sorted((starts[i] + at, level) for i, m in enumerate(meta)
                      for at, level in m["energies"])
    song = work / "music.wav"
    compose(sections, total, song)   # its energy follows the video
    music = read_wav(song)
    versions = [(v, out.with_name(out.stem + LANGUAGE_NAMES[v.lang] + out.suffix))
                for v in voices if v.audio]
    versions.append((None, out.with_name(out.stem + " (no narration)" + out.suffix)))
    for voice, path in versions:
        sound = soundtrack(starts, meta, music, voice, work)
        ffmpeg("-i", video, "-i", sound, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a",
               "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", path)
        print(f"saved {path} ({total:.1f} s, {path.stat().st_size / 1e6:.1f} MB)", flush=True)


ORDER = ["intro", "challenge", "pipeline", "sign-in", "app", "rag", "phone", "deployment",
         "results", "outro"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--history", type=Path, help="a runs folder to copy (Trends' history)")
    parser.add_argument("--mock", action="store_true", help="the mock LLM (no API calls)")
    parser.add_argument("--cards-only", action="store_true", help="record just the cards")
    parser.add_argument("--reuse-cards", action="store_true",
                        help="keep the cards recorded last time (in --work)")
    parser.add_argument("--assemble-only", action="store_true",
                        help="only join the clips recorded last time, with new sound")
    parser.add_argument("--screen", type=int, default=1,
                        help="the monitor to record (0 is the main one)")
    parser.add_argument("--screen-x", type=int, default=W, help="where that monitor starts")
    parser.add_argument("--voice", choices=["clone", "openai", "none"],
                        help="the narration (default: clone if there is a voice sample)")
    parser.add_argument("--voice-sample", type=Path,
                        default=Path.home() / "Videos" / "voice-sample.m4a")
    parser.add_argument("--voice-sample-he", type=Path,
                        default=Path.home() / "Videos" / "voice-sample-he.m4a",
                        help="a Hebrew sample of the voice (else the English one is used)")
    parser.add_argument("--languages", default="en,he", help="the narrations to make")
    parser.add_argument("--voice-only", action="store_true", help="only make the narration")
    parser.add_argument("--lines", help="with --voice-only: just these lines (comma-separated)")
    parser.add_argument("--work", type=Path, default=ROOT / "runs" / "demo-video")
    parser.add_argument("--out", type=Path,
                        default=Path.home() / "Videos" / "Foresight demo.mp4")
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    sample = args.voice_sample if args.voice_sample.exists() else None
    mode = args.voice or ("clone" if sample else "openai")
    voices = []
    for lang in args.languages.split(","):
        # read by a person, if there is a reading: voice-lines-<lang>.* in the sample's folder,
        # or a folder under it with a file for every line (voice-<lang>-01.* and on)
        videos = args.voice_sample.parent
        reading = sorted(videos.glob(f"voice-lines-{lang}.*"))
        reading = [r for r in reading if r.suffix.lower() in (".m4a", ".wav", ".mp3")]
        if not reading:
            firsts = sorted(videos.rglob(f"voice-{lang}-01.*"))
            reading = [f.parent for f in firsts
                       if len(list(f.parent.glob(f"voice-{lang}-??.*"))) >= len(NARRATION)]
        if reading and not args.voice:
            voices.append(Voice("recorded", reading[0], args.work, lang))
        else:
            own = args.voice_sample_he if lang == "he" and args.voice_sample_he.exists() else None
            voices.append(Voice(mode, own or sample, args.work, lang))
        voices[-1].prepare(args.lines.split(",") if args.voice_only and args.lines else None)
    voice = Narration(voices)
    if args.voice_only:
        return 0
    if args.assemble_only:
        assemble(args.work, args.out, voices)
        return 0

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False, ignore_default_args=["--enable-automation"],
            args=[f"--window-position={args.screen_x},0", f"--window-size={W},{H}",
                  "--force-device-scale-factor=1", "--hide-scrollbars",
                  "--disable-backgrounding-occluded-windows", "--disable-renderer-backgrounding",
                  "--disable-background-timer-throttling"])
        page = browser.new_context(no_viewport=True).new_page()
        page.add_init_script(FX_JS)
        full_screen(page, args.screen_x)
        rec = Recorder(page, args.work, args.screen, voice)
        for name in CARDS:
            kept = args.work / f"card-{name}"
            if not (args.reuse_cards and kept.with_suffix(".json").exists()):
                record_card(page, rec, name)
        if args.cards_only:
            browser.close()
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
        try:
            for _ in range(60):
                try:
                    urllib.request.urlopen(f"{BASE}/_stcore/health", timeout=2)
                    break
                except OSError:
                    time.sleep(1)
            scenes: list[str] = []
            try:
                walkthrough(page, rec, scenes)
            finally:  # never leave an analysis running
                with_stop = page.get_by_role("button", name="Stop analysis")
                if page.url.endswith("/new") and with_stop.count():
                    with_stop.click()
                    page.wait_for_timeout(4000)
        finally:
            server.terminate()
            browser.close()
    assemble(args.work, args.out, voices)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
