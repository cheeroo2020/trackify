"""Harvey Norman — harveynorman.com.au — STUB

Notes:
- Consoles: /computers-tablets/gaming/consoles
- PDPs have JSON-LD Product blocks; price often only visible after a JS
  render. Try the JSON-LD first; if absent, look for a `dataLayer.push`
  containing `productPrice`.
"""
from __future__ import annotations
from scrapers.base import stub_scraper

Scraper = stub_scraper("harvey_norman", note="consoles — JSON-LD + dataLayer fallback")
