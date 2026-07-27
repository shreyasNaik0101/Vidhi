"""Download amendment PDFs politely, with sha256 dedup. HTTP is injectable."""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from urllib import robotparser
from urllib.parse import urlparse

from ..config import RAW_DIR, config
from .parse import parse_notifications


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class RateLimiter:
    """At most one action per `min_interval` seconds."""

    def __init__(self, min_interval: float):
        self.min_interval = min_interval
        self._last = 0.0

    def wait(self, *, sleep=time.sleep, now=time.monotonic) -> None:
        gap = now() - self._last
        if gap < self.min_interval:
            sleep(self.min_interval - gap)
        self._last = now()


def robots_allows(url: str, user_agent: str, fetch_robots=None) -> bool:
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    rp = robotparser.RobotFileParser()
    try:
        if fetch_robots is not None:
            rp.parse((fetch_robots(robots_url) or "").splitlines())
        else:
            rp.set_url(robots_url)
            rp.read()
    except Exception:
        return True  # can't read robots -> don't block (still rate-limited)
    return rp.can_fetch(user_agent, url)


class Fetcher:
    def __init__(self, *, raw_dir=None, user_agent=None, delay=None, http_get=None, fetch_robots=None):
        self.raw_dir = Path(raw_dir or RAW_DIR)
        self.user_agent = user_agent or config.rbi_user_agent
        self.limiter = RateLimiter(config.fetch_delay_seconds if delay is None else delay)
        self.http_get = http_get                 # (url) -> bytes; required
        self.fetch_robots = fetch_robots
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.manifest_path = self.raw_dir / "manifest.json"
        self._manifest = (
            json.loads(self.manifest_path.read_text(encoding="utf-8"))
            if self.manifest_path.exists() else {}
        )

    def _get(self, url: str, retries: int = 3) -> bytes:
        delay = 1.0
        for attempt in range(retries):
            try:
                return self.http_get(url)
            except Exception:
                if attempt == retries - 1:
                    raise
                time.sleep(delay)
                delay *= 2          # exponential backoff
        raise RuntimeError("unreachable")

    def _seen_hash(self, h: str) -> bool:
        return any(v["sha256"] == h for v in self._manifest.values())

    def fetch(self, list_url: str, *, limit: int = 0) -> dict:
        html = self._get(list_url).decode("utf-8", errors="replace")
        links = parse_notifications(html, base_url=list_url)
        if limit:
            links = links[:limit]

        downloaded, skipped = [], []
        for link in links:
            if not robots_allows(link.url, self.user_agent, self.fetch_robots):
                skipped.append((link.url, "robots")); continue
            self.limiter.wait()
            data = self._get(link.url)
            h = sha256_bytes(data)
            if self._seen_hash(h):
                skipped.append((link.url, "duplicate")); continue
            fname = f"{h[:16]}.pdf"
            (self.raw_dir / fname).write_bytes(data)
            self._manifest[link.url] = {"sha256": h, "filename": fname,
                                        "title": link.title, "date": link.date}
            downloaded.append(fname)

        self.manifest_path.write_text(json.dumps(self._manifest, indent=2), encoding="utf-8")
        return {"downloaded": downloaded, "skipped": skipped, "total_links": len(links)}
