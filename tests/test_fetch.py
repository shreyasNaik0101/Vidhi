"""Fetch stage — notification parsing, rate limiting, robots, and sha256 dedup.

No network: the HTTP getter is injected with fixture bytes, so the whole stage runs
deterministically offline (CLAUDE.md §13).
"""
from __future__ import annotations

from rbi.fetch.fetch import Fetcher, RateLimiter
from rbi.fetch.parse import parse_notifications

FIXTURE = """<html><body><table>
<tr><td><a href="/rdocs/notification/PDFs/AAA.PDF">RBI (Regional Rural Banks - IRACP) Second Amendment Directions, 2026</a></td><td>Jul 16, 2026</td></tr>
<tr><td><a href="https://rbidocs.rbi.org.in/rdocs/notification/PDFs/BBB.PDF">RBI (Local Area Banks - IRACP) Second Amendment Directions, 2026</a></td><td>Jul 16, 2026</td></tr>
<tr><td><a href="/about-us.html">About us</a></td></tr>
</table></body></html>"""

LIST = "https://www.rbi.org.in/list"
ALLOW_ALL = lambda _u: ""   # empty robots.txt -> everything allowed


def test_parse_extracts_pdf_links_titles_dates():
    links = parse_notifications(FIXTURE, base_url="https://www.rbi.org.in/")
    assert len(links) == 2                                   # the about-us link is excluded
    assert links[0].url == "https://www.rbi.org.in/rdocs/notification/PDFs/AAA.PDF"
    assert "Regional Rural Banks" in links[0].title
    assert links[0].date == "Jul 16, 2026"
    assert links[1].url.endswith("BBB.PDF")


def test_rate_limiter_waits_the_gap():
    slept, clock = [], [0.0]
    rl = RateLimiter(2.0)
    rl.wait(sleep=lambda s: slept.append(s), now=lambda: clock[0])   # first call: no wait
    clock[0] = 0.5
    rl.wait(sleep=lambda s: (slept.append(s), clock.__setitem__(0, clock[0] + s)), now=lambda: clock[0])
    assert slept[-1] == 1.5                                   # 2.0 - 0.5 elapsed


def test_dedups_identical_bytes(tmp_path):
    def http_get(url):
        return b"%PDF identical bytes" if url.endswith(".PDF") else FIXTURE.encode()
    res = Fetcher(raw_dir=tmp_path, delay=0, http_get=http_get, fetch_robots=ALLOW_ALL).fetch(LIST, limit=2)
    assert len(res["downloaded"]) == 1                       # second is a duplicate
    assert any(reason == "duplicate" for _u, reason in res["skipped"])
    assert (tmp_path / "manifest.json").exists()


def test_downloads_distinct_documents(tmp_path):
    def http_get(url):
        if url.endswith("AAA.PDF"): return b"pdf-A"
        if url.endswith("BBB.PDF"): return b"pdf-B"
        return FIXTURE.encode()
    res = Fetcher(raw_dir=tmp_path, delay=0, http_get=http_get, fetch_robots=ALLOW_ALL).fetch(LIST, limit=2)
    assert len(res["downloaded"]) == 2


def test_robots_blocks_disallowed_paths(tmp_path):
    robots = "User-agent: *\nDisallow: /rdocs/"
    http_get = lambda url: (b"x" if url.endswith(".PDF") else FIXTURE.encode())
    res = Fetcher(raw_dir=tmp_path, delay=0, http_get=http_get,
                  fetch_robots=lambda _u: robots, user_agent="test-bot").fetch(LIST, limit=2)
    assert res["downloaded"] == []
    assert all(reason == "robots" for _u, reason in res["skipped"])
