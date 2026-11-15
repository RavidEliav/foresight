import pytest
import requests

pytestmark = [pytest.mark.smoke, pytest.mark.deployed]


def test_health_endpoint(app_url):
    response = requests.get(f"{app_url}/_stcore/health", timeout=30)
    assert response.status_code == 200
    assert response.text.strip() == "ok"


def test_app_page_responds(app_url):
    response = requests.get(app_url, timeout=30)
    assert response.status_code == 200
