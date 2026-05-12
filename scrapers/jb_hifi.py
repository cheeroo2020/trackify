"""JB Hi-Fi — jbhifi.com.au

JB exposes Open Graph + JSON-LD on PDPs. They sometimes apply bot challenges
on GitHub Actions IPs — if you see consistent 403s, switch to a proxy or run
locally. The runner logs failures rather than crashing.
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
    saw_product = False

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
            if blob.get("@type") != "Product":
                continue
            saw_product = True
            title = title or blob.get("name")
            img = blob.get("image")
            if isinstance(img, list) and img:
                image = img[0]
            elif isinstance(img, str):
                image = img
            offers = blob.get("offers")
            if isinstance(offers, list) and offers:
                offers = offers[0]
            if isinstance(offers, dict):
                price = parse_price(str(offers.get("price")))
                avail = (offers.get("availability") or "").lower()
                in_stock = "instock" in avail

    if not saw_product:
        # Fallback: og:title + meta product:price:amount
        og = tree.css_first('meta[property="og:title"]')
        title = og.attributes.get("content") if og else None
        mprice = tree.css_first('meta[property="product:price:amount"]')
        if mprice:
            price = parse_price(mprice.attributes.get("content"))
        og_img = tree.css_first('meta[property="og:image"]')
        if og_img:
            image = og_img.attributes.get("content")

    if not title:
        return None
    return Listing(
        retailer="jb_hifi",
        category=category,
        product_key=product_key,
        title=title,
        url=url,
        price_aud=price,
        in_stock=in_stock,
        image_url=image,
    )


class Scraper(BaseScraper):
    name = "jb_hifi"

    def scrape(self, client: httpx.Client, config: dict) -> Iterator[Listing]:
        retailer_cfg = config.get("retailers", {}).get(self.name, {})
        urls = retailer_cfg.get("urls", {})  # { product_key: pdp_url }
        for product_key, url in urls.items():
            category = "ps5" if product_key.startswith("ps5/") else (
                "xbox" if product_key.startswith("xbox/") else "console"
            )
            try:
                r = self.fetch(client, url)
            except httpx.HTTPError as exc:
                print(f"[jb_hifi] fetch failed {url}: {exc}")
                continue
            tree = self.parse_html(r)
            listing = _parse_pdp(tree, url, product_key, category)
            if listing:
                yield listing
