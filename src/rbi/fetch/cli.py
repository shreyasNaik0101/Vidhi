"""Fetch stage CLI. `python -m rbi.fetch.cli --limit 5 --dry-run` (CLAUDE.md §13).

--dry-run lists what it would download without fetching PDFs. Live fetching hits the
real RBI site; the parsing/dedup logic is covered by tests against a fixture.
"""
from __future__ import annotations

import typer

from ..config import config
from .fetch import Fetcher
from .parse import parse_notifications

app = typer.Typer(add_completion=False, help="Fetch RBI amendment PDFs (respectfully).")

_LIST = "https://www.rbi.org.in/Scripts/NotificationUser.aspx"


def _requests_get(url: str) -> bytes:
    import requests
    r = requests.get(url, headers={"User-Agent": config.rbi_user_agent}, timeout=30)
    r.raise_for_status()
    return r.content


@app.command()
def run(
    list_url: str = typer.Option(_LIST, help="Notifications list URL."),
    limit: int = typer.Option(5, help="Fetch at most N (test small first)."),
    dry_run: bool = typer.Option(False, help="List links, download nothing."),
) -> None:
    if dry_run:
        html = _requests_get(list_url).decode("utf-8", errors="replace")
        for link in parse_notifications(html, base_url=list_url)[: limit or None]:
            typer.echo(f"{link.date or '?':>14}  {link.title[:70]}")
        return

    result = Fetcher(http_get=_requests_get).fetch(list_url, limit=limit)
    typer.echo(f"downloaded {len(result['downloaded'])}, skipped {len(result['skipped'])}, "
               f"of {result['total_links']} links")


if __name__ == "__main__":
    app()
