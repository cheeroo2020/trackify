"""JD Sports AU — jdsports.com.au — BLOCKED, kept as stub.

Connection drops immediately (curl exit 000) on every request from this
machine and from GitHub Actions runners, regardless of headers. JD AU
appears to either geo-block or aggressively reject non-residential IPs
at the TLS layer.

A working scraper would need a residential proxy. Skipping.
"""
from __future__ import annotations
from scrapers.base import stub_scraper

Scraper = stub_scraper("jd_sports_au", note="TLS-level block; needs residential proxy")
