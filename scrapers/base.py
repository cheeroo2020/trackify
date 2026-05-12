from __future__ import annotations

import re
from typing import Iterable, Iterator, Optional

import httpx
from selectolax.parser import HTMLParser
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from trackify.models import Listing


PRICE_RE = re.compile(r"(\d[\d,]*\.?\d{0,2})")


def parse_price(text: str | None) -> Optional[float]:
    if not text:
        return None
    text = text.replace("\xa0", " ").replace(",", "")
    m = PRICE_RE.search(text)
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


def slugify(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


class BaseScraper:
    """Subclass and implement scrape(). Use self.fetch() for HTTP with retries."""

    name: str = ""  # set by subclass; matches scrapers/<name>.py
    category: str  # "sneakers" | "ps5" | "xbox" — or per-method if mixed

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=15),
        retry=retry_if_exception_type((httpx.HTTPError,)),
    )
    def fetch(self, client: httpx.Client, url: str, **kwargs) -> httpx.Response:
        r = client.get(url, **kwargs)
        r.raise_for_status()
        return r

    def parse_html(self, response: httpx.Response) -> HTMLParser:
        return HTMLParser(response.text)

    def scrape(self, client: httpx.Client, config: dict) -> Iterable[Listing]:  # pragma: no cover
        raise NotImplementedError


def stub_scraper(name: str, note: str = ""):
    """Build a 'not yet implemented' Scraper class. Logs and yields nothing."""

    class StubScraper(BaseScraper):
        def __init__(self):
            self.name = name

        def scrape(self, client, config) -> Iterator[Listing]:
            extra = f" ({note})" if note else ""
            print(f"[scrape] {name}: stub — implement scrapers/{name}.py to enable{extra}")
            return iter(())

    StubScraper.__name__ = f"Scraper_{name}_stub"
    return StubScraper
