#!/usr/bin/env python3
"""
Taxy backend — diff engine.

Compares today's scrape vs the last successful scrape and produces _diff.json
listing only the NEW items. This is what the chat app + KB updater consume.

Run after scrape_updates.py.

Usage:
    python diff_engine.py
    python diff_engine.py --since 2026-04-30   # diff against a specific date
"""

from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Set

ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"
HISTORY_DIR = ROOT / "data" / "history"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("taxy.diff")


def load_current() -> Dict[str, dict]:
    """Load every <source>.json in DATA_DIR (the latest scrape)."""
    out: Dict[str, dict] = {}
    for p in DATA_DIR.glob("*.json"):
        if p.name.startswith("_") or p.parent != DATA_DIR:
            continue
        try:
            data = json.loads(p.read_text())
            out[data["source"]] = data
        except Exception as e:
            log.warning("could not load %s: %s", p, e)
    return out


def load_history(date_str: str = None) -> Dict[str, Set[str]]:
    """Load the snapshot of item_ids from a previous date (defaults to most recent)."""
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    snapshots = sorted(HISTORY_DIR.glob("snapshot-*.json"))
    if not snapshots:
        log.info("no prior snapshots — first run, every item is 'new'")
        return {}
    if date_str:
        target = HISTORY_DIR / f"snapshot-{date_str}.json"
        if not target.exists():
            log.warning("no snapshot for %s — using most recent", date_str)
            target = snapshots[-1]
    else:
        target = snapshots[-1]
    log.info("comparing against %s", target.name)
    snap = json.loads(target.read_text())
    return {src: set(ids) for src, ids in snap.items()}


def save_snapshot(current: Dict[str, dict]) -> None:
    """Save today's item_ids per source for future diffs."""
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    snap_path = HISTORY_DIR / f"snapshot-{today}.json"
    snap = {src: [it["item_id"] for it in data["items"]] for src, data in current.items()}
    snap_path.write_text(json.dumps(snap, indent=2))
    log.info("snapshot saved → %s", snap_path)

    # Keep only last 90 snapshots
    all_snaps = sorted(HISTORY_DIR.glob("snapshot-*.json"))
    for old in all_snaps[:-90]:
        old.unlink()


def compute_diff(current: Dict[str, dict], previous_ids: Dict[str, Set[str]]) -> dict:
    """Compute new + removed items per source."""
    diff = {
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "summary": {"new_total": 0, "removed_total": 0, "sources_with_changes": []},
        "by_source": {},
    }
    for src, data in current.items():
        prev = previous_ids.get(src, set())
        curr_items = data["items"]
        curr_ids = {it["item_id"] for it in curr_items}
        new_ids = curr_ids - prev
        removed_ids = prev - curr_ids if prev else set()
        new_items = [it for it in curr_items if it["item_id"] in new_ids]
        if new_items or removed_ids:
            diff["summary"]["sources_with_changes"].append(src)
            diff["summary"]["new_total"] += len(new_items)
            diff["summary"]["removed_total"] += len(removed_ids)
        diff["by_source"][src] = {
            "category": curr_items[0]["category"] if curr_items else None,
            "new_items": new_items,
            "removed_ids": list(removed_ids),
        }
    return diff


def main():
    ap = argparse.ArgumentParser(description="Diff today's scrape vs prior snapshot")
    ap.add_argument("--since", help="ISO date — compare against snapshot-<date>.json")
    args = ap.parse_args()

    current = load_current()
    if not current:
        log.error("no current scrape data found in %s — run scrape_updates.py first", DATA_DIR)
        return 1

    previous = load_history(args.since)
    diff = compute_diff(current, previous)

    diff_path = DATA_DIR / "_diff.json"
    diff_path.write_text(json.dumps(diff, indent=2, ensure_ascii=False))
    log.info("diff written → %s", diff_path)
    log.info(
        "summary: %d new, %d removed, %d sources changed",
        diff["summary"]["new_total"],
        diff["summary"]["removed_total"],
        len(diff["summary"]["sources_with_changes"]),
    )

    save_snapshot(current)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
