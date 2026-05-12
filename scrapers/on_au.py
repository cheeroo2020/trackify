"""ON Running Australia — on.com/en-au

Approach: ON exposes product data via JSON-LD blocks on each PLP/PDP and via
its Shopify-like product feed. To stay robust across redesigns we:
  1. Fetch the mens running + lifestyle PLPs.
  2. Extract product cards (href + title + image) from JSON-LD ItemList blocks.
  3. For each product, fetch the PDP and read its Product JSON-LD for the
     current AUD price + the size 8 (US M) variant availability.

If the JSON-LD shape changes, replace the parser — the contract is just
"return Listings".
"""
from __future__ import annotations

import json
import re
from typing import Iterator, Optional

import httpx
from selectolax.parser import HTMLParser

from scrapers.base import BaseScraper, parse_price, slugify
from trackify.models import Listing


PLP_URLS = [
    "https://www.on.com/en-au/shop/mens/shoes/running",
    "https://www.on.com/en-au/shop/mens/shoes/training",
    "https://www.on.com/en-au/shop/mens/shoes/all-day",
    "https://www.on.com/en-au/shop/mens/shoes/hiking",
    "https://www.on.com/en-au/shop/mens/shoes/tennis",
]

# Mens US 8 ≈ EU 40.5/41 ≈ UK 7 — ON labels these explicitly as "US M 8" / "8".
TARGET_SIZE_LABEL_PATTERNS = [
    re.compile(r"^\s*8\s*$"),
    re.compile(r"\bUS\s*M?\s*8\b", re.I),
]


def _is_target_size(label: str) -> bool:
    return any(p.search(label) for p in TARGET_SIZE_LABEL_PATTERNS)


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


def _product_links_from_plp(tree: HTMLParser, base: str) -> list[str]:
    links: set[str] = set()
    # JSON-LD ItemList is the cleanest source
    for blob in _extract_jsonld(tree):
        if blob.get("@type") in ("ItemList", "CollectionPage"):
            for item in blob.get("itemListElement", []) or []:
                url = (
                    item.get("url")
                    if isinstance(item, dict)
                    else None
                )
                if not url and isinstance(item, dict):
                    url = (item.get("item") or {}).get("url") if isinstance(item.get("item"), dict) else None
                if url:
                    links.add(url)
    # Fallback: anchor tags that look like PDPs
    if not links:
        for a in tree.css("a[href]"):
            href = a.attributes.get("href", "")
            if "/shop/" in href and href.count("/") >= 4 and not href.endswith("/"):
                full = href if href.startswith("http") else f"https://www.on.com{href}"
                # Heuristic: PDP URLs end in a model slug, not a category slug
                if "/shoes/" in full and full.rstrip("/").split("/")[-1] not in {
                    "running", "training", "all-day", "hiking", "tennis", "shoes"
                }:
                    links.add(full)
    return sorted(links)


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
            image = blob["image"][0]
        elif isinstance(blob.get("image"), str):
            image = blob["image"]

        offers = blob.get("offers")
        candidates = []
        if isinstance(offers, list):
            candidates = offers
        elif isinstance(offers, dict):
            if offers.get("@type") == "AggregateOffer":
                # Use the low price as a fallback baseline; refine below if size 8 found
                price = parse_price(str(offers.get("lowPrice")))
                candidates = offers.get("offers") or []
            else:
                candidates = [offers]

        for off in candidates:
            if not isinstance(off, dict):
                continue
            label = " ".join(
                str(v) for v in (
                    off.get("name"),
                    off.get("sku"),
                    off.get("description"),
                    (off.get("itemOffered") or {}).get("size") if isinstance(off.get("itemOffered"), dict) else None,
                ) if v
            )
            if _is_target_size(label):
                p = parse_price(str(off.get("price")))
                avail = (off.get("availability") or "").lower()
                if p is not None:
                    price = p
                in_stock_size_8 = "instock" in avail or "in_stock" in avail
                break

    if not title:
        h1 = tree.css_first("h1")
        if h1:
            title = h1.text(strip=True)

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

    def scrape(self, client: httpx.Client, config: dict) -> Iterator[Listing]:
        max_products = int(config.get("retailers", {}).get(self.name, {}).get("max_products", 60))
        seen: set[str] = set()
        product_urls: list[str] = []
        for plp in PLP_URLS:
            try:
                r = self.fetch(client, plp)
            except httpx.HTTPError as exc:
                print(f"[on_au] PLP fetch failed {plp}: {exc}")
                continue
            tree = self.parse_html(r)
            for link in _product_links_from_plp(tree, plp):
                if link not in seen:
                    seen.add(link)
                    product_urls.append(link)

        if not product_urls:
            print("[on_au] no product URLs discovered from PLPs — selectors may have shifted")
            return

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
            yield listing
