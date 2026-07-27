"""Stage 1: fetch. Scrape the RBI notifications list and download amendment PDFs.

Respectful by construction (PROJECT_SPEC.md §6.1): one request per FETCH_DELAY_SECONDS,
a real User-Agent, robots.txt honoured, exponential backoff, and sha256 dedup so a
document is never downloaded twice. Parsing and dedup are pure/testable; the HTTP
getter is injectable so the whole stage runs against a fixture with no network.
"""
from .parse import NotificationLink, parse_notifications
from .fetch import Fetcher, RateLimiter, sha256_bytes

__all__ = ["NotificationLink", "parse_notifications", "Fetcher", "RateLimiter", "sha256_bytes"]
