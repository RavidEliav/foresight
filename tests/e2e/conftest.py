import pytest
from playwright.sync_api import Page, expect


def open_app(page: Page, url: str) -> None:
    """Open the app and wait until Streamlit has finished its first script run."""
    page.goto(url)
    page.wait_for_selector('[data-testid="stApp"]', timeout=60_000)
    expect(page.get_by_role("heading", name="Run Pipeline")).to_be_visible(timeout=60_000)
    expect(page.get_by_test_id("stStatusWidget")).to_have_count(0, timeout=60_000)


@pytest.fixture
def app_page(page: Page, app_url: str) -> Page:
    open_app(page, app_url)
    return page
