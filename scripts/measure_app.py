"""Measure the app server's memory (RSS) while a browser visits every page and asks the chat
one question. Starts Streamlit (mock LLM) on a free port; needs psutil and Playwright.

    python scripts/measure_app.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import psutil
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
PORT = 8597
PAGES = ["", "data-quality", "eda", "model", "report", "ask"]


def rss_mb(process: psutil.Process) -> int:
    return round(sum(p.memory_info().rss for p in [process, *process.children(recursive=True)])
                 / 2**20)


def main() -> int:
    env = dict(os.environ, MOCK_LLM="true", PYTHONUNBUFFERED="1")
    server = subprocess.Popen([sys.executable, "-m", "streamlit", "run", "app/streamlit_app.py",
                               "--server.port", str(PORT), "--server.headless", "true"],
                              cwd=ROOT, env=env, stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL)
    process = psutil.Process(server.pid)
    try:
        time.sleep(8)
        print(f"{'step':<28}{'MB':>6}")
        print(f"{'started':<28}{rss_mb(process):>6}")
        with sync_playwright() as p:
            page = p.chromium.launch().new_page()
            for name in PAGES:
                page.goto(f"http://localhost:{PORT}/{name}")
                page.locator('[data-testid="stMain"] h1').first.wait_for(timeout=120_000)
                page.wait_for_timeout(4000)
                print(f"{'page /' + name:<28}{rss_mb(process):>6}")
            if passcode := os.environ.get("FS_PASS"):
                page.get_by_label("Passcode").fill(passcode)
                page.get_by_role("button", name="Unlock the chat").click()
                chat = page.get_by_test_id("stChatInputTextArea")
                chat.wait_for(timeout=30_000)
                chat.fill("What is the model's test PR-AUC?")
                chat.press("Enter")
                page.wait_for_timeout(8000)
                print(f"{'chat question':<28}{rss_mb(process):>6}")
    finally:
        for child in process.children(recursive=True):
            child.kill()
        server.kill()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
