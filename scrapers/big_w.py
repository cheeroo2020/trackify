"""Big W — bigw.com.au — BLOCKED, kept as stub.

Sitemap is reachable (7 product sitemaps, 50K URLs each) but it only
includes games, accessories, console covers, etc. — the actual PS5 /
Xbox console SKUs aren't in the public sitemap.

Direct PDP requests for guessed slugs all return HTTP 403 from this
machine and from GitHub Actions runners. Their /api/v3/ JSON endpoints
also 403/redirect to the SPA shell. Big W has an aggressive WAF/bot
filter that rejects non-browser traffic.

Needs residential proxy + browser fingerprint to work. Skipping.
"""
from __future__ import annotations
from scrapers.base import stub_scraper

Scraper = stub_scraper("big_w", note="WAF blocks scraper traffic; needs proxy")
