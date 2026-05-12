"""Foot Locker AU — footlocker.com.au — STUB

Notes:
- Brand page: /en/category/brands/on.html
- PDPs have JSON-LD Product blocks (same pattern as eb_games).
- Filter size variants for "US 8".
- product_key should be `on/<slugified-model-name>` to group with on_au.
"""
from __future__ import annotations
from scrapers.base import stub_scraper

Scraper = stub_scraper("foot_locker_au", note="ON sneakers — JSON-LD on PDPs")
