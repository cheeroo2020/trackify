"""The Good Guys — thegoodguys.com.au

PDPs expose a clean JSON-LD Product block with offers.price and
availability. Same structural pattern as JB Hi-Fi. Product list is
config-driven; console SKUs change rarely so this stays stable.
"""
from __future__ import annotations

import json
from typing import Iterator, Optional

import httpx

from scrapers.base import BaseScraper, parse_price
from trackify.models import Listing


def _parse_pdp(tree, url: str, product_key: str, category: str) -> Optional[Listing]:
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
            if not isinstance(blob, dict) or blob.get("@type") != "Product":
                continue
            title = title or blob.get("name")
            img = blob.get("image")
            if isinstance(img, list) and img:
                image = image or img[0]
            elif isinstance(img, str):
                image = image or img
            offers = blob.get("offers")
            if isinstance(offers, list) and offers:
                offers = offers[0]
            if isinstance(offers, dict):
                price = parse_price(str(offers.get("price") or ""))
                avail = (offers.get("availability") or "").lower()
                in_stock = "instock" in avail.replace("/", "")

    if not title:
        og = tree.css_first('meta[property="og:title"]')
        if og:
            title = (og.attributes.get("content") or "").strip()
    if not image:
        og_img = tree.css_first('meta[property="og:image"]')
        if og_img:
            image = og_img.attributes.get("content")
    if not title:
        return None
    return Listing(
        retailer="the_good_guys",
        category=category,
        product_key=product_key,
        title=title,
        url=url,
        price_aud=price,
        in_stock=in_stock,
        image_url=image,
    )


class Scraper(BaseScraper):
    name = "the_good_guys"

    def scrape(self, client: httpx.Client, config: dict) -> Iterator[Listing]:
        retailer_cfg = config.get("retailers", {}).get(self.name, {})
        urls = retailer_cfg.get("urls", {})
        for product_key, url in urls.items():
            category = "ps5" if product_key.startswith("ps5/") else (
                "xbox" if product_key.startswith("xbox/") else "console"
            )
            try:
                r = self.fetch(client, url)
            except httpx.HTTPError as exc:
                print(f"[the_good_guys] fetch failed {url}: {exc}")
                continue
            tree = self.parse_html(r)
            listing = _parse_pdp(tree, url, product_key, category)
            if listing:
                yield listing
