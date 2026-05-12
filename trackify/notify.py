from __future__ import annotations

import json
import os
from typing import Iterable, Optional

import httpx

from .models import Alert


GITHUB_API = "https://api.github.com"


def detect_alerts(
    product_key: str,
    retailer: str,
    title: str,
    url: str,
    new_price: Optional[float],
    prev_low: Optional[float],
    drop_pct_threshold: float,
) -> Optional[Alert]:
    if new_price is None:
        return None
    if prev_low is None:
        return None  # first observation — nothing to compare to
    if new_price < prev_low:
        return Alert(
            product_key=product_key,
            retailer=retailer,
            title=title,
            url=url,
            new_price=new_price,
            previous_low=prev_low,
            reason="new-all-time-low",
        )
    drop = (prev_low - new_price) / prev_low * 100 if prev_low > 0 else 0
    if drop >= drop_pct_threshold:
        return Alert(
            product_key=product_key,
            retailer=retailer,
            title=title,
            url=url,
            new_price=new_price,
            previous_low=prev_low,
            reason="drop-pct",
            drop_pct=round(drop, 1),
        )
    return None


def format_issue_body(alerts: Iterable[Alert]) -> str:
    by_product: dict[str, list[Alert]] = {}
    for a in alerts:
        by_product.setdefault(a.product_key, []).append(a)
    lines: list[str] = []
    for product_key, group in sorted(by_product.items()):
        lines.append(f"### {group[0].title}")
        for a in group:
            if a.reason == "new-all-time-low":
                tag = "**all-time low**"
                detail = f"now ${a.new_price:.2f} (prev low ${a.previous_low:.2f})"
            else:
                tag = f"**-{a.drop_pct}%**"
                detail = f"${a.new_price:.2f} from ${a.previous_low:.2f}"
            lines.append(f"- {tag} at [{a.retailer}]({a.url}) — {detail}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def open_github_issue(title: str, body: str) -> Optional[str]:
    """Open an issue on the current repo. Returns the issue URL or None."""
    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")  # "owner/name"
    if not token or not repo:
        return None
    r = httpx.post(
        f"{GITHUB_API}/repos/{repo}/issues",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        json={"title": title, "body": body, "labels": ["price-drop"]},
        timeout=30.0,
    )
    if r.status_code in (200, 201):
        return r.json().get("html_url")
    print(f"[notify] GitHub issue creation failed: {r.status_code} {r.text[:200]}")
    return None


def write_alert_summary(alerts: list[Alert], path) -> None:
    payload = [
        {
            "product_key": a.product_key,
            "retailer": a.retailer,
            "title": a.title,
            "url": a.url,
            "new_price": a.new_price,
            "previous_low": a.previous_low,
            "reason": a.reason,
            "drop_pct": a.drop_pct,
        }
        for a in alerts
    ]
    path.write_text(json.dumps(payload, indent=2) + "\n")
