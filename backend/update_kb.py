#!/usr/bin/env python3
"""
Taxy backend — KB updater.

Reads _diff.json produced by diff_engine.py and merges new items into the
user-facing knowledge bases the chat app consumes:

  - landmark_case_law.json   (case law section)
  - operational_reference_data.json (notifications + circulars)

Conservative by default — items are added under a separate `pending_review`
section so a human can promote them. Full automation is opt-in via --auto-approve.
"""

from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent
KB_ROOT = ROOT.parent  # IncomeTax/
DIFF_FILE = ROOT / "data" / "_diff.json"
KB_CASE_LAW = KB_ROOT / "landmark_case_law.json"
KB_OPERATIONAL = KB_ROOT / "operational_reference_data.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("taxy.kb")


def load_kb(path: Path) -> dict:
    if not path.exists():
        log.warning("KB %s missing — starting empty", path)
        return {}
    return json.loads(path.read_text())


def save_kb(path: Path, kb: dict, dry_run: bool) -> None:
    if dry_run:
        log.info("DRY RUN — would write %s", path)
        return
    path.write_text(json.dumps(kb, indent=2, ensure_ascii=False))
    log.info("wrote %s", path)


def update_case_law(kb: dict, new_items: list, auto_approve: bool) -> int:
    """Add new case-law items either to pending or directly to the KB."""
    bucket = "cases" if auto_approve else "pending_review"
    kb.setdefault(bucket, [])
    existing_ids = {x.get("item_id") for x in kb[bucket]}
    added = 0
    for it in new_items:
        if it["item_id"] in existing_ids:
            continue
        kb[bucket].append({
            "item_id": it["item_id"],
            "title": it["title"],
            "url": it["url"],
            "date": it.get("date"),
            "summary": it.get("summary"),
            "source": it["source"],
            "added_at": datetime.now(timezone.utc).isoformat(),
        })
        added += 1
    return added


def update_operational(kb: dict, new_items: list, category: str, auto_approve: bool) -> int:
    """Add notifications / circulars / press releases."""
    bucket_key = "updates" if auto_approve else "pending_review"
    kb.setdefault(bucket_key, {})
    kb[bucket_key].setdefault(category, [])
    existing_ids = {x.get("item_id") for x in kb[bucket_key][category]}
    added = 0
    for it in new_items:
        if it["item_id"] in existing_ids:
            continue
        kb[bucket_key][category].append({
            "item_id": it["item_id"],
            "title": it["title"],
            "url": it["url"],
            "date": it.get("date"),
            "summary": it.get("summary"),
            "ref_no": it.get("raw_meta", {}).get("ref_no"),
            "source": it["source"],
            "added_at": datetime.now(timezone.utc).isoformat(),
        })
        added += 1
    return added


def main():
    ap = argparse.ArgumentParser(description="Apply diff to KB JSONs")
    ap.add_argument("--auto-approve", action="store_true",
                    help="Promote new items directly into the live KB (default: pending review)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not DIFF_FILE.exists():
        log.error("no diff file — run diff_engine.py first")
        return 1

    diff = json.loads(DIFF_FILE.read_text())
    case_kb = load_kb(KB_CASE_LAW)
    op_kb = load_kb(KB_OPERATIONAL)

    case_added = 0
    op_added = 0
    for src, payload in diff.get("by_source", {}).items():
        category = payload.get("category")
        new = payload.get("new_items", [])
        if not new:
            continue
        if category == "case_law":
            case_added += update_case_law(case_kb, new, args.auto_approve)
        elif category in ("circulars", "notifications", "press", "analysis"):
            op_added += update_operational(op_kb, new, category, args.auto_approve)

    if case_added:
        case_kb.setdefault("metadata", {})["last_auto_update"] = datetime.now(timezone.utc).isoformat()
        save_kb(KB_CASE_LAW, case_kb, args.dry_run)
    if op_added:
        op_kb.setdefault("metadata", {})["last_auto_update"] = datetime.now(timezone.utc).isoformat()
        save_kb(KB_OPERATIONAL, op_kb, args.dry_run)

    log.info("done — %d new case-law items, %d new operational items", case_added, op_added)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
