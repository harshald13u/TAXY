#!/usr/bin/env python3
"""
Taxy backend — daily scraper for Indian tax updates.

Hits CBDT, ITAT, PIB, Live Law, and TaxGuru once a day.
Writes one JSON per source to backend/data/<source>.json.
Idempotent — safe to run multiple times a day.

Usage:
    python scrape_updates.py                    # scrape all enabled sources
    python scrape_updates.py --only cbdt_circulars  # scrape one source
    python scrape_updates.py --dry-run          # don't write files
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional
from urllib.parse import urljoin

import requests
import yaml
from bs4 import BeautifulSoup

try:
    import feedparser
except ImportError:
    feedparser = None

# ---------- Config ----------
ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"
SOURCES_FILE = ROOT / "sources.yaml"
HEADERS = {
    # Real Chrome UA — incometaxindia.gov.in and PIB block "TaxyBot"-style UAs.
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-IN,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}
TIMEOUT = 30  # seconds per request

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("taxy.scraper")


# ---------- Data model ----------
@dataclass
class Item:
    """Normalized item returned by every scraper."""
    source: str
    category: str
    title: str
    url: str
    date: Optional[str]      # ISO date string if available
    summary: Optional[str]   # short description
    item_id: str             # stable hash for diffing
    raw_meta: dict           # source-specific extras (number, ref, etc.)


# ---------- HTTP helper ----------
def fetch(url: str) -> Optional[str]:
    """GET a URL with retries. Returns HTML text or None on failure."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT, verify=True)
        r.raise_for_status()
        return r.text
    except requests.exceptions.RequestException as e:
        log.warning("fetch failed: %s — %s", url, e)
        return None


def make_id(url: str, title: str) -> str:
    """Stable hash for diffing. URL is usually unique; title is fallback."""
    import hashlib
    key = (url + "|" + title).lower().strip()
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


# ---------- Scrapers ----------
def scrape_cbdt_listing(name: str, url: str, category: str) -> List[Item]:
    """
    CBDT circulars / notifications / press-releases.
    The pages share a common table layout under #ctl00_SPWebPartManager1_g_*.
    Defensive: layout may shift. We grab any <a> within the main content area
    that points at a /communications/ PDF or detail page.
    """
    html = fetch(url)
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    items: List[Item] = []

    # Find the main content container — try a few selectors
    main = (
        soup.select_one("#ctl00_PlaceHolderMain_RichHtmlField1__ControlWrapper_RichHtmlField")
        or soup.select_one("#ctl00_SPWebPartManager1_g_*")
        or soup.select_one("table.contenttable")
        or soup
    )

    rows = main.find_all("tr")
    for tr in rows:
        cells = tr.find_all("td")
        if len(cells) < 2:
            continue
        link = tr.find("a", href=True)
        if not link:
            continue
        href = urljoin(url, link["href"])
        title = link.get_text(strip=True)
        if not title or len(title) < 5:
            continue

        # Try to extract a date / number from siblings
        date = None
        ref_no = None
        for c in cells:
            txt = c.get_text(strip=True)
            if re.match(r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}", txt):
                date = txt
            if re.match(r"^\d+/\d{4}$", txt) or "Notification No" in txt:
                ref_no = txt

        items.append(Item(
            source=name,
            category=category,
            title=title[:300],
            url=href,
            date=date,
            summary=None,
            item_id=make_id(href, title),
            raw_meta={"ref_no": ref_no} if ref_no else {},
        ))

    log.info("[%s] scraped %d items", name, len(items))
    return items


def scrape_pib_listing(name: str, url: str, category: str) -> List[Item]:
    """PIB Ministry of Finance releases — table-based listing."""
    html = fetch(url)
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    items: List[Item] = []
    for li in soup.select("ul.num li, div.content-area li"):
        a = li.find("a", href=True)
        if not a:
            continue
        title = a.get_text(strip=True)
        href = urljoin(url, a["href"])
        if not title or "PIB" not in href and "pib.gov.in" not in href:
            continue
        date = None
        date_el = li.find(class_=re.compile("date", re.I))
        if date_el:
            date = date_el.get_text(strip=True)
        items.append(Item(
            source=name, category=category, title=title[:300],
            url=href, date=date, summary=None,
            item_id=make_id(href, title), raw_meta={},
        ))
    log.info("[%s] scraped %d items", name, len(items))
    return items


def scrape_itat_listing(name: str, url: str, category: str) -> List[Item]:
    """ITAT (Income Tax Appellate Tribunal) recent orders."""
    html = fetch(url)
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    items: List[Item] = []
    for a in soup.select("a[href*='judicial']"):
        title = a.get_text(strip=True)
        href = urljoin(url, a["href"])
        if not title or len(title) < 10:
            continue
        items.append(Item(
            source=name, category=category, title=title[:300],
            url=href, date=None, summary=None,
            item_id=make_id(href, title), raw_meta={},
        ))
    log.info("[%s] scraped %d items", name, len(items))
    return items


def scrape_rss(name: str, url: str, category: str) -> List[Item]:
    """Generic RSS/Atom feed parser — Live Law, TaxGuru."""
    if not feedparser:
        log.error("feedparser not installed — skipping RSS source %s", name)
        return []
    feed = feedparser.parse(url)
    items: List[Item] = []
    for entry in feed.entries[:50]:
        title = entry.get("title", "").strip()
        link = entry.get("link", "")
        date = entry.get("published") or entry.get("updated")
        summary = (entry.get("summary") or entry.get("description") or "")[:500]
        if not title or not link:
            continue
        items.append(Item(
            source=name, category=category, title=title[:300],
            url=link, date=date, summary=summary,
            item_id=make_id(link, title), raw_meta={},
        ))
    log.info("[%s] scraped %d items", name, len(items))
    return items


# ---------- Dispatcher ----------
SCRAPERS = {
    "cbdt_listing": scrape_cbdt_listing,
    "pib_listing": scrape_pib_listing,
    "itat_listing": scrape_itat_listing,
    "rss": scrape_rss,
}


def run_scraper(source: dict) -> List[Item]:
    name = source["name"]
    stype = source["type"]
    fn = SCRAPERS.get(stype)
    if not fn:
        log.error("[%s] no scraper for type %s", name, stype)
        return []
    try:
        return fn(name, source["url"], source["category"])
    except Exception as e:
        log.exception("[%s] scraper crashed: %s", name, e)
        return []


def write_output(name: str, items: List[Item], dry_run: bool = False) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out_path = DATA_DIR / f"{name}.json"
    payload = {
        "source": name,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "count": len(items),
        "items": [asdict(it) for it in items],
    }
    if dry_run:
        log.info("[%s] DRY RUN — would write %d items to %s", name, len(items), out_path)
        return
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    log.info("[%s] wrote %s", name, out_path)


def main():
    ap = argparse.ArgumentParser(description="Scrape Indian tax updates")
    ap.add_argument("--only", help="Only run this source name")
    ap.add_argument("--dry-run", action="store_true", help="Don't write files")
    args = ap.parse_args()

    config = yaml.safe_load(SOURCES_FILE.read_text())
    sources = config.get("sources", [])

    total = 0
    for src in sources:
        if not src.get("enabled", True):
            continue
        if args.only and src["name"] != args.only:
            continue
        items = run_scraper(src)
        write_output(src["name"], items, dry_run=args.dry_run)
        total += len(items)

    log.info("Done. Scraped %d items total.", total)


if __name__ == "__main__":
    main()
