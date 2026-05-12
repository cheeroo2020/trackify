"""ON Running Australia — on.com/en-au

Discovery via the public products.xml sitemap (it's the only mens-shoes
source on this site that doesn't require JS rendering). We:
  1. Fetch the sitemap and pull every URL matching
     /products/<slug>/mens/<colorway>-shoes-<sku>
  2. Dedupe by slug (one colorway per model is enough — the model-level
     price doesn't vary across colorways).
  3. Fetch each PDP and read its Product JSON-LD for AUD price + the
     mens US 8 variant availability.
"""
from __future__ import annotations

import json
import re
from typing import Iterator, Optional

import httpx
from selectolax.parser import HTMLParser

from scrapers.base import BaseScraper, parse_price, slugify
from trackify.models import Listing


SITEMAP_URL = "https://www.on.com/en-au/products.xml"
SHOE_URL_RE = re.compile(
    r"^https://www\.on\.com/en-au/products/([^/]+)/mens/[^/]*shoes-[^/]+$"
)

# ON labels mens US 8 in JSON-LD offer descriptions as "US M 8" or just "8" /
# inside a sku containing the size code.
TARGET_SIZE_PATTERNS = [
    re.compile(r"\bUS\s*M?\s*8\b", re.I),
    re.compile(r"\bsize\W*8\b", re.I),
]


def _is_target_size(label: str) -> bool:
    return any(p.search(label or "") for p in TARGET_SIZE_PATTERNS)


def _extract_jsonld(tree: HTMLParser) -> list[dict]:
    out: list[dict] = []
    for node in tree.css('script[type="application/ld+json"]'):
        text = node.text() or ""
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(data, list):
            out.extend(d for d in data if isinstance(d, dict))
        elif isinstance(data, dict):
            out.append(data)
    return out


def _parse_pdp(tree: HTMLParser, url: str) -> Optional[Listing]:
    title: Optional[str] = None
    price: Optional[float] = None
    image: Optional[str] = None
    in_stock_size_8 = False

    for blob in _extract_jsonld(tree):
        if blob.get("@type") != "Product":
            continue
        title = title or blob.get("name")
        if isinstance(blob.get("image"), list) and blob["image"]:
            image = image or blob["image"][0]
        elif isinstance(blob.get("image"), str):
            image = image or blob["image"]

        offers = blob.get("offers")
        if isinstance(offers, dict):
            if offers.get("@type") == "AggregateOffer":
                price = price or parse_price(str(offers.get("lowPrice") or ""))
                candidates = offers.get("offers") or []
            else:
                candidates = [offers]
        elif isinstance(offers, list):
            candidates = offers
        else:
            candidates = []

        for off in candidates:
            if not isinstance(off, dict):
                continue
            label_bits = [
                off.get("name"),
                off.get("sku"),
                off.get("description"),
                off.get("size"),
            ]
            item = off.get("itemOffered")
            if isinstance(item, dict):
                label_bits.append(item.get("size"))
                label_bits.append(item.get("name"))
            label = " ".join(str(v) for v in label_bits if v)
            if _is_target_size(label):
                p = parse_price(str(off.get("price") or ""))
                avail = (off.get("availability") or "").lower()
                if p is not None:
                    price = p
                in_stock_size_8 = "instock" in avail or "in_stock" in avail or avail.endswith("instock")
                break

    if not title:
        h1 = tree.css_first("h1")
        if h1:
            title = h1.text(strip=True)
    if not title:
        og = tree.css_first('meta[property="og:title"]')
        if og:
            title = og.attributes.get("content")

    if not image:
        og_img = tree.css_first('meta[property="og:image"]')
        if og_img:
            image = og_img.attributes.get("content")

    if not title:
        return None

    return Listing(
        retailer="on_au",
        category="sneakers",
        product_key=f"on/{slugify(title)}",
        title=title,
        url=url,
        price_aud=price,
        in_stock=in_stock_size_8,
        size="US M8",
        image_url=image,
    )


class Scraper(BaseScraper):
    name = "on_au"
    category = "sneakers"

    def _discover(self, client: httpx.Client) -> list[str]:
        r = self.fetch(client, SITEMAP_URL)
        urls: dict[str, str] = {}
        for m in re.finditer(r"<loc>([^<]+)</loc>", r.text):
            url = m.group(1)
            match = SHOE_URL_RE.match(url)
            if not match:
                continue
            slug = match.group(1)
            urls.setdefault(slug, url)
        return list(urls.values())

    def scrape(self, client: httpx.Client, config: dict) -> Iterator[Listing]:
        max_products = int(
            config.get("retailers", {}).get(self.name, {}).get("max_products", 60)
        )
        try:
            product_urls = self._discover(client)
        except httpx.HTTPError as exc:
            print(f"[on_au] sitemap fetch failed: {exc}")
            return
        print(f"[on_au] sitemap discovered {len(product_urls)} unique mens shoe models")

        seen_keys: set[str] = set()
        for url in product_urls[:max_products]:
            try:
                r = self.fetch(client, url)
            except httpx.HTTPError as exc:
                print(f"[on_au] PDP fetch failed {url}: {exc}")
                continue
            tree = self.parse_html(r)
            listing = _parse_pdp(tree, url)
            if listing is None:
                continue
            # Dedupe across colorway URLs that happened to share a model slug
            if listing.product_key in seen_keys:
                continue
            seen_keys.add(listing.product_key)
            yield listing
