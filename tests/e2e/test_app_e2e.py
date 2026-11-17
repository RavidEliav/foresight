"""Playwright E2E scenarios (requirements §9.2).

E1-E4 are read-only and also run against the deployed apps (marker ``deployed``).
E5-E7 start pipeline runs or LLM questions, so they only run against a local app with
MOCK_LLM=true.
"""

import csv
import random
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.e2e
deployed = pytest.mark.deployed


def _goto(page: Page, title: str) -> None:
    page.get_by_test_id("stSidebarNav").get_by_role("link", name=title).click()
    expect(page.get_by_role("heading", name=title, level=1)).to_be_visible(timeout=60_000)


@deployed
def test_e1_app_loads_and_shows_environment(app_page: Page, expected_env):
    expect(app_page.get_by_test_id("stException")).to_have_count(0)
    expect(app_page.get_by_test_id("stSidebar")).to_contain_text("Foresight")
    badge = app_page.get_by_test_id("stSidebar").get_by_text("Environment:")
    expect(badge).to_be_visible()
    if expected_env:
        expect(badge).to_contain_text(f"Environment: {expected_env}")


@deployed
def test_e2_every_result_page_shows_its_content(app_page: Page):
    _goto(app_page, "Data Quality")
    expect(app_page.get_by_text("Data Contract validation")).to_be_visible()
    expect(app_page.get_by_test_id("stMetric").filter(has_text="Failing runs")).to_be_visible()

    _goto(app_page, "EDA & Insights")
    expect(app_page.get_by_test_id("stPlotlyChart").first).to_be_visible(timeout=30_000)
    expect(app_page.get_by_text("Insights from the Data Analyst crew")).to_be_visible()
    expect(app_page.get_by_test_id("stMetric").filter(has_text="Fail rate")).to_be_visible()

    _goto(app_page, "Model")
    expect(app_page.get_by_role("heading", name="Model comparison")).to_be_visible()
    expect(app_page.get_by_test_id("stMetric").filter(has_text="PR-AUC")).to_be_visible()
    expect(app_page.get_by_test_id("stMetric").filter(has_text="Fail recall")).to_be_visible()
    expect(app_page.get_by_test_id("stDataFrame").first).to_be_visible()
    expect(app_page.get_by_text("Model card", exact=False).first).to_be_visible()
    expect(app_page.get_by_test_id("stException")).to_have_count(0)


@deployed
def test_e3_report_labels_facts_and_hypotheses_and_downloads(app_page: Page):
    _goto(app_page, "Investigation & Report")
    expect(app_page.get_by_test_id("stMetric").filter(has_text="Failing runs caught")
           ).to_be_visible()
    expect(app_page.get_by_text("Key findings")).to_be_visible()
    expect(app_page.get_by_text("confidence").first).to_be_visible()  # hypothesis cards
    expect(app_page.get_by_test_id("stPlotlyChart").first).to_be_visible(timeout=30_000)
    app_page.get_by_role("tab", name="Full investigation").click()
    for label in ("Facts", "Assumptions", "Hypotheses"):
        expect(app_page.locator("span:visible", has_text=label).first).to_be_visible()
    app_page.get_by_role("tab", name="Engineering report").click()
    with app_page.expect_download() as download:
        app_page.get_by_role("button", name="Download engineering_report.md").click()
    text = Path(download.value.path()).read_text(encoding="utf-8")
    assert download.value.suggested_filename == "engineering_report.md"
    assert text.startswith("# Engineering report") and "## Hypotheses" in text


@deployed
def test_e4_wrong_passcode_is_rejected(app_page: Page):
    app_page.get_by_label("Passcode").fill("definitely-wrong-passcode")
    app_page.get_by_role("button", name="Run pipeline").click()
    expect(app_page.get_by_text("Not authorized")).to_be_visible(timeout=30_000)
    expect(app_page.get_by_test_id("stException")).to_have_count(0)


def test_e7_ask_foresight_cites_sources_and_refuses_off_topic(app_page: Page, e2e_passcode):
    page = app_page
    _goto(page, "Ask Foresight")
    page.get_by_label("Passcode").fill(e2e_passcode)
    page.get_by_role("button", name="Unlock the chat").click()
    chat = page.get_by_test_id("stChatInputTextArea")
    expect(chat).to_be_visible(timeout=30_000)

    chat.fill("Which sensors differ between failing and passing runs?")
    chat.press("Enter")
    answers = page.get_by_test_id("stChatMessage").filter(has_text="[source:")
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


def test_e5_broken_upload_is_stopped_by_the_contract_gate(app_page: Page, tmp_path,
                                                          e2e_passcode):
    upload = tmp_path / "broken.csv"
    _broken_csv(upload)
    app_page.get_by_text("Upload a CSV").click()
    app_page.get_by_test_id("stFileUploaderDropzoneInput").set_input_files(str(upload))
    expect(app_page.get_by_text("broken.csv")).to_be_visible(timeout=30_000)
    app_page.get_by_label("Passcode").fill(e2e_passcode)
    app_page.get_by_role("button", name="Run pipeline").click()

    expect(app_page.get_by_test_id("stAlertContentError").filter(
        has_text="Some labels are not -1 (pass) or 1 (fail)")).to_be_visible(timeout=180_000)
    expect(app_page.get_by_text("Data Contract: ERROR")).to_be_visible()
    app_page.get_by_text("Technical details").click()
    expect(app_page.get_by_text("Data checks that did not pass")).to_be_visible()
    expect(app_page.get_by_text("raw_label_values").first).to_be_visible()
    expect(app_page.get_by_test_id("stException")).to_have_count(0)


def test_e6_full_run_shows_progress_then_the_new_report(app_page: Page, e2e_passcode):
    page = app_page
    page.get_by_label("Passcode").fill(e2e_passcode)
    page.get_by_role("button", name="Run pipeline").click()

    expect(page.get_by_text("Data Analyst crew")).to_be_visible(timeout=60_000)
    expect(page.get_by_test_id("stAlertContentSuccess").filter(has_text="completed")).to_be_visible(
        timeout=900_000)
    for crew in ("Data Analyst crew", "Data Scientist crew", "Investigation crew",
                 "Engineering Report crew"):
        expect(page.get_by_text(crew)).to_be_visible()

    page.get_by_role("link", name="See the results, starting with Data Quality").click()
    expect(page.get_by_role("heading", name="Data Quality", level=1)).to_be_visible()
    _goto(page, "Investigation & Report")
    caption = page.get_by_test_id("stMain").get_by_test_id("stCaptionContainer").first
    expect(caption).to_contain_text("Run ")
    expect(caption).not_to_contain_text("Reference")
    expect(page.get_by_text("Report safety checks")).to_be_visible()
