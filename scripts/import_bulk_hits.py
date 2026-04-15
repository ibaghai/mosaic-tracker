#!/usr/bin/env python3
"""
Import bulk_expand JSON hits into the companies table.

Usage:
    python3 scripts/import_bulk_hits.py --hits scripts/midmarket_hits.json
"""

import argparse
import json
from datetime import datetime
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db.models import init_db, get_connection
from db import queries


def _default_careers_url(ats_type: str, ats_identifier: str):
    if ats_type == "greenhouse":
        return f"https://job-boards.greenhouse.io/{ats_identifier}"
    if ats_type == "lever":
        return f"https://jobs.lever.co/{ats_identifier}"
    if ats_type == "ashby":
        return f"https://jobs.ashbyhq.com/{ats_identifier}"
    if ats_type == "workable":
        return f"https://apply.workable.com/{ats_identifier}/"
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Import bulk_expand hits into DB")
    parser.add_argument("--hits", type=Path, required=True, help="JSON file from bulk_expand stdout")
    parser.add_argument("--company-type", default="startup", help="company_type to set on import")
    args = parser.parse_args()

    init_db()
    rows = json.loads(args.hits.read_text())
    if not isinstance(rows, list):
        raise ValueError("hits file must contain a JSON list")

    now = datetime.utcnow().isoformat()
    inserted = 0
    ids = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = row.get("name")
        ats_type = row.get("ats_type")
        ats_identifier = row.get("ats_identifier")
        if not name or not ats_type or not ats_identifier:
            continue
        company_id = queries.upsert_company({
            "name": name,
            "website": None,
            "ats_type": ats_type,
            "ats_identifier": ats_identifier,
            "funding_round": None,
            "funding_amount_m": None,
            "funding_date": None,
            "sector": None,
            "company_type": args.company_type,
            "careers_url": row.get("careers_url") or _default_careers_url(ats_type, str(ats_identifier)),
            "source_type": row.get("source_type", "bulk_expand"),
            "source_confidence": row.get("confidence", 0.8),
            "verification_status": "verified",
            "last_verified_at": now,
        })
        ids.append(company_id)
        inserted += 1

    conn = get_connection()
    with conn:
        for company_id in set(ids):
            conn.execute(
                "INSERT OR IGNORE INTO company_tags (company_id, tag) VALUES (?, 'size_midmarket')",
                (company_id,),
            )
    conn.close()

    print(json.dumps({
        "rows_read": len(rows),
        "rows_imported": inserted,
        "tagged_midmarket": len(set(ids)),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
