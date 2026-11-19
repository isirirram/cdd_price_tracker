"""robots.txt parsing and enforcement (RFC 9309)."""
from unittest.mock import MagicMock, patch

import pytest

from scraper import robots, security
from scraper.integrations import GenericEcommerceAdapter, ShopifyAdapter
from scraper.robots import RobotsChecker, RobotsDisallowedError, parse_robots

# Close to Shopify's default robots.txt
SHOPIFY_STYLE = """
User-agent: *
Disallow: /admin
Disallow: /cart
Disallow: /checkout
Disallow: /*/collections/*sort_by*
Disallow: /search
Allow: /search/special

User-agent: BadBot
Disallow: /
"""


@pytest.fixture(autouse=True)
def no_waiting(monkeypatch):
    monkeypatch.setattr(robots, "MIN_HOST_INTERVAL", 0)


def test_star_group_rules():
    rules = parse_robots(SHOPIFY_STYLE)
    assert rules.is_allowed("/products/snowboard")
    assert rules.is_allowed("/products/snowboard.js")
    assert not rules.is_allowed("/cart")
    assert not rules.is_allowed("/checkout/123")
    assert not rules.is_allowed("/search?q=x")


def test_wildcards_are_supported():
    rules = parse_robots(SHOPIFY_STYLE)
    # urllib.robotparser would wrongly allow this one
    assert not rules.is_allowed("/en/collections/all?sort_by=price")
    assert rules.is_allowed("/en/collections/all")


def test_longest_match_wins_and_allow_wins_ties():
    rules = parse_robots("User-agent: *\nDisallow: /search\nAllow: /search/special\n")
    assert rules.is_allowed("/search/special/1")
    tie = parse_robots("User-agent: *\nDisallow: /p\nAllow: /p\n")
    assert tie.is_allowed("/p")


def test_dollar_anchor():
    rules = parse_robots("User-agent: *\nDisallow: /*.json$\n")
    assert not rules.is_allowed("/products/x.json")
    assert rules.is_allowed("/products/x.json?view=1")


def test_our_own_group_beats_star():
    text = "User-agent: *\nDisallow: /\n\nUser-agent: SmartPriceTracker\nAllow: /products/\nDisallow: /\n"
    rules = parse_robots(text)
    assert rules.is_allowed("/products/a")
    assert not rules.is_allowed("/about")


def test_disallow_all_for_us():
    rules = parse_robots("User-agent: smartpricetracker\nDisallow: /\n")
    assert not rules.is_allowed("/products/a")


def test_empty_disallow_allows_everything():
    assert parse_robots("User-agent: *\nDisallow:\n").is_allowed("/anything")


def test_crawl_delay_is_read():
    assert parse_robots("User-agent: *\nCrawl-delay: 5\n").crawl_delay == 5


def test_missing_robots_txt_allows():
    checker = RobotsChecker(lambda url: (404, ""))
    checker.check("https://shop.example.com/products/a")  # no exception


def test_server_error_disallows():
    checker = RobotsChecker(lambda url: (503, ""))
    with pytest.raises(RobotsDisallowedError, match="could not be read"):
        checker.check("https://shop.example.com/products/a")


def test_unreachable_robots_disallows():
    def boom(url):
        raise ConnectionError("down")

    checker = RobotsChecker(boom)
    with pytest.raises(RobotsDisallowedError):
        checker.check("https://shop.example.com/products/a")


def test_robots_is_cached_per_site():
    calls = []

    def fetch(url):
        calls.append(url)
        return 200, "User-agent: *\nDisallow: /cart\n"

    checker = RobotsChecker(fetch)
    checker.check("https://shop.example.com/products/a")
    checker.check("https://shop.example.com/products/b")
    checker.check("https://other.example.com/products/a")
    assert calls == [
        "https://shop.example.com/robots.txt",
        "https://other.example.com/robots.txt",
    ]


def test_requests_to_same_site_are_spaced_out(monkeypatch):
    monkeypatch.setattr(robots, "MIN_HOST_INTERVAL", 1.5)
    slept = []
    monkeypatch.setattr(robots.time, "sleep", lambda s: slept.append(s))
    checker = RobotsChecker(lambda url: (404, ""))
    checker.check("https://shop.example.com/products/a")
    checker.check("https://shop.example.com/products/b")
    assert len(slept) == 1 and 1.0 < slept[0] <= 1.5


# ------------------------------------------- end to end through safe_get
def _response(status, text="", headers=None):
    resp = MagicMock()
    resp.status_code = status
    resp.text = text
    resp.headers = headers or {}
    resp.is_redirect = False
    return resp


def _fake_site(robots_txt, page_status=200, page_text="<html></html>"):
    fetched = []

    def get(self, url, **kwargs):
        fetched.append(url)
        if url.endswith("/robots.txt"):
            return _response(200, robots_txt)
        return _response(page_status, page_text)

    return get, fetched


@pytest.fixture
def robots_on(monkeypatch):
    monkeypatch.setattr(security, "ROBOTS_CHECK_ENABLED", True)
    monkeypatch.setattr(security, "validate_safe_url", lambda url, allow_local=False: url)
    security.robots_checker.clear()


def test_safe_get_refuses_disallowed_page(robots_on):
    get, fetched = _fake_site("User-agent: *\nDisallow: /products/\n")
    with patch("requests.Session.get", get):
        with pytest.raises(RobotsDisallowedError):
            security.safe_get("https://shop.example.com/products/a")
    # only robots.txt was requested, never the product page
    assert fetched == ["https://shop.example.com/robots.txt"]


def test_safe_get_sends_honest_user_agent(robots_on):
    seen = {}

    def get(self, url, **kwargs):
        seen[url] = kwargs["headers"]["User-Agent"]
        return _response(404 if url.endswith("robots.txt") else 200)

    with patch("requests.Session.get", get):
        security.safe_get("https://shop.example.com/products/a")
    assert all("SmartPriceTracker" in ua and "Chrome" not in ua for ua in seen.values())


def test_generic_adapter_reports_robots_refusal(robots_on):
    get, _ = _fake_site("User-agent: *\nDisallow: /\n")
    with patch("requests.Session.get", get):
        result = GenericEcommerceAdapter().scrape("https://shop.example.com/item/42")
    assert result.success is False
    assert result.error == "robots.txt on shop.example.com does not allow automated access to this page."


def test_shopify_adapter_reports_robots_refusal(robots_on):
    get, _ = _fake_site("User-agent: SmartPriceTracker\nDisallow: /\n")
    with patch("requests.Session.get", get):
        result = ShopifyAdapter().scrape("https://store.example.com/products/board")
    assert result.success is False
    assert "robots.txt" in result.error
