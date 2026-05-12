from __future__ import annotations

import argparse
import importlib
import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import httpx
import yaml

from . import store, notify
from .models import Listing, Alert


REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = REPO_ROOT / "config.yml"


def load_config() -> dict:
    return yaml.safe_load(CONFIG_PATH.read_text())


def _instantiate_scraper(name: str):
    """Import scrapers.<name> and return its Scraper class instance."""
    mod = importlib.import_module(f"scrapers.{name}")
    cls = getattr(mod, "Scraper")
    return cls()


def run_once(only: list[str] | None = None, dry_run: bool = False) -> int:
    cfg = load_config()
    enabled = cfg.get("retailers", {})
    drop_threshold = float(cfg.get("alerting", {}).get("drop_pct_threshold", 5.0))

    all_listings: list[Listing] = []
    alerts: list[Alert] = []
    errors: list[tuple[str, str]] = []

    with httpx.Client(
        timeout=30.0,
        follow_redirects=True,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-AU,en;q=0.9",
        },
        http2=True,
    ) as client:
        for name, meta in enabled.items():
            if not meta.get("enabled", False):
                continue
            if only and name not in only:
                continue
            print(f"[run] scraping {name}…", flush=True)
            try:
                scraper = _instantiate_scraper(name)
            except ModuleNotFoundError:
                print(f"[run] no scraper module for {name}, skipping")
                continue
            try:
                listings = list(scraper.scrape(client=client, config=cfg))
            except Exception as exc:  # noqa: BLE001
                errors.append((name, f"{exc.__class__.__name__}: {exc}"))
                traceback.print_exc()
                continue

            print(f"[run] {name}: {len(listings)} listings", flush=True)
            for listing in listings:
                if listing.image_url and not listing.image_path:
                    listing.image_path = store.cache_image(listing.image_url, client=client)
                prev_low = store.previous_low(listing.product_key, listing.retailer)
                if not dry_run:
                    store.save_observation(listing)
                alert = notify.detect_alerts(
                    product_key=listing.product_key,
                    retailer=listing.retailer,
                    title=listing.title,
                    url=listing.url,
                    new_price=listing.price_aud,
                    prev_low=prev_low,
                    drop_pct_threshold=drop_threshold,
                )
                if alert:
                    alerts.append(alert)
                all_listings.append(listing)

    if not dry_run:
        store.write_latest_snapshot(all_listings)

    summary_dir = REPO_ROOT / "data"
    summary_dir.mkdir(parents=True, exist_ok=True)
    notify.write_alert_summary(alerts, summary_dir / "alerts.json")

    print(f"[run] total listings: {len(all_listings)}, alerts: {len(alerts)}, errors: {len(errors)}")
    for name, msg in errors:
        print(f"[run]   error in {name}: {msg}")

    if alerts and not dry_run:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        title = f"Price drops — {today} ({len(alerts)} alert{'s' if len(alerts) != 1 else ''})"
        body = notify.format_issue_body(alerts)
        url = notify.open_github_issue(title, body)
        if url:
            print(f"[run] opened issue: {url}")
        else:
            print("[run] (no GITHUB_TOKEN — skipping issue creation; alerts.json was written)")

    return 0 if not errors else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="trackify", description="Weekly AU retail price tracker")
    parser.add_argument("--only", nargs="*", help="Run only these retailer scrapers by name")
    parser.add_argument("--dry-run", action="store_true", help="Don't write data/ or open issues")
    args = parser.parse_args(argv)
    return run_once(only=args.only, dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
