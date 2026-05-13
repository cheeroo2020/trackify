"""The Iconic — theiconic.com.au — BLOCKED, kept as stub.

Static HTML is empty: their brand/category pages render client-side with
no SSR. No __NEXT_DATA__, no JSON-LD product blocks, no microdata. The
HTML body is JS bundle + framework shell only.

A working scraper here would require headless browser automation (Playwright
or similar) running outside GitHub Actions, or a paid scraping API. Not
worth the operational overhead vs. what it would add (mostly the same ON
models already covered by on_au and foot_locker_au).
"""
from __future__ import annotations
from scrapers.base import stub_scraper

Scraper = stub_scraper("the_iconic", note="JS-rendered SPA — needs headless browser")
