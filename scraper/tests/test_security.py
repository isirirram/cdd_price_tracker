"""
Unit tests for SSRF protection, URL validation, and JSON-LD parsing (scraper/security.py).
"""

from unittest.mock import MagicMock, patch
import pytest

from scraper.exceptions import InvalidUrlError
from scraper.security import (
    extract_json_ld,
    find_product_in_json_ld,
    is_ip_private_or_restricted,
    safe_get,
    validate_safe_url,
)


def test_is_ip_private_or_restricted():
    """Verify IP classification for private, loopback, and public ranges."""
    # Loopback
    assert is_ip_private_or_restricted("127.0.0.1") is True
    assert is_ip_private_or_restricted("127.255.255.255") is True
    assert is_ip_private_or_restricted("::1") is True

    # RFC 1918 Private IPv4
    assert is_ip_private_or_restricted("10.0.0.1") is True
    assert is_ip_private_or_restricted("172.16.0.1") is True
    assert is_ip_private_or_restricted("192.168.1.1") is True

    # Cloud Metadata Link-Local
    assert is_ip_private_or_restricted("169.254.169.254") is True
    assert is_ip_private_or_restricted("fe80::1") is True

    # Broadcast / Unspecified
    assert is_ip_private_or_restricted("0.0.0.0") is True

    # Public routable IPs
    assert is_ip_private_or_restricted("8.8.8.8") is False
    assert is_ip_private_or_restricted("1.1.1.1") is False
    assert is_ip_private_or_restricted("142.250.190.46") is False


def test_validate_safe_url_blocks_unsupported_schemes():
    """Verify non-HTTP(S) schemes are rejected."""
    with pytest.raises(InvalidUrlError) as exc:
        validate_safe_url("ftp://example.com/file.txt")
    assert "scheme" in str(exc.value).lower()

    with pytest.raises(InvalidUrlError) as exc:
        validate_safe_url("file:///etc/passwd")
    assert "scheme" in str(exc.value).lower()

    with pytest.raises(InvalidUrlError) as exc:
        validate_safe_url("javascript:alert(1)")
    assert "scheme" in str(exc.value).lower()


def test_validate_safe_url_blocks_local_hostnames():
    """Verify localhost, 127.0.0.1, and internal domain names are rejected."""
    with pytest.raises(InvalidUrlError) as exc:
        validate_safe_url("http://localhost:8000/products/p1")
    assert "blocked" in str(exc.value).lower()

    with pytest.raises(InvalidUrlError) as exc:
        validate_safe_url("http://127.0.0.1:8000/products/p1")
    assert "prohibited" in str(exc.value).lower() or "blocked" in str(exc.value).lower()

    with pytest.raises(InvalidUrlError) as exc:
        validate_safe_url("http://server.internal/products/p1")
    assert "internal" in str(exc.value).lower()

    with pytest.raises(InvalidUrlError) as exc:
        validate_safe_url("http://backend.local/products/p1")
    assert "internal" in str(exc.value).lower()


@patch("socket.getaddrinfo")
def test_validate_safe_url_blocks_domains_resolving_to_private_ips(mock_getaddrinfo):
    """Verify domains resolving to 10.x or 192.168.x are rejected (DNS rebinding / SSRF)."""
    # Mock DNS resolving evil.com to 192.168.1.100
    mock_getaddrinfo.return_value = [
        (2, 1, 0, "", ("192.168.1.100", 80))
    ]

    with pytest.raises(InvalidUrlError) as exc:
        validate_safe_url("https://evil.com/products/test")
    assert "ssrf prevention" in str(exc.value).lower()


def test_validate_safe_url_allows_public_https():
    """Verify valid public HTTP/HTTPS URLs pass validation."""
    clean = validate_safe_url("https://example.com/products/item-1")
    assert clean == "https://example.com/products/item-1"


@patch("requests.Session.get")
def test_safe_get_blocks_redirect_to_private_ip(mock_session_get):
    """Verify redirects attempting to access localhost or private IPs are blocked."""
    # First response is a 302 redirecting to http://127.0.0.1/admin
    resp_redirect = MagicMock()
    resp_redirect.is_redirect = True
    resp_redirect.status_code = 302
    resp_redirect.headers = {"Location": "http://127.0.0.1/admin"}

    mock_session_get.return_value = resp_redirect

    with pytest.raises(InvalidUrlError) as exc:
        safe_get("https://public-site.com/redirect-me")
    assert "blocked" in str(exc.value).lower() or "prohibited" in str(exc.value).lower()


def test_extract_json_ld_parsing():
    """Verify Schema.org JSON-LD extraction from HTML."""
    html = """
    <html>
    <head>
      <script type="application/ld+json">
      {
        "@context": "https://schema.org/",
        "@type": "Product",
        "name": "Widget Pro",
        "offers": {"price": "99.00", "priceCurrency": "USD"}
      }
      </script>
      <script type="application/ld+json">
      [{"@type": "BreadcrumbList"}]
      </script>
    </head>
    </html>
    """
    items = extract_json_ld(html)
    assert len(items) == 2
    product = find_product_in_json_ld(items)
    assert product is not None
    assert product["name"] == "Widget Pro"


def test_find_product_in_json_ld_graph_support():
    """Verify finding product node inside @graph array."""
    data = [
        {
            "@context": "https://schema.org",
            "@graph": [
                {"@type": "Organization", "name": "Company"},
                {"@type": "Product", "name": "Graph Product", "offers": {"price": "50.0"}}
            ]
        }
    ]
    prod = find_product_in_json_ld(data)
    assert prod is not None
    assert prod["name"] == "Graph Product"


# ---------------------------------------------- NAT64 / IPv6-only networks
from unittest.mock import patch as _patch

from scraper.security import is_ip_private_or_restricted, validate_safe_url


def test_nat64_public_address_is_allowed():
    # boat-lifestyle.com seen through DNS64 on an IPv6-only hotspot
    assert is_ip_private_or_restricted("64:ff9b::17e3:2620") is False   # 23.227.38.32
    assert is_ip_private_or_restricted("64:ff9b::8.8.8.8") is False


def test_nat64_cannot_hide_private_addresses():
    assert is_ip_private_or_restricted("64:ff9b::7f00:1") is True       # 127.0.0.1
    assert is_ip_private_or_restricted("64:ff9b::a00:1") is True        # 10.0.0.1
    assert is_ip_private_or_restricted("64:ff9b::c0a8:101") is True     # 192.168.1.1
    assert is_ip_private_or_restricted("64:ff9b::a9fe:a9fe") is True    # 169.254.169.254


def test_ipv4_mapped_addresses():
    assert is_ip_private_or_restricted("::ffff:23.227.38.32") is False
    assert is_ip_private_or_restricted("::ffff:127.0.0.1") is True


def test_other_reserved_ipv6_still_blocked():
    assert is_ip_private_or_restricted("::1") is True
    assert is_ip_private_or_restricted("fe80::1") is True
    assert is_ip_private_or_restricted("fd00::1") is True


def test_store_resolving_to_nat64_passes_validation():
    fake_dns = [(10, 1, 6, "", ("64:ff9b::17e3:2620", 0, 0, 0))]
    with _patch("socket.getaddrinfo", return_value=fake_dns):
        url = "https://www.boat-lifestyle.com/products/airdopes-141"
        assert validate_safe_url(url) == url
