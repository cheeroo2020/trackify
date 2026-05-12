"""Amazon AU — amazon.com.au — STUB

Heads up: Amazon aggressively blocks scrapers, especially from datacenter
IPs like GitHub Actions runners. Realistic options if you want this to work:
  1. Use the Product Advertising API (PA-API) with your associates account
     — proper, allowed, but requires sign-up and a few approved sales.
  2. Use a residential-proxy service (Bright Data, ScraperAPI, etc.).
  3. Skip Amazon and rely on the other retailers.

If you go the HTML route anyway: PDPs have `#priceblock_ourprice`,
`#corePrice_feature_div`, or a JSON-LD Product block depending on layout.
"""
from __future__ import annotations
from scrapers.base import stub_scraper

Scraper = stub_scraper("amazon_au", note="bot-blocked — prefer PA-API or proxy")
