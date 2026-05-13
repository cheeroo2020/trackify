"""Rebel Sport — rebelsport.com.au

Salesforce Commerce Cloud (Demandware). PDPs serve clean JSON-LD Product
blocks with offers.priceSpecification[].price + .priceCurrency.

Discovery: parse /brands/on for anchor tags matching mens shoe PDPs.
Rebel's brand listing only shows a small set of "in-stock-recently" cards
in static HTML (the rest is lazy-loaded), so coverage here is naturally
limited to whatever's prominent on the brand page. That's still useful
as a third price source for ON Cloudrunner / Cloudsurfer / Cloudmonster.
"""
from __future__ import annotations

import json
import re
from typing import Iterator, Optional

import httpx

from scrapers.base import BaseScraper, parse_price, slugify
from trackify.models import Listing


BRAND_LISTING_URL = "https://www.rebelsport.com.au/brands/on"

# Mens shoes only: /p/on-<model-slug>-mens-<sport>-shoes-<MNNNN>.html
PDP_URL_RE = re.compile(
    r'href="(/p/on-(?P<model>[^"]+?)-mens-[^"]*-shoes-M\d+\.html)[^"]*"', re.I
)


def _model_title(name: Optional[str]) -> Optional[str]:
    """'On Cloudrunner 2 Mens Running Shoes White/Grey US 8' → 'Cloudrunner 2'."""
    if not name:
        return None
    # Strip leading "On " (case-insensitive)
    s = re.sub(r"^On\s+", "", name, flags=re.I)
    # Cut at " Mens " / " Womens " / " Running " etc.
    s = re.split(r"\s+(?:Mens?|Womens?)\s+", s, maxsplit=1, flags=re.I)[0]
    # Some titles are like "Cloudmonster Mens Running Shoes Black/Black" so the
    # split above gives us "Cloudmonster". If split didn't trigger, also strip
    # trailing " Shoes" or " Running Shoes" or " Sneakers".
    s = re.sub(
        r"\s+(?:Running\s+)?(?:Training\s+)?(?:Trail\s+)?Shoes\s.*$",
        "",
        s,
        flags=re.I,
    )
    return s.strip()


def _parse_pdp(tree, url: str) -> Optional[Listing]:
    title: Optional[str] = None
    price: Optional[float] = None
    image: Optional[str] = None
    in_stock = False

    for node in tree.css('script[type="application/ld+json"]'):
        text = node.text() or ""
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            continue
        blobs = data if isinstance(data, list) else [data]
        for blob in blobs:
            if not isinstance(blob, dict):
                continue
            if blob.get("@type") not in ("Product", "ProductGroup"):
                continue
            full_name = blob.get("name") or ""
            cand = _model_title(full_name)
            if cand and (not title or len(cand) < len(title)):
                title = cand

            img = blob.get("image")
            if not image:
                if isinstance(img, str):
                    image = img
                elif isinstance(img, list) and img:
                    image = img[0]

            offers = blob.get("offers")
            if isinstance(offers, list) and offers:
                offers = offers[0]
            if isinstance(offers, dict):
                avail = (offers.get("availability") or "").lower()
                in_stock = in_stock or ("instock" in avail.replace("/", ""))

                # Rebel nests price in priceSpecification[].price
                p: Optional[float] = None
                specs = offers.get("priceSpecification") or []
                if isinstance(specs, list):
                    for spec in specs:
                        if isinstance(spec, dict):
                            p = p or parse_price(str(spec.get("price") or ""))
                if p is None:
                    p = parse_price(str(offers.get("price") or ""))
                if p is not None and (price is None or p < price):
                    price = p

    if not title:
        return None
    return Listing(
        retailer="rebel",
        category="sneakers",
        product_key=f"on/{slugify(title)}",
        title=title,
        url=url,
        price_aud=price,
        in_stock=in_stock,
        size="US M8",
        image_url=image,
    )


class Scraper(BaseScraper):
    name = "rebel"
    category = "sneakers"

    def _discover(self, client: httpx.Client) -> list[str]:
        try:
            r = self.fetch(client, BRAND_LISTING_URL, headers={
                "Referer": "https://www.rebelsport.com.au/",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            })
        except httpx.HTTPError as exc:
            print(f"[rebel] brand listing fetch failed: {exc}")
            return []
        seen: dict[str, str] = {}
        for m in PDP_URL_RE.finditer(r.text):
            href, model = m.group(1), m.group("model").lower()
            seen.setdefault(model, f"https://www.rebelsport.com.au{href}")
        return list(seen.values())

    def scrape(self, client: httpx.Client, config: dict) -> Iterator[Listing]:
        max_products = int(
            config.get("retailers", {}).get(self.name, {}).get("max_products", 20)
        )
        urls = self._discover(client)
        print(f"[rebel] discovered {len(urls)} unique mens On models")
        seen_keys: set[str] = set()
        for url in urls[:max_products]:
            try:
                r = self.fetch(client, url, headers={
                    "Referer": BRAND_LISTING_URL,
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                })
            except httpx.HTTPError as exc:
                print(f"[rebel] PDP fetch failed {url}: {exc}")
                continue
            tree = self.parse_html(r)
            listing = _parse_pdp(tree, url)
            if not listing:
                continue
            if listing.product_key in seen_keys:
                continue
            seen_keys.add(listing.product_key)
            yield listing
