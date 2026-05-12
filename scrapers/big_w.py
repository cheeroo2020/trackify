"""Big W — bigw.com.au — STUB

Notes:
- Consoles category: /toys/gaming
- PDPs expose a JSON-LD Product block.
- May require an Akamai cookie challenge on first request; usually OK once
  the session is established.
"""
from __future__ import annotations
from scrapers.base import stub_scraper

Scraper = stub_scraper("big_w", note="consoles — JSON-LD on PDPs")
