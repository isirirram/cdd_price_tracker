"""
robots.txt support (RFC 9309) for every storefront request the scraper makes.

Why not urllib.robotparser? It ignores the `*` and `$` wildcards, and real
store robots.txt files (Shopify's default one, for example) depend on them,
so it would allow pages the site has disallowed.

Rules applied (RFC 9309):
- The group for our user-agent token wins; otherwise the `*` group is used.
- The longest matching rule wins; on a tie, Allow wins.
- robots.txt returns 4xx (including 404)  -> everything is allowed.
- robots.txt returns 5xx / can't be reached -> everything is disallowed
  (we don't know the rules, so we don't crawl).
- Results are cached per site for ROBOTS_CACHE_SECONDS.
- Crawl-delay is honoured, and every site gets at least MIN_HOST_INTERVAL
  seconds between our requests, so we never hammer a store.
"""

import logging
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# The product token we identify as (also used in our User-Agent header)
USER_AGENT_TOKEN = "SmartPriceTracker"

ROBOTS_CACHE_SECONDS = 3600
MIN_HOST_INTERVAL = 2.0     # seconds between two requests to the same site
MAX_CRAWL_DELAY = 30.0      # never block a worker longer than this
MAX_ROBOTS_BYTES = 500 * 1024  # RFC 9309: parse at least 500 KiB


class RobotsDisallowedError(Exception):
    """The site's robots.txt does not allow us to fetch this URL."""

    def __init__(self, message: str, site: str = "unknown"):
        self.message = message
        self.site = site
        super().__init__(message)


# ----------------------------------------------------------------- parsing
@dataclass
class RobotsRules:
    rules: List[Tuple[bool, str]] = field(default_factory=list)  # (allow, pattern)
    crawl_delay: Optional[float] = None
    disallow_all: bool = False  # robots.txt unreachable -> don't crawl

    def is_allowed(self, path: str) -> bool:
        if self.disallow_all:
            return False
        if path == "/robots.txt":
            return True
        best_len, best_allow = -1, True
        for allow, pattern in self.rules:
            if _pattern_matches(pattern, path):
                length = len(pattern)
                if length > best_len or (length == best_len and allow):
                    best_len, best_allow = length, allow
        return best_allow


def _pattern_matches(pattern: str, path: str) -> bool:
    anchored = pattern.endswith("$")
    body = pattern[:-1] if anchored else pattern
    regex = "".join(".*" if ch == "*" else re.escape(ch) for ch in body)
    return re.match(regex + ("$" if anchored else ""), path) is not None


def parse_robots(text: str, agent: str = USER_AGENT_TOKEN) -> RobotsRules:
    """Return the rules that apply to `agent` from a robots.txt body."""
    agent = agent.lower()
    groups: List[Tuple[List[str], List[Tuple[bool, str]], Optional[float]]] = []
    agents: List[str] = []
    rules: List[Tuple[bool, str]] = []
    delay: Optional[float] = None
    in_rules = False

    def close_group():
        if agents:
            groups.append((agents, rules, delay))

    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        key, value = (part.strip() for part in line.split(":", 1))
        key = key.lower()

        if key == "user-agent":
            if in_rules:  # a user-agent line after rules starts a new group
                close_group()
                agents, rules, delay, in_rules = [], [], None, False
            agents.append(value.lower())
        elif key in ("allow", "disallow"):
            in_rules = True
            if value:  # an empty Disallow means "allow everything"
                rules.append((key == "allow", value))
        elif key == "crawl-delay":
            in_rules = True
            try:
                delay = float(value)
            except ValueError:
                pass
    close_group()

    def collect(match: Callable[[str], bool]) -> Optional[RobotsRules]:
        picked = [g for g in groups if any(match(a) for a in g[0])]
        if not picked:
            return None
        merged = RobotsRules()
        for _, group_rules, group_delay in picked:
            merged.rules.extend(group_rules)
            if group_delay is not None:
                merged.crawl_delay = max(merged.crawl_delay or 0, group_delay)
        return merged

    return (
        collect(lambda a: a != "*" and agent.startswith(a))
        or collect(lambda a: a == "*")
        or RobotsRules()
    )


# --------------------------------------------------------------- checking
class RobotsChecker:
    """Caches robots.txt per site and spaces out requests to each site."""

    def __init__(self, fetch: Callable[[str], Tuple[int, str]]):
        # fetch(robots_url) -> (status_code, text). Raises on network errors.
        self._fetch = fetch
        self._cache: Dict[str, Tuple[float, RobotsRules]] = {}
        self._last_request: Dict[str, float] = {}
        self._lock = threading.Lock()

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()
            self._last_request.clear()

    def rules_for(self, origin: str) -> RobotsRules:
        now = time.monotonic()
        with self._lock:
            cached = self._cache.get(origin)
            if cached and now - cached[0] < ROBOTS_CACHE_SECONDS:
                return cached[1]

        try:
            status, text = self._fetch(f"{origin}/robots.txt")
            if 200 <= status < 300:
                rules = parse_robots(text[:MAX_ROBOTS_BYTES])
            elif 400 <= status < 500:
                rules = RobotsRules()  # no robots.txt: everything allowed
            else:
                rules = RobotsRules(disallow_all=True)
        except Exception as exc:
            logger.warning("Could not read %s/robots.txt: %s", origin, exc)
            rules = RobotsRules(disallow_all=True)

        with self._lock:
            self._cache[origin] = (now, rules)
        return rules

    def check(self, url: str) -> None:
        """Raise RobotsDisallowedError if robots.txt forbids `url`;
        otherwise wait out the site's crawl delay, then return."""
        parsed = urlparse(url)
        host = parsed.netloc.lower()
        origin = f"{parsed.scheme.lower()}://{host}"
        path = parsed.path or "/"
        if parsed.query:
            path += "?" + parsed.query

        rules = self.rules_for(origin)
        if rules.disallow_all:
            raise RobotsDisallowedError(
                f"robots.txt on {host} could not be read, so the page was not fetched "
                "(sites are only crawled when their rules are known).",
                site=host,
            )
        if not rules.is_allowed(path):
            raise RobotsDisallowedError(
                f"robots.txt on {host} does not allow automated access to this page.",
                site=host,
            )

        gap = min(max(rules.crawl_delay or 0, MIN_HOST_INTERVAL), MAX_CRAWL_DELAY)
        with self._lock:
            wait = self._last_request.get(host, 0) + gap - time.monotonic()
            self._last_request[host] = time.monotonic() + max(wait, 0)
        if wait > 0:
            time.sleep(wait)
