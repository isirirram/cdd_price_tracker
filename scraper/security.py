"""
Security and validation utilities for the Smart Price Tracker Scraper module.

Enforces SSRF (Server-Side Request Forgery) protection, private IP blocking,
safe HTTP request handling, and JSON-LD structured data parsing.
"""

import ipaddress
import json
import logging
import re
import socket
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import requests

from scraper.exceptions import InvalidUrlError
from scraper.robots import USER_AGENT_TOKEN, RobotsChecker, RobotsDisallowedError

__all__ = ["RobotsDisallowedError", "safe_get", "validate_safe_url", "describe_error"]

logger = logging.getLogger(__name__)

# Maximum response size limit (5 MB) to prevent denial of service via oversized payloads
MAX_RESPONSE_SIZE = 5 * 1024 * 1024

# Hostnames explicitly blocked from automated scraping
BLOCKED_HOSTNAMES = {
    "localhost",
    "127.0.0.1",
    "::1",
    "0.0.0.0",
}

# Blocked domain suffixes for private/internal environments
BLOCKED_SUFFIXES = (
    ".local",
    ".internal",
    ".lan",
    ".localhost",
    ".home.arpa",
)


# IPv6 addresses that carry an IPv4 address inside them. On IPv6-only networks
# (many mobile hotspots, e.g. Jio) DNS64 answers with NAT64 addresses like
# 64:ff9b::17e3:2620 (= 23.227.38.32). Python marks that whole range as
# "reserved", so we check the IPv4 address inside instead. That also stops
# someone hiding a private IPv4 address (e.g. 64:ff9b::7f00:1 = 127.0.0.1).
NAT64_WELL_KNOWN = ipaddress.ip_network("64:ff9b::/96")


def _embedded_ipv4(ip):
    if ip.version != 6:
        return None
    if ip.ipv4_mapped:                       # ::ffff:a.b.c.d
        return ip.ipv4_mapped
    if ip in NAT64_WELL_KNOWN:               # 64:ff9b::a.b.c.d
        return ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF)
    return None


def is_ip_private_or_restricted(ip_str: str) -> bool:
    """
    Check if an IPv4 or IPv6 string is private, loopback, link-local,
    reserved, or otherwise internal/non-routable on the public internet.
    IPv6 addresses that wrap an IPv4 address (NAT64, IPv4-mapped) are judged
    by the IPv4 address inside them.
    """
    try:
        ip = ipaddress.ip_address(ip_str.split("%", 1)[0])
    except ValueError:
        return True  # Malformed IP strings are treated as restricted for safety

    inner = _embedded_ipv4(ip)
    if inner is not None:
        ip = inner

    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def validate_safe_url(url: str, allow_local: bool = False) -> str:
    """
    Validate that a URL is safe to fetch and protects against SSRF attacks.

    Requirements:
    1. Must use http or https scheme.
    2. Must possess a valid hostname.
    3. Hostname and resolved IP addresses must not belong to private,
       loopback, or internal networks (unless allow_local=True).

    Returns:
        The cleaned, stripped URL string.

    Raises:
        InvalidUrlError: If the URL fails scheme, hostname, or IP validation.
    """
    if not url or not isinstance(url, str):
        raise InvalidUrlError("URL cannot be empty or non-string.", site="unknown")

    clean_url = url.strip()
    try:
        parsed = urlparse(clean_url)
    except Exception as e:
        raise InvalidUrlError(f"Malformed URL: {str(e)}", site="unknown")

    scheme = (parsed.scheme or "").lower()
    if scheme not in ("http", "https"):
        raise InvalidUrlError(
            f"Invalid URL scheme '{scheme}'. Only HTTP and HTTPS URLs are permitted.",
            site=parsed.netloc or "unknown"
        )

    hostname = parsed.hostname
    if not hostname:
        raise InvalidUrlError("URL lacks a valid hostname.", site="unknown")

    hostname_lower = hostname.lower()

    if allow_local:
        return clean_url

    # Check blocked hostnames
    if hostname_lower in BLOCKED_HOSTNAMES:
        raise InvalidUrlError(
            f"Access to '{hostname}' is blocked for security (SSRF prevention).",
            site=hostname
        )

    # Check blocked internal domain suffixes
    for suffix in BLOCKED_SUFFIXES:
        if hostname_lower.endswith(suffix):
            raise InvalidUrlError(
                f"Access to internal domain '{hostname}' is blocked (SSRF prevention).",
                site=hostname
            )

    # Check if hostname itself is a literal IP address
    try:
        ip = ipaddress.ip_address(hostname_lower)
        if is_ip_private_or_restricted(str(ip)):
            raise InvalidUrlError(
                f"Access to private/internal IP address '{hostname}' is prohibited (SSRF prevention).",
                site=hostname
            )
        return clean_url
    except ValueError:
        pass  # Hostname is a domain name, proceed to DNS resolution

    # Resolve domain to check underlying IPs
    try:
        addr_info = socket.getaddrinfo(hostname, None)
        for _, _, _, _, sockaddr in addr_info:
            ip_str = sockaddr[0]
            if is_ip_private_or_restricted(ip_str):
                raise InvalidUrlError(
                    f"Destination host '{hostname}' resolves to private/internal IP '{ip_str}' (SSRF prevention).",
                    site=hostname
                )
    except socket.gaierror:
        # If DNS fails here, allow requests to handle the network error naturally,
        # unless it was an invalid host format.
        pass
    except InvalidUrlError:
        raise
    except Exception as e:
        logger.warning(f"DNS validation error for '{hostname}': {e}")

    return clean_url


# We identify ourselves honestly instead of pretending to be a browser, so
# sites can recognise us and their robots.txt rules for us apply.
USER_AGENT = (
    f"Mozilla/5.0 (compatible; {USER_AGENT_TOKEN}/1.0; "
    "+https://github.com/isirirram/cdd_price_tracker)"
)

# Tests switch this off for adapters that are tested with mocked HTTP;
# tests/test_robots.py covers the robots.txt logic itself.
ROBOTS_CHECK_ENABLED = True


def _fetch_robots(robots_url: str):
    resp = safe_get(robots_url, timeout=5, check_robots=False)
    return resp.status_code, resp.text


robots_checker = RobotsChecker(_fetch_robots)


def describe_error(exc: Exception, prefix: str) -> str:
    """Error text for a failed scrape. robots.txt refusals are shown as-is."""
    if isinstance(exc, RobotsDisallowedError):
        return exc.message
    return f"{prefix}: {exc}"


def safe_get(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 10,
    max_redirects: int = 3,
    allow_local: bool = False,
    check_robots: bool = True,
) -> requests.Response:
    """
    Perform an HTTP GET request with SSRF validation across all redirects.

    Validates initial URL and any redirect destinations against private IP spaces,
    and checks every URL (redirects included) against the site's robots.txt.

    Raises:
        RobotsDisallowedError: if robots.txt doesn't allow the URL.
    """
    clean_url = validate_safe_url(url, allow_local=allow_local)
    check_robots = check_robots and ROBOTS_CHECK_ENABLED and not allow_local

    default_headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json;q=0.8,*/*;q=0.7",
        "Accept-Language": "en-US,en;q=0.9,hi;q=0.8",
    }
    if headers:
        default_headers.update(headers)

    session = requests.Session()
    session.max_redirects = max_redirects

    # Custom redirect validation
    curr_url = clean_url
    redirects_followed = 0

    while True:
        if check_robots:
            robots_checker.check(curr_url)

        resp = session.get(
            curr_url,
            headers=default_headers,
            timeout=timeout,
            allow_redirects=False
        )

        if resp.is_redirect or resp.status_code in (301, 302, 303, 307, 308):
            redirects_followed += 1
            if redirects_followed > max_redirects:
                raise InvalidUrlError("Exceeded maximum redirects threshold.", site=url)

            location = resp.headers.get("Location")
            if not location:
                break

            # Handle relative redirects
            if location.startswith("/"):
                parsed = urlparse(curr_url)
                next_url = f"{parsed.scheme}://{parsed.netloc}{location}"
            else:
                next_url = location

            # Validate the redirect target for SSRF safety
            curr_url = validate_safe_url(next_url, allow_local=allow_local)
            continue

        return resp


def extract_json_ld(html: str) -> List[Dict[str, Any]]:
    """
    Extract all Schema.org JSON-LD scripts from HTML without external dependencies.
    """
    if not html or not isinstance(html, str):
        return []

    pattern = re.compile(
        r'<script[^>]*type=[\'"]application/ld\+json[\'"][^>]*>(.*?)</script>',
        re.DOTALL | re.IGNORECASE
    )
    results: List[Dict[str, Any]] = []

    for match in pattern.finditer(html):
        content = match.group(1).strip()
        if not content:
            continue
        try:
            data = json.loads(content)
            if isinstance(data, list):
                results.extend(data)
            elif isinstance(data, dict):
                results.append(data)
        except Exception:
            continue

    return results


def find_product_in_json_ld(json_ld_items: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Locate and return the first Schema.org Product or ProductGroup item from parsed JSON-LD nodes.
    Supports single products, @graph arrays, nested structures, and hasVariant lists.
    """
    allowed_types = {"product", "productgroup", "individualproduct", "productmodel"}

    for item in json_ld_items:
        if not isinstance(item, dict):
            continue

        # Check @graph containers
        if "@graph" in item and isinstance(item["@graph"], list):
            nested_res = find_product_in_json_ld(item["@graph"])
            if nested_res:
                return nested_res

        type_field = item.get("@type")
        is_product = False
        if isinstance(type_field, str) and type_field.lower() in allowed_types:
            is_product = True
        elif isinstance(type_field, list) and any(str(t).lower() in allowed_types for t in type_field):
            is_product = True

        if is_product:
            return item

        # Check hasVariant or mainEntity
        if "hasVariant" in item and isinstance(item["hasVariant"], list):
            variant_res = find_product_in_json_ld(item["hasVariant"])
            if variant_res:
                return variant_res
        if "mainEntity" in item and isinstance(item["mainEntity"], dict):
            main_res = find_product_in_json_ld([item["mainEntity"]])
            if main_res:
                return main_res

    return None


def extract_meta_tags(html: str) -> Dict[str, str]:
    """
    Extract OpenGraph, Twitter, and standard product meta tags from HTML.
    Returns a dictionary of normalized lowercase meta property/name -> content.
    """
    if not html or not isinstance(html, str):
        return {}

    pattern = re.compile(
        r'<meta\s+[^>]*(?:property|name)\s*=\s*[\'"]([^\'"]+)[\'"][^>]*content\s*=\s*[\'"]([^\'"]*)[\'"]'
        r'|<meta\s+[^>]*content\s*=\s*[\'"]([^\'"]*)[\'"][^>]*(?:property|name)\s*=\s*[\'"]([^\'"]+)[\'"]',
        re.IGNORECASE
    )

    meta_tags: Dict[str, str] = {}
    for match in pattern.finditer(html):
        groups = match.groups()
        if groups[0] is not None:
            key, val = groups[0], groups[1]
        else:
            val, key = groups[2], groups[3]
        if key and val is not None:
            clean_key = key.strip().lower()
            if clean_key not in meta_tags:
                meta_tags[clean_key] = val.strip()

    return meta_tags


def resolve_image_url(base_url: str, img_url: Optional[str]) -> Optional[str]:
    """
    Safely resolve relative and protocol-relative image URLs to absolute HTTP/HTTPS URLs.
    """
    if not img_url or not isinstance(img_url, str):
        return None
    clean = img_url.strip()
    if not clean:
        return None

    if clean.startswith("//"):
        parsed_base = urlparse(base_url)
        scheme = parsed_base.scheme or "https"
        resolved = f"{scheme}:{clean}"
    elif clean.startswith("http://") or clean.startswith("https://"):
        resolved = clean
    else:
        resolved = urljoin(base_url, clean)

    if resolved.startswith("http://") or resolved.startswith("https://"):
        return resolved
    return None
