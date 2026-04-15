#!/usr/bin/env python3
"""
Apply growth quality gates and company tagging.

Usage:
    python3 scripts/growth_maintenance.py --apply
"""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db.models import get_connection


def _rows_to_ids(rows):
    return {row["id"] for row in rows}


def find_low_first_scrape(min_jobs: int):
    conn = get_connection()
    rows = conn.execute(
        """
        WITH first_success AS (
            SELECT
                sr.company_id,
                sr.jobs_found,
                sr.run_at,
                ROW_NUMBER() OVER (
                    PARTITION BY sr.company_id
                    ORDER BY sr.run_at ASC, sr.id ASC
                ) AS rn
            FROM scrape_runs sr
            WHERE sr.status = 'success'
        )
        SELECT c.id, c.name, fs.jobs_found, fs.run_at
        FROM first_success fs
        JOIN companies c ON c.id = fs.company_id
        WHERE fs.rn = 1 AND fs.jobs_found < ?
        """
        , (min_jobs,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def find_missing_second_success(max_days: int):
    conn = get_connection()
    rows = conn.execute(
        """
        WITH success_runs AS (
            SELECT company_id, run_at
            FROM scrape_runs
            WHERE status = 'success'
        ),
        agg AS (
            SELECT
                company_id,
                MIN(run_at) AS first_success_at,
                COUNT(*) AS success_count
            FROM success_runs
            GROUP BY company_id
        )
        SELECT c.id, c.name, a.first_success_at, a.success_count
        FROM agg a
        JOIN companies c ON c.id = a.company_id
        WHERE a.success_count < 2
          AND julianday('now') - julianday(a.first_success_at) > ?
        """
        , (max_days,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def find_stale_zero_job_companies(stale_days: int):
    conn = get_connection()
    rows = conn.execute(
        """
        WITH active_jobs AS (
            SELECT c.id AS company_id, COUNT(j.id) AS active_jobs
            FROM companies c
            LEFT JOIN job_postings j
              ON j.company_id = c.id
             AND j.is_active = 1
            GROUP BY c.id
        ),
        latest_success AS (
            SELECT company_id, MAX(run_at) AS last_success_at
            FROM scrape_runs
            WHERE status = 'success'
            GROUP BY company_id
        )
        SELECT c.id, c.name, COALESCE(a.active_jobs, 0) AS active_jobs, ls.last_success_at
        FROM companies c
        LEFT JOIN active_jobs a ON a.company_id = c.id
        LEFT JOIN latest_success ls ON ls.company_id = c.id
        WHERE COALESCE(a.active_jobs, 0) = 0
          AND ls.last_success_at IS NOT NULL
          AND julianday('now') - julianday(ls.last_success_at) > ?
        """
        , (stale_days,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def find_repeated_failures(window: int):
    conn = get_connection()
    rows = conn.execute(
        """
        WITH ordered AS (
            SELECT
                sr.company_id,
                sr.status,
                ROW_NUMBER() OVER (
                    PARTITION BY sr.company_id
                    ORDER BY sr.run_at DESC, sr.id DESC
                ) AS rn
            FROM scrape_runs sr
        ),
        head AS (
            SELECT
                company_id,
                COUNT(*) AS n_runs,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS n_failed
            FROM ordered
            WHERE rn <= ?
            GROUP BY company_id
        )
        SELECT c.id, c.name, h.n_runs, h.n_failed
        FROM head h
        JOIN companies c ON c.id = h.company_id
        WHERE h.n_runs = ? AND h.n_failed = ?
        """
        , (window, window, window)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def find_midmarket_candidates(min_jobs: int, max_jobs: int):
    conn = get_connection()
    rows = conn.execute(
        """
        WITH active AS (
            SELECT c.id, c.name, c.company_type, COUNT(j.id) AS active_jobs
            FROM companies c
            LEFT JOIN job_postings j
              ON j.company_id = c.id
             AND j.is_active = 1
            GROUP BY c.id
        )
        SELECT id, name, active_jobs
        FROM active
        WHERE company_type != 'bigco'
          AND active_jobs BETWEEN ? AND ?
        ORDER BY active_jobs DESC, name
        """
        , (min_jobs, max_jobs)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def apply_tags(*, disable_ids: set[int], midmarket_ids: set[int]):
    conn = get_connection()
    with conn:
        for company_id in disable_ids:
            conn.execute(
                "INSERT OR IGNORE INTO company_tags (company_id, tag) VALUES (?, 'disabled_autoprune')",
                (company_id,),
            )
        conn.execute(
            "DELETE FROM company_tags WHERE tag = 'size_midmarket'"
        )
        for company_id in midmarket_ids:
            conn.execute(
                "INSERT OR IGNORE INTO company_tags (company_id, tag) VALUES (?, 'size_midmarket')",
                (company_id,),
            )
    conn.close()


def current_tag_counts():
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT tag, COUNT(*) AS count
        FROM company_tags
        GROUP BY tag
        ORDER BY count DESC, tag
        """
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply growth quality gates and tags")
    parser.add_argument("--apply", action="store_true", help="write tag changes")
    parser.add_argument("--first-min-jobs", type=int, default=5)
    parser.add_argument("--second-within-days", type=int, default=7)
    parser.add_argument("--zero-jobs-stale-days", type=int, default=21)
    parser.add_argument("--failure-window", type=int, default=3)
    parser.add_argument("--midmarket-min-jobs", type=int, default=20)
    parser.add_argument("--midmarket-max-jobs", type=int, default=300)
    args = parser.parse_args()

    low_first = find_low_first_scrape(args.first_min_jobs)
    missing_second = find_missing_second_success(args.second_within_days)
    stale_zero = find_stale_zero_job_companies(args.zero_jobs_stale_days)
    repeated_fail = find_repeated_failures(args.failure_window)
    midmarket = find_midmarket_candidates(args.midmarket_min_jobs, args.midmarket_max_jobs)

    disable_ids = (
        _rows_to_ids(low_first)
        | _rows_to_ids(missing_second)
        | _rows_to_ids(stale_zero)
        | _rows_to_ids(repeated_fail)
    )
    midmarket_ids = _rows_to_ids(midmarket)

    payload = {
        "apply": args.apply,
        "quality_gates": {
            "low_first_scrape_jobs": len(low_first),
            "missing_second_success": len(missing_second),
            "stale_zero_jobs": len(stale_zero),
            "repeated_failures": len(repeated_fail),
            "disable_union": len(disable_ids),
        },
        "midmarket": {
            "tagged_companies": len(midmarket_ids),
            "min_jobs": args.midmarket_min_jobs,
            "max_jobs": args.midmarket_max_jobs,
        },
    }

    if args.apply:
        apply_tags(disable_ids=disable_ids, midmarket_ids=midmarket_ids)
        payload["tag_counts"] = current_tag_counts()

    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
