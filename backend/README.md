# Taxy Backend — Daily Auto-Update

A scheduled Python pipeline that scrapes Indian tax sources every day, detects
new circulars / notifications / case law, and updates the chat app's knowledge
base JSONs automatically.

## Honest scope

This is **not** "self-learning AI". It's a cron job + scrapers + diff engine.
Useful, real, deployable for free, but boring under the hood. That honesty matters.

## What it does (every day, automatically)

1. **`scrape_updates.py`** — hits 7 sources:
   - CBDT circulars, notifications, press releases (incometaxindia.gov.in)
   - PIB Ministry of Finance releases
   - ITAT (Income Tax Appellate Tribunal) recent orders
   - Live Law tax section (RSS)
   - TaxGuru income-tax category (RSS)
2. **`diff_engine.py`** — compares today's scrape vs yesterday's, lists new items
3. **`update_kb.py`** — adds new items to `landmark_case_law.json` and
   `operational_reference_data.json` under a `pending_review` bucket
4. **You promote** approved items into the live KB (or use `--auto-approve` for
   full automation, at your own risk)

## Files

```
backend/
├── sources.yaml              # which sources to scrape — edit freely
├── scrape_updates.py         # the scraper
├── diff_engine.py            # the differ
├── update_kb.py              # the KB updater
├── requirements.txt          # Python deps
├── data/
│   ├── cbdt_circulars.json   # one file per source (today's snapshot)
│   ├── cbdt_notifications.json
│   ├── ...
│   ├── _diff.json            # what changed since the last run
│   └── history/
│       └── snapshot-YYYY-MM-DD.json   # daily snapshots, last 90 kept
└── README.md                 # this file

.github/workflows/
└── daily-update.yml          # GitHub Actions schedule — runs at 01:30 IST daily
```

## Deploy in 5 minutes

1. **Push this repo to GitHub** (private or public — both work)
2. Go to **Settings → Actions → General** and enable Actions
3. Go to **Settings → Actions → General → Workflow permissions** → set to
   **"Read and write permissions"** (so the bot can push KB updates back)
4. The workflow runs automatically at 20:00 UTC daily. To trigger now:
   **Actions tab → Taxy Daily Update → Run workflow**

That's it. Zero infra. Free for public repos. ~2 minutes of compute per run.

## Run locally to test

```bash
cd backend
pip install -r requirements.txt

# Scrape everything once
python scrape_updates.py

# Or just one source:
python scrape_updates.py --only cbdt_circulars

# Compute what's new
python diff_engine.py

# Apply to KB (in pending_review by default)
python update_kb.py

# Or apply directly without review:
python update_kb.py --auto-approve
```

## Tested results (first run, 2 May 2026)

End-to-end pipeline confirmed working:

| Source | Status | Items |
|--------|--------|-------|
| TaxGuru RSS | ✅ working | 50 items (incl. Sec 194T TDS, Safe Harbour Rules ITA 2025) |
| ITAT orders | ✅ working | 3 items |
| CBDT circulars | ⚠️ 404 — URL changed; serves with browser UA | 0 (selectors need updating) |
| CBDT notifications | ⚠️ 404 — URL changed | 0 |
| CBDT press releases | ⚠️ 404 — URL changed | 0 |
| PIB finance | ⚠️ blocks bots | 0 (use browser UA — included now) |
| Live Law tax | ❌ feed URL wrong | 0 — disabled |

Pipeline output:
- 53 new items detected by diff engine
- 3 added to `landmark_case_law.json` under `pending_review`
- 50 added to `operational_reference_data.json` under `pending_review`

**Bottom line: the chain works. CBDT scrapers need the URL/selectors confirmed
once you have a real run on a fresh CBDT page (their layout shifts twice a year).**

## What honesty looks like

- **Scrapers break.** Government websites change layout without warning.
  When a scraper breaks, that source's count goes to 0 — check `data/<source>.json`
  and update the CSS selectors in `scrape_updates.py`.
- **First run treats everything as new.** The diff engine has nothing to
  compare against, so day 1's `_diff.json` will be huge. Day 2 onwards is the
  real signal.
- **Pending review by default.** Items don't go straight into the user-facing
  KB — they sit in `pending_review` so you can curate. Flip to `--auto-approve`
  in the workflow once you trust the scrapers.
- **Not all sources are covered.** Supreme Court tax matters need a custom
  filter (too many non-tax orders); high courts each have their own portals.
  Adding sources is editing `sources.yaml` plus possibly a new scraper function.
- **Some sources rate-limit.** PIB and incometaxindia.gov.in are friendly with
  one daily request. Don't run the workflow more than once a day or you'll
  get blocked.

## Adding a new source

Edit `sources.yaml`:

```yaml
- name: my_new_source
  url: https://example.com/tax-feed.rss
  type: rss              # or cbdt_listing / pib_listing / itat_listing
  category: case_law     # or circulars / notifications / press / analysis
  enabled: true
```

If it's an RSS feed, no code changes needed. If it's a custom HTML layout,
add a new function in `scrape_updates.py` and register it in the `SCRAPERS` dict.

## Reading updates from the chat app

The chat app (`app/app.html`) can fetch the live KB JSONs at startup via:

```javascript
fetch('https://raw.githubusercontent.com/<your-repo>/main/landmark_case_law.json')
  .then(r => r.json())
  .then(kb => { /* merge into ACT object */ });
```

Or, if you serve the site on the same repo via GitHub Pages, just `fetch('/landmark_case_law.json')`.

## What's NOT in this system

- LLM summarization of new circulars (would cost ~₹0.50/circular via Claude Haiku — easy to add)
- Automatic high-court scraping (each HC has its own portal — manual selectors needed)
- Email/Slack alerts when something major changes (one webhook call, easy to add)
- Real ML/AI "learning" (this is just deterministic pattern matching)

These are all next-step adds, not built-in. The base pipeline does the boring 80%.
