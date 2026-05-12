"""The Iconic AU — theiconic.com.au — STUB

Implementation notes when you fill this in:
- Search for ON Running brand on theiconic.com.au/?q=on+running+mens
- The Iconic uses Next.js with embedded __NEXT_DATA__ JSON — read that script
  instead of HTML selectors. It contains structured product data including
  size variants and prices.
- Filter to size "US 8" / "8 US" in mens.
- product_key should be `on/<slugified-model-name>` so it groups with on_au.
"""
from __future__ import annotations
from scrapers.base import stub_scraper

Scraper = stub_scraper("the_iconic", note="ON sneakers — read __NEXT_DATA__")
