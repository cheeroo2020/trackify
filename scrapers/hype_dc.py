"""Hype DC — hypedc.com — partially feasible, kept as stub for now.

Sitemap discovery works: /au/public/sitemap-brand-categories.xml lists
clean URLs like /au/brands/on/cloudmonster, /au/brands/on/cloudtilt, etc.
6 mens On models discoverable.

PDPs return 200 only with a full set of browser headers (UA + Referer
+ Accept). Product data lives in a Nuxt 3 `__NUXT_DATA__` JSON blob
that uses Nuxt's index-reference encoding — not standard JSON shape.
Extracting price + title would need a custom decoder.

Marked as stub until either Hype DC adds JSON-LD/microdata to PDPs, or
we invest in a Nuxt deserializer.
"""
from __future__ import annotations
from scrapers.base import stub_scraper

Scraper = stub_scraper("hype_dc", note="Nuxt __NUXT_DATA__ encoding — needs custom parser")
