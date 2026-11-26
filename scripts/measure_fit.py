"""Phase 8.7: does each page's main part fit one screen? Starts the app (mock LLM, local
developer view, the reference run) and, for each page and screen size, measures the height of
the main part (everything above the first "Extended data" or "Technical details" expander)
against the screen, and saves a screenshot.

    python scripts/measure_fit.py [out_dir]
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
PORT = 8599
PAGES = {"home": "", "run": "new", "data-quality": "data-quality", "eda": "eda", "model": "model",
         "report": "report", "replay": "replay", "trends": "trends", "ask": "ask",
         "activity": "activity", "users": "users"}
# The browser window, not the screen: a laptop at 1920x1080 with 125% scaling (the Windows
# default) shows about 1536x730 under the browser bars; a desktop at 1920x1080, 1920x960.
SCREENS = {"laptop": (1536, 730), "desktop": (1920, 960), "phone": (390, 844),
           "phone-small": (390, 664)}  # an iPhone's Safari with its bars shown
PHONE_AGENT = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
               "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")
EXTRA = ("Extended data", "Technical details", "Run history", "Your runs")

# Positions from the top of the page (it is not scrolled): the bottom of the content, and the
# top of the first "extra" section, whichever comes first.
MEASURE = r"""(extra) => {
  const content = document.querySelector(
    '[data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"]');
  const bottom = content.getBoundingClientRect().bottom;
  let fold = bottom;
  for (const e of document.querySelectorAll('[data-testid="stExpander"], .fs-section')) {
    const label = e.innerText.split('\n')[0].toLowerCase();
    if (extra.some(x => label.includes(x.toLowerCase()))) {
      fold = Math.min(fold, e.getBoundingClientRect().top);
    }
  }
  return {page: Math.round(bottom), main: Math.round(fold), screen: window.innerHeight};
}"""


def main() -> int:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "logs" / "fit"
    out.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, MOCK_LLM="true", FORESIGHT_SKIP_DOTENV="true", SUPABASE_DB_URL="",
               PYTHONUNBUFFERED="1")
    server = subprocess.Popen([sys.executable, "-m", "streamlit", "run", "app/streamlit_app.py",
                               "--server.port", str(PORT), "--server.headless", "true"],
                              cwd=ROOT, env=env, stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL)
    failures = 0
    try:
        time.sleep(8)
        with sync_playwright() as p:
            browser = p.chromium.launch()
            print(f"{'page':<14}{'screen':<9}{'main':>6}{'page':>6}{'screen':>8}  fits")
            for screen, (width, height) in SCREENS.items():
                phone = screen.startswith("phone")  # the app draws its phone view
                page = browser.new_page(viewport={"width": width, "height": height},
                                        is_mobile=phone, has_touch=phone,
                                        user_agent=PHONE_AGENT if phone else None)
                for name, path in PAGES.items():
                    page.goto(f"http://localhost:{PORT}/{path}")
                    page.wait_for_selector('[data-testid="stMainBlockContainer"]',
                                           timeout=60_000)
                    page.wait_for_timeout(1500)
                    status = page.get_by_test_id("stStatusWidget")
                    if status.count():
                        status.wait_for(state="detached", timeout=60_000)
                    page.wait_for_timeout(2000)
                    m = page.evaluate(MEASURE, list(EXTRA))
                    # a phone shows the whole page on one screen (Extended data is a closed
                    # row of tabs); a computer, the main part above the extra sections
                    fits = (m["page"] if phone else m["main"]) <= m["screen"]
                    failures += not fits
                    print(f"{name:<14}{screen:<9}{m['main']:>6}{m['page']:>6}{m['screen']:>8}"
                          f"  {'yes' if fits else 'NO'}")
                    page.screenshot(path=str(out / f"{name}-{screen}.png"))
                page.close()
    finally:
        server.terminate()
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
