from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Iterable, Optional

import httpx

from .models import Listing, PricePoint


REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
PRODUCTS_DIR = DATA_DIR / "products"
IMAGES_DIR = REPO_ROOT / "images"
LATEST_PATH = DATA_DIR / "latest.json"


def _product_file(product_key: str, retailer: str) -> Path:
    safe = product_key.replace("/", "-")
    return PRODUCTS_DIR / f"{safe}__{retailer}.json"


def load_history(product_key: str, retailer: str) -> dict:
    path = _product_file(product_key, retailer)
    if not path.exists():
        return {"product_key": product_key, "retailer": retailer, "history": []}
    return json.loads(path.read_text())


def save_observation(listing: Listing) -> dict:
    PRODUCTS_DIR.mkdir(parents=True, exist_ok=True)
    record = load_history(listing.product_key, listing.retailer)
    record["title"] = listing.title
    record["category"] = listing.category
    record["url"] = listing.url
    if listing.size:
        record["size"] = listing.size
    if listing.image_path:
        record["image_path"] = listing.image_path

    point = PricePoint(
        observed_at=listing.observed_at,
        price_aud=listing.price_aud,
        in_stock=listing.in_stock,
        url=listing.url,
    ).__dict__

    history = record.get("history", [])
    # Skip duplicate consecutive points (same price + stock) to keep the file small.
    if history:
        last = history[-1]
        if (
            last.get("price_aud") == point["price_aud"]
            and last.get("in_stock") == point["in_stock"]
        ):
            last["observed_at"] = point["observed_at"]
        else:
            history.append(point)
    else:
        history.append(point)
    record["history"] = history

    _product_file(listing.product_key, listing.retailer).write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n"
    )
    return record


def write_latest_snapshot(listings: Iterable[Listing]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    snapshot = [l.to_dict() for l in listings]
    snapshot.sort(key=lambda r: (r["category"], r["product_key"], r["retailer"]))
    LATEST_PATH.write_text(json.dumps(snapshot, indent=2) + "\n")


def previous_low(product_key: str, retailer: str) -> Optional[float]:
    """Return the lowest price ever seen for this (product, retailer).

    Called BEFORE save_observation, so the on-disk history does not yet
    contain the observation we're about to write — every stored point is
    'prior' and counts.
    """
    record = load_history(product_key, retailer)
    prices = [p["price_aud"] for p in record.get("history", []) if p.get("price_aud") is not None]
    return min(prices) if prices else None


def cache_image(image_url: str, client: Optional[httpx.Client] = None) -> Optional[str]:
    """Download an image once and return its repo-relative path."""
    if not image_url:
        return None
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(image_url.encode()).hexdigest()[:16]
    suffix = ".jpg"
    for ext in (".png", ".webp", ".jpg", ".jpeg"):
        if ext in image_url.lower():
            suffix = ext
            break
    rel = f"images/{digest}{suffix}"
    abs_path = REPO_ROOT / rel
    if abs_path.exists():
        return rel

    own_client = client is None
    if own_client:
        client = httpx.Client(timeout=20.0, follow_redirects=True)
    try:
        r = client.get(image_url)
        if r.status_code == 200 and r.content:
            abs_path.write_bytes(r.content)
            return rel
    except httpx.HTTPError:
        return None
    finally:
        if own_client:
            client.close()
    return None
