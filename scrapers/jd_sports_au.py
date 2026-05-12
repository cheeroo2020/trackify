"""JD Sports AU — jdsports.com.au — STUB

Notes:
- Brand listing: /men/brand/on/
- Salesforce Commerce Cloud backend; PDPs expose a `var product = {...}` JSON
  blob in inline JS, plus JSON-LD.
- Map size "8" to US M8 for ON shoes.
"""
from __future__ import annotations
from scrapers.base import stub_scraper

Scraper = stub_scraper("jd_sports_au", note="ON sneakers — inline product JSON")
