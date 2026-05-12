from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class Listing:
    """A single product offer at one retailer at one point in time."""

    retailer: str
    category: str  # "sneakers" | "ps5" | "xbox"
    product_key: str  # stable slug used to group observations across retailers
    title: str
    url: str
    price_aud: Optional[float]
    in_stock: bool
    size: Optional[str] = None  # "US M8" for sneakers
    image_url: Optional[str] = None
    image_path: Optional[str] = None  # relative path inside repo, set after caching
    observed_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PricePoint:
    observed_at: str
    price_aud: Optional[float]
    in_stock: bool
    url: str


@dataclass
class Alert:
    product_key: str
    retailer: str
    title: str
    url: str
    new_price: float
    previous_low: Optional[float]
    reason: str  # "new-all-time-low" | "drop-pct"
    drop_pct: Optional[float] = None
