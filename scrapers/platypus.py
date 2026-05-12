"""Platypus Shoes — platypusshoes.com.au — STUB

Notes:
- Brand: /collections/mens-on
- Shopify storefront — append `.json` to any product URL to get a clean JSON
  response with variants, prices, and inventory. Much easier than HTML.
- Filter variants where `option1` (or whichever option is "Size") == "8".
"""
from __future__ import annotations
from scrapers.base import stub_scraper

Scraper = stub_scraper("platypus", note="Shopify — use products.json endpoints")
