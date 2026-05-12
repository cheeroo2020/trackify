# trackify

Weekly price tracker for **ON sneakers (mens US 8)**, **PlayStation 5 consoles**,
and **Xbox consoles** across major Australian retailers. Runs entirely inside
GitHub Actions on a weekly cron, commits price history back to the repo, and
opens an issue when a tracked product hits a new low (or drops ≥5%).

**Live dashboard**: <https://cheeroo2020.github.io/trackify/>
(responsive grid of product cards — images, prices side-by-side per retailer,
cheapest highlighted. Auto-redeploys when the weekly Action commits new data.)

## Enabling the dashboard (one-time)

On GitHub: **Settings → Pages → Build and deployment → Source: Deploy from a
branch → Branch: `main` / root → Save.** Site goes live at the URL above in
about a minute.

## How it works

```
.github/workflows/track.yml     weekly cron (Mon ~9am Sydney) → runs trackify
trackify/                       framework: runner, store, notify, models
scrapers/                       one file per retailer; subclass BaseScraper
config.yml                      what to track, thresholds, retailer toggles
data/products/<key>__<retailer>.json     price history per (product, retailer)
data/latest.json                most recent snapshot for all listings
data/alerts.json                alerts produced by the most recent run
images/                         cached product images, content-hashed
```

Each weekly run:
1. Scrapes every enabled retailer.
2. Caches new product images into `images/`.
3. Appends a price point to `data/products/<key>__<retailer>.json`
   (consecutive identical points are collapsed).
4. Diffs each new price against the historical low for that (product, retailer).
5. If any drops trigger, opens a GitHub Issue summarising them (labelled `price-drop`).
6. Commits `data/` and `images/` back to the repo so the history is durable.

## What works out of the box

| Retailer | Status | Notes |
| --- | --- | --- |
| ON AU (`on_au`) | ✅ live | auto-discovers all mens models, filters to US M8 |
| EB Games (`eb_games`) | ✅ live | console URLs pinned in `config.yml` |
| JB Hi-Fi (`jb_hifi`) | ✅ live | console URLs pinned in `config.yml`; may need proxy if GitHub IPs get blocked |
| The Iconic | 🟡 stub | hint inside the file |
| Foot Locker AU | 🟡 stub | |
| JD Sports AU | 🟡 stub | |
| Platypus | 🟡 stub | Shopify — `products.json` trick noted |
| Hype DC | 🟡 stub | Shopify — same |
| Rebel | 🟡 stub | |
| Amazon AU | 🟡 stub | aggressive bot-blocking; needs PA-API or residential proxy |
| Big W | 🟡 stub | |
| Harvey Norman | 🟡 stub | |
| The Good Guys | 🟡 stub | |

Stubs are real Python modules that log "not implemented yet" and yield nothing,
so the pipeline runs cleanly even before you fill them in. Each stub file
contains a short note explaining the best path to implement it.

## Running locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m trackify.runner --dry-run        # full run, doesn't write files
python -m trackify.runner --only on_au     # one scraper at a time
python -m trackify.runner                  # full run, writes data/ + images/
```

To preview the dashboard locally without Pages:

```bash
python3 -m http.server 8000   # then open http://localhost:8000
```

Local runs won't open GitHub Issues unless you export `GITHUB_TOKEN` and
`GITHUB_REPOSITORY=<owner>/trackify`. Alerts are also always written to
`data/alerts.json` so you can inspect them either way.

## Adding a scraper

1. Create `scrapers/<name>.py` with a `class Scraper(BaseScraper)` exposing
   a `scrape(self, client, config) -> Iterable[Listing]` method. Copy
   `scrapers/eb_games.py` as a template — JSON-LD parsing covers most AU
   retailers.
2. Yield `Listing` objects (see `trackify/models.py`). Use a consistent
   `product_key` across retailers — e.g. `on/cloud-5` — so price history
   groups correctly in `data/products/`.
3. Set `enabled: true` for the retailer in `config.yml`.
4. Test with `python -m trackify.runner --only <name>`.

## Tuning what gets tracked

- **Add/remove console SKUs**: edit `retailers.<retailer>.urls` in `config.yml`.
  Keep `product_key` stable when a retailer changes its URL, or you'll start
  a fresh history.
- **Change cadence**: edit the `cron:` line in `.github/workflows/track.yml`.
- **Change alert threshold**: `alerting.drop_pct_threshold` in `config.yml`.
- **Switch sneaker size**: `sneakers.target_size_label` plus the regexes in
  `scrapers/on_au.py`.

## Known limitations

- Selectors will break. JSON-LD is the most stable surface but retailers do
  refactor — when a scraper starts returning zero listings, that's the signal
  to update its parser.
- GitHub Actions runs from datacenter IPs. Some sites (Amazon especially)
  block these aggressively. The honest workaround is residential proxies or
  official APIs.
- No CAPTCHA solving, no JS rendering. Scrapers only work on retailers that
  serve a usable HTML body without JS. The three live scrapers do; some
  stubs will need a different strategy.
- "Notify when prices are cheapest" is implemented as "alert when a new
  all-time low is seen for that (product, retailer) pair, or a ≥5% drop".
  History is built up after the first few runs.
