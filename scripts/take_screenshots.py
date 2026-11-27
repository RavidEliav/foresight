"""Phase 9: the README's screenshots (docs/images). Starts the app as a local developer (no
Google keys) on an empty runs folder, so it shows the reference analysis, with the real chat
(OPENAI_API_KEY from .env: one question and the first stages of one analysis, about a cent;
--mock for none). Saves every page at a laptop's window size in the menu's order, an analysis
with its fourth stage running (stopped right after), Trends after three more real analyses
(about 5 cents in all, 15 minutes), four phone views, and the sign-in page of the main app.
The README's diagrams come from scripts/readme_art.py.

    python scripts/take_screenshots.py [--mock] [--out docs/images] [--sign-in URL]
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from io import BytesIO
from pathlib import Path

from PIL import Image
from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
PORT = 8598
BASE = f"http://localhost:{PORT}"
LAPTOP = {"width": 1536, "height": 864}
PHONE = {"width": 390, "height": 844}
PHONE_AGENT = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
               "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")
QUESTION = "Which sensors differ most between failing and passing runs?"
PAGES = {"data-quality": "data-quality", "insights": "eda", "model": "model",
         "findings": "report"}
# The New analysis picture: stages 1-3 done, 4 running, 5 waiting (the stage tiles' classes)
STAGES_AT = """(want) => [...document.querySelectorAll('.fs-stage')]
  .map(e => [...e.classList].find(c => c !== 'fs-stage')).join() === want"""
AT_FOURTH = "fs-done,fs-done,fs-done,fs-running,fs-pending"
# Trends' history: real analyses of SECOM and two scenarios (about a cent each)
HISTORY = [None, {"kind": "planted_fault"}, {"kind": "drift"}]
NAME = "Ravid Eliav"  # the local developer's name, shown as "Hi, Ravid" (main shows yours)

# The local checkout's environment badge and the sign-in greeting: main shows neither
TIDY = """() => {
  for (const e of document.querySelectorAll('[data-testid="stSidebar"] .stMarkdownBadge'))
    if (e.innerText.startsWith('Environment')) e.closest('[data-testid="stElementContainer"]')
      .style.display = 'none';
  for (const e of document.querySelectorAll('[data-testid="stToast"]')) e.remove();
}"""


def settle(page: Page, wait_ms: int = 2500) -> None:
    """Wait until the script has finished and the charts have drawn."""
    page.wait_for_selector('[data-testid="stMainBlockContainer"]', timeout=90_000)
    page.wait_for_selector('.stApp[data-test-script-state="notRunning"]', timeout=90_000)
    page.wait_for_timeout(wait_ms)


def shot(page: Page, out: Path, name: str) -> None:
    page.evaluate(TIDY)
    page.wait_for_timeout(300)
    # WebP: a fifth of a PNG's size, and GitHub shows it
    Image.open(BytesIO(page.screenshot())).convert("RGB").save(
        out / f"{name}.webp", "WEBP", quality=90, method=6)
    print("saved", name)


def analyse(env: dict, runs: Path, recipe: dict | None) -> None:
    """One analysis from the command line, to the end (SECOM, or a scenario recipe)."""
    command = [sys.executable, "-m", "foresight.cli", "run"]
    if recipe:
        path = runs / f"recipe-{recipe['kind']}.json"
        path.write_text(json.dumps(recipe), encoding="utf-8")
        command += ["--scenario", str(path)]
    subprocess.run(command, cwd=ROOT, env=dict(env, PYTHONPATH=str(ROOT / "src")),
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=1200,
                   check=False)
    print("analysis done:", (recipe or {}).get("kind", "SECOM"))


def open_page(page: Page, path: str, wait_ms: int = 2500) -> None:
    page.goto(f"{BASE}/{path}")
    settle(page, wait_ms)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mock", action="store_true", help="the mock LLM (no API calls)")
    parser.add_argument("--out", type=Path, default=ROOT / "docs" / "images")
    parser.add_argument("--sign-in", default="https://foresight-ai.up.railway.app",
                        help="the app whose sign-in page is captured (empty: none)")
    parser.add_argument("--name", default=NAME, help="the name in the top right corner")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    runs = Path(tempfile.mkdtemp(prefix="foresight-shots-"))
    env = dict(os.environ, MOCK_LLM="true" if args.mock else "false", GOOGLE_CLIENT_ID="",
               SUPABASE_DB_URL="", SUPABASE_URL="", SUPABASE_SECRET_KEY="",
               FORESIGHT_RUNS_DIR=str(runs), FORESIGHT_MODELS_DIR=str(ROOT / "runs" / ".models"),
               FORESIGHT_LOCAL_NAME=args.name, PYTHONUNBUFFERED="1")
    env.pop("RAILWAY_ENVIRONMENT_NAME", None)
    server = subprocess.Popen([sys.executable, "-m", "streamlit", "run", "app/streamlit_app.py",
                               "--server.port", str(PORT), "--server.headless", "true"],
                              cwd=ROOT, env=env, stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL)
    try:
        for _ in range(60):
            try:
                urllib.request.urlopen(f"{BASE}/_stcore/health", timeout=2)
                break
            except OSError:
                time.sleep(1)
        with sync_playwright() as p:
            browser = p.chromium.launch()
            laptop = browser.new_page(viewport=LAPTOP)

            # Ask first, so Home lists the question
            open_page(laptop, "ask")
            chat = laptop.get_by_test_id("stChatInputTextArea")
            chat.fill(QUESTION)
            chat.press("Enter")
            laptop.get_by_test_id("stChatMessage").nth(1).wait_for(timeout=180_000)
            settle(laptop, 1500)
            shot(laptop, args.out, "ask")

            open_page(laptop, "")
            shot(laptop, args.out, "home")
            for name, path in PAGES.items():
                open_page(laptop, path, 3500)
                if name == "findings":  # the anomaly timeline and the run map
                    laptop.get_by_role("tab", name="Anomalies and run map").click()
                    laptop.wait_for_timeout(4000)
                shot(laptop, args.out, name)

            open_page(laptop, "replay", 3000)  # most of the test period, at 30 runs a second
            laptop.get_by_text("30 runs/s", exact=True).click()
            settle(laptop, 1000)
            laptop.get_by_role("button", name="Play", exact=True).click()
            laptop.wait_for_timeout(10_000)
            shot(laptop, args.out, "line-replay")
            laptop.get_by_role("button", name="Pause", exact=True).click()

            phone = browser.new_page(viewport=PHONE, is_mobile=True, has_touch=True,
                                     user_agent=PHONE_AGENT, device_scale_factor=2)
            open_page(phone, "eda", 3000)
            phone.get_by_role("tab", name="Fail rate over time").tap()
            phone.wait_for_timeout(3500)
            shot(phone, args.out, "phone-insights")
            open_page(phone, "replay", 3000)  # the whole test period, then the newest wafer
            phone.get_by_role("button", name="End", exact=True).tap()
            settle(phone, 3000)
            phone.get_by_role("tab", name="Wafer").tap()
            phone.wait_for_timeout(4000)
            shot(phone, args.out, "phone-replay")

            # an analysis in progress: three stages done, the fourth running, the fifth
            # waiting; stopped once the pictures are taken
            open_page(laptop, "new")
            laptop.get_by_role("button", name="Run analysis").click()
            try:
                laptop.locator(".fs-stage").first.wait_for(timeout=60_000)
                # the page shows a running analysis when it loads: the phone opens it now
                phone.goto(f"{BASE}/new")
                phone.locator(".fs-stage").first.wait_for(timeout=60_000)
                for page in (laptop, phone):
                    page.wait_for_function(STAGES_AT, arg=AT_FOURTH, timeout=600_000,
                                           polling=500)
                laptop.wait_for_timeout(1500)
                shot(laptop, args.out, "new-analysis")
                shot(phone, args.out, "phone-new-analysis")
            finally:  # never leave the analysis running
                laptop.get_by_role("button", name="Stop analysis").click()
                laptop.wait_for_timeout(5000)
            phone.close()

            # Trends: a few real analyses, so it has tokens and stage times to show
            for recipe in HISTORY:
                analyse(env, runs, recipe)
            open_page(laptop, "trends", 3000)
            laptop.get_by_role("tab", name="LLM tokens per run").click()
            laptop.get_by_role("tab", name="Where the run time goes").click()
            laptop.wait_for_timeout(3500)
            shot(laptop, args.out, "trends")
            laptop.close()

            if args.sign_in:
                for name, size, extra in (
                        ("sign-in", LAPTOP, {}),
                        ("phone-sign-in", PHONE, {"is_mobile": True, "has_touch": True,
                                                  "user_agent": PHONE_AGENT,
                                                  "device_scale_factor": 2})):
                    visitor = browser.new_page(viewport=size, **extra)
                    visitor.goto(args.sign_in)
                    visitor.get_by_role("button", name="Continue with Google").wait_for(
                        timeout=90_000)
                    visitor.wait_for_timeout(2000)
                    shot(visitor, args.out, name)
                    visitor.close()
            browser.close()
    finally:
        server.terminate()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
