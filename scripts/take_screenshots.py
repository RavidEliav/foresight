"""Phase 9: the README's screenshots (docs/images). Starts the app as a local developer (no
Google keys) on an empty runs folder, so it shows the reference analysis, with the real chat
(OPENAI_API_KEY from .env: one question, well under 0.1 cent; --mock for none). Saves each
page at a laptop's window size, a few pages on a phone, an analysis in progress (stopped right
after), and the sign-in page of the main app.

    python scripts/take_screenshots.py [--mock] [--out docs/images] [--sign-in URL]
"""

from __future__ import annotations

import argparse
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


def open_page(page: Page, path: str, wait_ms: int = 2500) -> None:
    page.goto(f"{BASE}/{path}")
    settle(page, wait_ms)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mock", action="store_true", help="the mock LLM (no API calls)")
    parser.add_argument("--out", type=Path, default=ROOT / "docs" / "images")
    parser.add_argument("--sign-in", default="https://foresight-ai.up.railway.app",
                        help="the app whose sign-in page is captured (empty: none)")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    runs = Path(tempfile.mkdtemp(prefix="foresight-shots-"))
    env = dict(os.environ, MOCK_LLM="true" if args.mock else "false", GOOGLE_CLIENT_ID="",
               SUPABASE_DB_URL="", SUPABASE_URL="", SUPABASE_SECRET_KEY="",
               FORESIGHT_RUNS_DIR=str(runs), FORESIGHT_MODELS_DIR=str(ROOT / "runs" / ".models"),
               PYTHONUNBUFFERED="1")
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
                shot(laptop, args.out, name)
            laptop.get_by_role("tab", name="Simulated wafer").click()
            laptop.wait_for_timeout(3500)
            shot(laptop, args.out, "findings-wafer")

            open_page(laptop, "replay", 3000)  # most of the test period, at 30 runs a second
            laptop.get_by_text("30 runs/s", exact=True).click()
            settle(laptop, 1000)
            laptop.get_by_role("button", name="Play", exact=True).click()
            laptop.wait_for_timeout(10_000)
            shot(laptop, args.out, "line-replay")
            laptop.get_by_role("button", name="Pause", exact=True).click()

            # an analysis in progress, stopped once the picture is taken
            open_page(laptop, "new")
            laptop.get_by_role("button", name="Run analysis").click()
            laptop.locator(".fs-stage.fs-done").first.wait_for(timeout=180_000)
            laptop.wait_for_timeout(2500)
            shot(laptop, args.out, "new-analysis")
            laptop.get_by_role("button", name="Stop analysis").click()
            laptop.wait_for_timeout(5000)
            laptop.close()

            phone = browser.new_page(viewport=PHONE, is_mobile=True, has_touch=True,
                                     user_agent=PHONE_AGENT, device_scale_factor=2)
            for name, path in (("phone-home", ""), ("phone-findings", "report"),
                               ("phone-model", "model")):
                open_page(phone, path, 3500)
                shot(phone, args.out, name)
            phone.close()

            if args.sign_in:
                visitor = browser.new_page(viewport=LAPTOP)
                visitor.goto(args.sign_in)
                visitor.get_by_role("button", name="Continue with Google").wait_for(timeout=90_000)
                visitor.wait_for_timeout(2000)
                shot(visitor, args.out, "sign-in")
            browser.close()
    finally:
        server.terminate()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
