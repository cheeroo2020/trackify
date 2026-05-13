"""Platypus Shoes — platypusshoes.com.au — BLOCKED, kept as stub.

Their sitemap is reachable and lists clean product URLs like
  /shop/on/cloud-6, /shop/on/cloudmonster, /shop/on/cloudvista-2

But the PDPs return ~70KB of pure JS bundle with no product data in
static HTML (no JSON-LD, no microdata, no og:price tags, no inline
state). Their /products.json endpoint returns 404 (they're on
Magento/Bigcommerce, not Shopify, despite my earlier guess).

Needs headless browser to render. Skipping.
"""
from __future__ import annotations
from scrapers.base import stub_scraper

Scraper = stub_scraper("platypus", note="SPA — PDPs have zero static product data")
