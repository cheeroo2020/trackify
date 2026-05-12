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
    """Flatten all JSON-LD blocks into a single list of @type-bearing dicts.
    ON wraps its product data in {"@graph": [...]} so we recurse into that.
    """
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


def _model_name_from_group(name: Optional[str]) -> Optional[str]:
    """ProductGroup names look like "Men's Cloud 6"; strip the gender prefix."""
    if not name:
        return None
    return re.sub(r"^(Men'?s|Women'?s)\s+", "", name).strip()


def _parse_pdp(tree: HTMLParser, url: str) -> Optional[Listing]:
    """ON's JSON-LD shape:
      ProductGroup → hasVariant: [Product(colorway), ...]
                                  → offers: { price, priceCurrency, availability }
    Per-size info is not in JSON-LD (only colorways). The model-level price
    is the same across all sizes within a colorway for ON shoes, so we track
    that as the "US M8 price".
    """
    title: Optional[str] = None
    price: Optional[float] = None
    image: Optional[str] = None
    in_stock = False
    saw_offer = False

    blobs = _extract_jsonld(tree)

    # First pass: take the ProductGroup name and walk its variants (preferred shape)
    for blob in blobs:
        if blob.get("@type") != "ProductGroup":
            continue
        title = title or _model_name_from_group(blob.get("name"))
        variants = blob.get("hasVariant") or blob.get("member") or []
        for v in variants:
            if not isinstance(v, dict):
                continue
            if not image:
                vimg = v.get("image")
                if isinstance(vimg, str):
                    image = vimg
                elif isinstance(vimg, list) and vimg:
                    image = vimg[0]
            offers = v.get("offers")
            if isinstance(offers, dict):
                p = parse_price(str(offers.get("price") or ""))
                avail = (offers.get("availability") or "").lower()
                avail_in = "instock" in avail.replace("/", "")
                if p is not None:
                    saw_offer = True
                    if price is None or p < price:
                        price = p
                        in_stock = avail_in

    # Second pass: standalone Products (in case ProductGroup is missing)
    if not saw_offer:
        for blob in blobs:
            if blob.get("@type") != "Product":
                continue
            title = title or _model_name_from_group(blob.get("name")) or blob.get("name")
            if not image:
                bimg = blob.get("image")
                if isinstance(bimg, str):
                    image = bimg
                elif isinstance(bimg, list) and bimg:
                    image = bimg[0]
            offers = blob.get("offers")
            offer_list = offers if isinstance(offers, list) else [offers]
            for o in offer_list:
                if not isinstance(o, dict):
                    continue
                if o.get("@type") == "AggregateOffer":
                    p = parse_price(str(o.get("lowPrice") or ""))
                    if p is not None and (price is None or p < price):
                        price = p
                else:
                    p = parse_price(str(o.get("price") or ""))
                    avail = (o.get("availability") or "").lower()
                    avail_in = "instock" in avail.replace("/", "")
                    if p is not None and (price is None or p < price):
                        price = p
                        in_stock = avail_in

    # Fallbacks for title / image
    if not title:
        h1 = tree.css_first("h1")
        if h1:
            title = h1.text(strip=True)
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
        retailer="on_au",
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
