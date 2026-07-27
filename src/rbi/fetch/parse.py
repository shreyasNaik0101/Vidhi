"""Parse the RBI notifications list into downloadable links (pure, testable)."""
from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urljoin

from bs4 import BeautifulSoup

# RBI notification anchors are either a direct PDF or a NotificationUser.aspx page.
_LINKY = re.compile(r"\.pdf$|NotificationUser\.aspx", re.IGNORECASE)
_DATEY = re.compile(r"[A-Z][a-z]{2,8} \d{1,2}, \d{4}")


@dataclass
class NotificationLink:
    title: str
    url: str
    date: str | None = None


def parse_notifications(html: str, base_url: str = "https://www.rbi.org.in/") -> list[NotificationLink]:
    """Extract (title, absolute url, date?) for each notification/PDF anchor."""
    soup = BeautifulSoup(html, "html.parser")
    out: list[NotificationLink] = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not _LINKY.search(href):
            continue
        url = urljoin(base_url, href)
        if url in seen:
            continue
        seen.add(url)
        title = " ".join(a.get_text().split())
        if not title:
            continue
        # a date sitting in the same row, if any
        row = a.find_parent("tr")
        m = _DATEY.search(row.get_text()) if row else None
        out.append(NotificationLink(title=title, url=url, date=m.group(0) if m else None))
    return out
