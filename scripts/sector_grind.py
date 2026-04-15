#!/usr/bin/env python3
"""
Run multiple sector-based ATS discovery batches and add confirmed hits directly
into the canonical tracker.

Usage:
    python3 scripts/sector_grind.py
    python3 scripts/sector_grind.py --limit-sectors 3
"""

import argparse
import json
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db import queries  # noqa: E402
from db.models import init_db  # noqa: E402

SECTORS_FILE = ROOT / "scripts" / "sector_batches.json"


def load_sectors() -> dict[str, list[str]]:
    with open(SECTORS_FILE) as handle:
        return json.load(handle)


def existing_company_names() -> set[str]:
    return {row["name"].strip().lower() for row in queries.get_all_companies()}


def careers_url(ats_type: str, ats_identifier: str) -> Optional[str]:
    if ats_type == "greenhouse":
        return f"https://job-boards.greenhouse.io/{ats_identifier}"
    if ats_type == "lever":
        return f"https://jobs.lever.co/{ats_identifier}"
    if ats_type == "ashby":
        return f"https://jobs.ashbyhq.com/{ats_identifier}"
    return None


def run_batch(candidates: list[str]) -> list[dict]:
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as handle:
        handle.write("\n".join(candidates) + "\n")
        temp_path = handle.name
    try:
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "batch_discover.py"), temp_path],
            capture_output=True,
            text=True,
            check=True,
            cwd=str(ROOT),
        )
        return json.loads(proc.stdout)
    finally:
        Path(temp_path).unlink(missing_ok=True)


def add_hits(hits: list[dict], sector_name: str) -> list[dict]:
    added = []
    now = datetime.utcnow().isoformat()
    for hit in hits:
        company_id = queries.upsert_company({
            "name": hit["name"],
            "website": None,
            "ats_type": hit["ats_type"],
            "ats_identifier": hit["ats_identifier"],
            "funding_round": None,
            "funding_amount_m": None,
            "funding_date": None,
            "sector": sector_name,
            "company_type": "startup",
            "careers_url": careers_url(hit["ats_type"], hit["ats_identifier"]),
            "source_type": "sector_grind",
            "source_confidence": 0.95,
            "verification_status": "verified",
            "last_verified_at": now,
        })
        added.append({**hit, "company_id": company_id})
    return added


def main() -> int:
    parser = argparse.ArgumentParser(description="Run sector ATS discovery batches")
    parser.add_argument("--limit-sectors", type=int, default=0)
    args = parser.parse_args()

    init_db()
    sectors = load_sectors()
    existing = existing_company_names()
    summary = []
    sector_items = list(sectors.items())
    if args.limit_sectors:
        sector_items = sector_items[: args.limit_sectors]

    for sector_name, companies in sector_items:
        candidates = [name for name in companies if name.lower() not in existing]
        print(f"\n[{sector_name}] candidates={len(candidates)}")
        if not candidates:
            summary.append({"sector": sector_name, "candidates": 0, "hits": 0, "added": 0})
            continue
        hits = run_batch(candidates)
        added = add_hits(hits, sector_name)
        for row in added:
            existing.add(row["name"].lower())
        summary.append({
            "sector": sector_name,
            "candidates": len(candidates),
            "hits": len(hits),
            "added": len(added),
            "top_hits": added[:5],
        })
        print(f"[{sector_name}] hits={len(hits)} added={len(added)}")

    print("\n=== sector grind summary ===")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
