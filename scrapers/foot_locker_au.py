"""Foot Locker AU — footlocker.com.au

Discovery: parse anchor tags on the On brand listing for `/en/product/*-men-shoes/*.html`,
dedupe by model slug (one PDP per model).

PDP parsing: JSON-LD ProductGroup with hasVariant array; each variant is a Product
with offers.price + offers.priceCurrency=AUD + offers.availability. We take the
cheapest in-stock variant as the model-level "current price" (mens US 8 isn't
exposed as a separate offer, but FL's mens models are sized the same across
US 8–13, so the price for one size is the price for all).
"""
from __future__ import annotations

import json
import re
from typing import Iterator, Optional

import httpx

from scrapers.base import BaseScraper, parse_price, slugify
from trackify.models import Listing


BRAND_LISTING_URLS = [
    "https://www.footlocker.com.au/en/category/brands/on.html",
    "https://www.footlocker.com.au/en/category/brands/on.html?currentPage=2",
    "https://www.footlocker.com.au/en/category/brands/on.html?currentPage=3",
]

# /en/product/on-cloudmonster-men-shoes/244206508004.html
PDP_URL_RE = re.compile(
    r'href="(/en/product/(on-[^/]*-men-shoes)/[^"]+\.html)"', re.I
)


def _extract_jsonld(tree) -> list[dict]:
    """Flatten all JSON-LD into @type-bearing dicts (handles @graph if present)."""
    out: list[dict] = []
    for node in tree.css('script[type="application/ld+json"]'):
        text = node.text() or ""
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            continue
        stack = [data]
        while stack:
            cur = stack.pop()
            if isinstance(cur, dict):
                if "@graph" in cur and isinstance(cur["@graph"], list):
                    stack.extend(cur["@graph"])
                else:
                    out.append(cur)
            elif isinstance(cur, list):
                stack.extend(cur)
    return out


def _model_title(name: str | None) -> str | None:
    """'On Cloudmonster - Men Shoes' → 'Cloudmonster'."""
    if not name:
        return None
    s = re.sub(r"\s*-\s*Men'?s?\s+Shoes\s*$", "", name, flags=re.I)
    s = re.sub(r"^On\s+", "", s, flags=re.I)
    return s.strip()


def _parse_pdp(tree, url: str) -> Optional[Listing]:
    title: Optional[str] = None
    price: Optional[float] = None
    image: Optional[str] = None
    in_stock = False

    for blob in _extract_jsonld(tree):
        if blob.get("@type") != "ProductGroup":
            continue
        title = title or _model_title(blob.get("name")) or blob.get("name")
        # Image: prefer first variant image (top-level FL image is a placeholder)
        for variant in blob.get("hasVariant") or []:
            if not isinstance(variant, dict):
                continue
            if not image:
                vimg = variant.get("image")
                if isinstance(vimg, str):
                    image = vimg
                elif isinstance(vimg, list) and vimg:
                    image = vimg[0]
            offers = variant.get("offers")
            if isinstance(offers, dict):
                p = parse_price(str(offers.get("price") or ""))
                avail = (offers.get("availability") or "").lower()
                avail_in = "instock" in avail.replace("/", "")
                if p is not None and (price is None or p < price):
                    price = p
                    in_stock = avail_in

    if not title:
        return None
    return Listing(
        retailer="foot_locker_au",
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
    name = "foot_locker_au"
    category = "sneakers"

    def _discover(self, client: httpx.Client) -> list[str]:
        """Pull mens On product URLs from the brand listing pages and dedupe
        by model slug (one URL per model — colorways share the same PDP)."""
        seen_models: dict[str, str] = {}
        for listing_url in BRAND_LISTING_URLS:
            try:
                r = self.fetch(client, listing_url)
            except httpx.HTTPError as exc:
                print(f"[foot_locker_au] listing fetch failed {listing_url}: {exc}")
                continue
            for m in PDP_URL_RE.finditer(r.text):
                href, model_slug = m.group(1), m.group(2).lower()
                if model_slug not in seen_models:
                    seen_models[model_slug] = f"https://www.footlocker.com.au{href}"
        return list(seen_models.values())

    def scrape(self, client: httpx.Client, config: dict) -> Iterator[Listing]:
        max_products = int(
            config.get("retailers", {}).get(self.name, {}).get("max_products", 40)
        )
        urls = self._discover(client)
        print(f"[foot_locker_au] discovered {len(urls)} unique mens On models")
        seen_keys: set[str] = set()
        for url in urls[:max_products]:
            try:
                r = self.fetch(client, url)
            except httpx.HTTPError as exc:
                print(f"[foot_locker_au] PDP fetch failed {url}: {exc}")
                continue
            tree = self.parse_html(r)
            listing = _parse_pdp(tree, url)
            if not listing:
                continue
            if listing.product_key in seen_keys:
                continue
            seen_keys.add(listing.product_key)
            yield listing
