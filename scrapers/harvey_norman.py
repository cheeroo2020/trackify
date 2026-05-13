"""Harvey Norman — harveynorman.com.au — BLOCKED, kept as stub.

Returns HTTP 403 on every request from this machine and from GitHub
Actions runners, including sitemap.xml — even with a full set of browser
headers and an AU geo cookie. They have a strict WAF.

Needs residential proxy. Skipping.
"""
from __future__ import annotations
from scrapers.base import stub_scraper

Scraper = stub_scraper("harvey_norman", note="WAF blocks all requests; needs proxy")
