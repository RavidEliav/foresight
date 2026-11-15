"""Generic E2E scenarios. Domain scenarios (E2, E3, E5-E7) are added in later phases."""

import pytest
from playwright.sync_api import Page, expect

pytestmark = [pytest.mark.e2e, pytest.mark.deployed]


def test_e1_app_loads_and_shows_environment(app_page: Page, expected_env):
    expect(app_page.get_by_test_id("stException")).to_have_count(0)
    expect(app_page.get_by_test_id("stSidebar")).to_contain_text("Foresight")
    badge = app_page.get_by_test_id("stSidebar").get_by_text("Environment:")
    expect(badge).to_be_visible()
    if expected_env:
        expect(badge).to_contain_text(f"Environment: {expected_env}")


def test_e4_wrong_passcode_is_rejected(app_page: Page):
    app_page.get_by_label("Passcode").fill("definitely-wrong-passcode")
    app_page.get_by_role("button", name="Run pipeline").click()
    expect(app_page.get_by_text("Not authorized")).to_be_visible(timeout=30_000)
    expect(app_page.get_by_test_id("stException")).to_have_count(0)
