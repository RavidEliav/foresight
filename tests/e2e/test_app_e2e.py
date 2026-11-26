"""Playwright E2E scenarios (requirements §9.2).

The deployed apps need Google sign-in (Phase 8.6), which a test browser cannot do: against
them only the sign-in screen and the public pages are checked (marker ``deployed``). E1-E7
run in CI against a local app without sign-in, which opens as a local developer; E5-E7 start
pipeline runs or LLM questions, so they need MOCK_LLM=true.
"""

import csv
import random
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.e2e
deployed = pytest.mark.deployed


def _goto(page: Page, title: str) -> None:
    page.get_by_test_id("stSidebar").get_by_role("link", name=title, exact=True).click()
    expect(page.get_by_role("heading", name=title, level=1)).to_be_visible(timeout=60_000)


def _show_reference_run(page: Page) -> None:
    """Deployed apps may hold older runs; the read-only checks look at the committed one."""
    page.get_by_test_id("stSidebar").get_by_test_id("stSelectbox").click()
    page.get_by_role("option", name="Reference analysis · SECOM").click()
    expect(page.get_by_test_id("stSidebar").get_by_text("The reference analysis of the SECOM data")
           ).to_be_visible(timeout=30_000)


def _open_signed_out(page: Page, url: str) -> None:
    """The sign-in screen of an app with sign-in; skips for an app without (local, CI)."""
    page.goto(url)
    sign_in = page.get_by_role("button", name="Continue with Google")
    expect(sign_in.or_(page.get_by_role("heading", name="Home"))).to_be_visible(
        timeout=60_000)
    if not sign_in.is_visible():
        pytest.skip("this app has no sign-in configured (a local checkout)")


@deployed
def test_e0_visitors_see_only_the_sign_in_screen(page: Page, app_url):
    _open_signed_out(page, app_url)
    # Phase 8.10 (#75): the sign-in card says how a newcomer gets in
    expect(page.get_by_text("then request access")).to_be_visible()
    expect(page.get_by_test_id("stSidebar").get_by_role("link", name="Model")).to_have_count(0)
    page.goto(f"{app_url}/report")  # a deep link shows the sign-in screen, not the page
    expect(page.get_by_role("button", name="Continue with Google")).to_be_visible(timeout=60_000)
    expect(page.get_by_text("Key findings")).to_have_count(0)
    expect(page.get_by_test_id("stException")).to_have_count(0)


@deployed
@pytest.mark.parametrize(("path", "title", "text"), [
    ("privacy", "Privacy", "What Foresight stores"),
    ("terms", "Terms of use", "No warranty"),
])
def test_e0_privacy_and_terms_are_public(page: Page, app_url, path, title, text):
    """Google's sign-in screen links to these pages, so they open without signing in."""
    page.goto(f"{app_url}/{path}")
    expect(page.get_by_role("heading", name=title, level=1)).to_be_visible(timeout=60_000)
    expect(page.get_by_text(text)).to_be_visible()


@deployed
def test_e4_a_forged_review_link_decides_nothing(page: Page, app_url):
    page.goto(f"{app_url}/review?token=forged.token&action=approve")
    expect(page.get_by_text("This link does not work any more")).to_be_visible(timeout=60_000)
    expect(page.get_by_role("button", name="Approve")).to_have_count(0)


def test_e1_app_loads_and_shows_environment(app_page: Page, expected_env):
    expect(app_page.get_by_test_id("stException")).to_have_count(0)
    expect(app_page.get_by_test_id("stSidebar")).to_contain_text("Foresight")
    badge = app_page.get_by_test_id("stSidebar").get_by_text("Environment:")
    expect(badge).to_be_visible()
    if expected_env:
        expect(badge).to_contain_text(f"Environment: {expected_env}")


def test_e2_every_result_page_shows_its_content(app_page: Page):
    _show_reference_run(app_page)
    _goto(app_page, "Data quality")
    expect(app_page.get_by_text("Data Contract validation")).to_be_visible()
    expect(app_page.get_by_test_id("stMetric").filter(has_text="Failing runs")).to_be_visible()

    _goto(app_page, "Data insights")
    expect(app_page.get_by_test_id("stPlotlyChart").first).to_be_visible(timeout=30_000)
    expect(app_page.get_by_text("Insights from the AI data analyst")).to_be_visible()
    expect(app_page.get_by_test_id("stMetric").filter(has_text="Fail rate")).to_be_visible()

    _goto(app_page, "Model")
    _open_extended(app_page, "Model comparison")  # Extended data: closed until pressed
    expect(app_page.get_by_role("heading", name="Model comparison")).to_be_visible()
    expect(app_page.get_by_test_id("stMetric").filter(has_text="PR-AUC")).to_be_visible()
    expect(app_page.get_by_test_id("stMetric").filter(has_text="Fail recall")).to_be_visible()
    # the comparison has long descriptions: a wrapped table, every column shown (Phase 8.7)
    expect(app_page.get_by_test_id("stTable").first).to_contain_text("baseline_always_pass")
    expect(app_page.get_by_text("Model card", exact=False).first).to_be_visible()
    expect(app_page.get_by_test_id("stException")).to_have_count(0)


def _open_extended(page: Page, tab: str) -> None:
    """Extended data is a row of tabs that are all closed until one is pressed."""
    page.locator(".st-key-extended-report, .st-key-extended-model").get_by_role(
        "radio", name=tab, exact=True).click()  # a segmented control: radio buttons


def test_e3_report_labels_facts_and_hypotheses_and_downloads(app_page: Page):
    _show_reference_run(app_page)
    _goto(app_page, "Findings")
    expect(app_page.get_by_test_id("stMetric").filter(has_text="Failing runs caught")
           ).to_be_visible()
    expect(app_page.get_by_text("Key findings").last).to_be_visible()  # the first tab
    app_page.get_by_role("tab", name="Hypotheses").click()  # Phase 8.7: one tab at a time
    expect(app_page.get_by_text("confidence").first).to_be_visible()  # hypothesis cards
    app_page.get_by_role("tab", name="Anomalies and run map").click()
    expect(app_page.locator('[data-testid="stPlotlyChart"]:visible').first).to_be_visible(
        timeout=30_000)
    _open_extended(app_page, "Full investigation")
    for label in ("Facts", "Assumptions", "Hypotheses"):
        expect(app_page.locator("span:visible", has_text=label).first).to_be_visible()
    _open_extended(app_page, "Engineering report")
    with app_page.expect_download() as download:
        app_page.get_by_role("button", name="Download the engineering report").click()
    # Phase 8.10: every download is a PDF
    assert download.value.suggested_filename == (
        "Foresight - Reference analysis - Engineering report.pdf")
    assert Path(download.value.path()).read_bytes().startswith(b"%PDF")
    # Phase 8.8: the whole run in one PDF, from under the sidebar's run choice
    with app_page.expect_download(timeout=60_000) as report:
        app_page.get_by_test_id("stSidebar").get_by_role(
            "button", name="Download the full report").click()
    assert report.value.suggested_filename == "Foresight - Reference analysis - Full report.pdf"
    assert Path(report.value.path()).read_bytes().startswith(b"%PDF")


def test_e8_line_replay_plays_the_reference_test_period(app_page: Page):  # needs sign-in: CI
    _show_reference_run(app_page)
    _goto(app_page, "Line replay")
    replayed = app_page.get_by_test_id("stMetric").filter(has_text="Runs replayed")
    expect(replayed).to_contain_text("0 of 392")
    app_page.get_by_role("button", name="Play", exact=True).click()
    expect(replayed).not_to_contain_text("0 of 392", timeout=15_000)  # the line is moving
    app_page.get_by_role("button", name="End", exact=True).click()
    expect(replayed).to_contain_text("392 of 392", timeout=15_000)
    expect(app_page.get_by_test_id("stMetric").filter(has_text="Failing runs caught")
           ).to_contain_text("5 of 24")
    expect(app_page.get_by_text("Simulated die yield")).to_be_visible()  # the note: a tooltip
    expect(app_page.get_by_test_id("stException")).to_have_count(0)


# Phase 8.7: the main part of every page (above Extended data and technical details) fits the
# browser window of a laptop (1920x1080 at 125%: about 1536x730). A phone's browser gets the
# phone view (one card with tabs, lower charts), and the whole page fits an iPhone's Safari
# with its bars shown (390x664).
FIT = r"""() => {
  const content = document.querySelector(
    '[data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"]');
  let fold = content.getBoundingClientRect().bottom;
  for (const e of document.querySelectorAll('[data-testid="stExpander"], .fs-section')) {
    const label = e.innerText.split('\n')[0].toLowerCase();
    if (['extended data', 'technical details', 'run history', 'your runs']
        .some(x => label.includes(x))) { fold = Math.min(fold, e.getBoundingClientRect().top); }
  }
  return {main: fold, page: content.getBoundingClientRect().bottom,
          screen: window.innerHeight};
}"""
PHONE_AGENT = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
               "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")
PATHS = {"Home": "", "New analysis": "new", "Data quality": "data-quality", "Data insights": "eda",
         "Model": "model", "Findings": "report", "Line replay": "replay",
         "Trends": "trends", "Ask Foresight": "ask", "My activity": "activity",
         "Users & access": "users"}


@pytest.mark.parametrize(("width", "height"), [(1536, 730), (390, 664)])
def test_e9_every_page_fits_one_screen(browser, app_url, width, height):
    phone = width <= 640
    context = browser.new_context(viewport={"width": width, "height": height},
                                  is_mobile=phone, has_touch=phone,
                                  user_agent=PHONE_AGENT if phone else None)
    page = context.new_page()
    too_tall = {}
    for title, path in PATHS.items():
        page.goto(f"{app_url.rstrip('/')}/{path}")
        expect(page.get_by_role("heading", name=title, level=1)).to_be_visible(timeout=60_000)
        expect(page.get_by_test_id("stStatusWidget")).to_have_count(0, timeout=60_000)
        page.wait_for_timeout(1500)  # charts take their height
        m = page.evaluate(FIT)
        measured = m["page"] if phone else m["main"]
        if measured > m["screen"]:
            too_tall[title] = round(measured)
    assert not too_tall, f"taller than the screen at {width}x{height}: {too_tall}"
    if phone:  # the "Hi, name" menu opens with a tap (Streamlit's header lay over it)
        page.get_by_test_id("stPopover").get_by_role("button").tap()
        expect(page.get_by_text("My activity").last).to_be_visible(timeout=10_000)
    context.close()



def test_e7_ask_foresight_cites_sources_and_refuses_off_topic(app_page: Page, e2e_runs):
    page = app_page
    _goto(page, "Ask Foresight")
    chat = page.get_by_test_id("stChatInputTextArea")
    expect(chat).to_be_visible(timeout=30_000)

    chat.fill("Which sensors differ between failing and passing runs?")
    chat.press("Enter")
    # Phase 8.10: each source shows as a chip with its plain name
    answers = page.get_by_test_id("stChatMessage").filter(
        has=page.locator(".stMarkdownBadge"))
    expect(answers.first).to_be_visible(timeout=120_000)

    chat.fill("What is the capital of France?")
    chat.press("Enter")
    expect(page.get_by_test_id("stChatMessage").filter(
        has_text="Not found in this run's artifacts.")).to_be_visible(timeout=120_000)
    expect(page.get_by_test_id("stException")).to_have_count(0)


def _broken_csv(path) -> None:
    """Enough rows and all 590 sensors, but some labels are 2 (only -1 and 1 are allowed)."""
    rng = random.Random(0)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["timestamp", "label"] + [f"f_{i:03d}" for i in range(590)])
        for row in range(150):
            label = 2 if row % 10 == 0 else -1
            writer.writerow([f"2008-08-01T{row // 60:02d}:{row % 60:02d}:00", label]
                            + [round(rng.gauss(100, 10), 3) for _ in range(590)])


def test_e5_broken_upload_is_stopped_by_the_contract_gate(app_page: Page, tmp_path, e2e_runs):
    upload = tmp_path / "broken.csv"
    _broken_csv(upload)
    _goto(app_page, "New analysis")  # the app opens on Home (Phase 8.10)
    app_page.get_by_text("Upload a CSV").click()
    app_page.get_by_test_id("stFileUploaderDropzoneInput").set_input_files(str(upload))
    expect(app_page.get_by_test_id("stFileChipName").filter(has_text="broken.csv")  # the chip
           ).to_be_visible(timeout=30_000)
    app_page.get_by_role("button", name="Run analysis").click()

    expect(app_page.get_by_test_id("stAlertContentError").filter(
        has_text="Some labels are not -1 (pass) or 1 (fail)")).to_be_visible(timeout=180_000)
    expect(app_page.get_by_text("Data Contract: ERROR")).to_be_visible()
    failed_checks = app_page.get_by_text("Data checks that did not pass")
    for _ in range(3):  # the page reruns once more when the run ends; a click may be lost
        app_page.get_by_text("Technical details").click()
        try:
            expect(failed_checks).to_be_visible(timeout=5_000)
            break
        except AssertionError:
            continue
    expect(failed_checks).to_be_visible()
    expect(app_page.get_by_test_id("stCode")).to_contain_text("raw_label_values")
    expect(app_page.get_by_test_id("stException")).to_have_count(0)


def test_e6_full_run_shows_progress_then_the_new_report(app_page: Page, e2e_runs):
    page = app_page
    _goto(page, "New analysis")
    page.get_by_role("button", name="Run analysis").click()

    expect(page.get_by_text("AI data analyst")).to_be_visible(timeout=60_000)
    expect(page.get_by_test_id("stAlertContentSuccess").filter(has_text="completed")).to_be_visible(
        timeout=900_000)
    for crew in ("AI data analyst", "AI data scientist", "AI investigator", "AI report writer"):
        expect(page.get_by_text(crew)).to_be_visible()

    page.get_by_role("link", name="See the results, starting with Data quality").click()
    expect(page.get_by_role("heading", name="Data quality", level=1)).to_be_visible()
    _goto(page, "Findings")
    caption = page.get_by_test_id("stMain").get_by_test_id("stCaptionContainer").first
    expect(caption).to_contain_text("Analysis ")  # the new analysis, by its number
    expect(caption).not_to_contain_text("Reference")
    expect(page.get_by_text("Report safety checks").first).to_be_visible()
