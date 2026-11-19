"""The adapter tests mock HTTP responses for the product page only, so the
robots.txt check is switched off for them. test_robots.py tests it directly."""
import pytest

from scraper import security


@pytest.fixture(autouse=True)
def no_robots_check(monkeypatch):
    monkeypatch.setattr(security, "ROBOTS_CHECK_ENABLED", False)
    security.robots_checker.clear()
    yield
    security.robots_checker.clear()
