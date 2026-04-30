"""Smoke test for analysis.people on the v1 branch.

Picks a real job from the v1 DB, fetches candidate humans at that company
(in mock mode unless APOLLO_API_KEY is set), and prints what would be
persisted. Exercises caps, mock mode, and the people-search code path.

Usage:
    python scripts/test_apollo_people.py            # picks a job automatically
    python scripts/test_apollo_people.py --job 12345 # specific job id
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from textwrap import indent

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db.models import init_db, get_connection  # noqa: E402
from analysis import people as people_mod  # noqa: E402


def _pick_job(job_id: int | None) -> dict:
    init_db()
    conn = get_connection()
    try:
        if job_id:
            row = conn.execute("""
                SELECT jp.id, jp.title, jp.company_id, c.name AS company_name, c.website,
                       jp.description
                FROM job_postings jp JOIN companies c ON c.id = jp.company_id
                WHERE jp.id = ?
            """, (job_id,)).fetchone()
        else:
            row = conn.execute("""
                SELECT jp.id, jp.title, jp.company_id, c.name AS company_name, c.website,
                       jp.description
                FROM job_postings jp JOIN companies c ON c.id = jp.company_id
                WHERE jp.is_active = 1 AND c.website IS NOT NULL
                ORDER BY jp.first_seen_at DESC
                LIMIT 1
            """).fetchone()
        if not row:
            raise SystemExit("no active job found in v1 DB")
        return dict(row)
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job", type=int, default=None)
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()

    job = _pick_job(args.job)
    print(f"Job: #{job['id']}  {job['title']}  @  {job['company_name']}  ({job['website']})")
    print(f"Apollo usage status: {json.dumps(people_mod.usage_status(), indent=2)}")
    print()

    for archetype, titles in [
        ("recruiter", ["recruiter", "talent partner"]),
        ("hiring_manager", ["VP Engineering", "Director of Engineering", "Head of Engineering"]),
        ("recent_joiner", None),
    ]:
        print(f"── archetype: {archetype} ──")
        try:
            results = people_mod.find_people_at_company(
                job["company_id"],
                titles=titles,
                archetype=archetype,
                limit=args.limit,
                persist=True,
            )
        except people_mod.ApolloCapExceeded as exc:
            print(f"  CAP HIT: {exc}")
            continue
        except people_mod.ApolloError as exc:
            print(f"  Apollo error: {exc}")
            continue

        if not results:
            print("  (no people)")
            continue

        for person in results:
            print(f"  • [{person.get('id')}] {person['name']} — {person.get('title')}")
            print(indent(
                f"linkedin: {person.get('linkedin_url')}\n"
                f"email: {person.get('email')} ({person.get('email_status')})\n"
                f"bio: {person.get('bio_summary')}\n"
                f"tenure_start: {person.get('tenure_start_date')}",
                "      ",
            ))
        print()

    print(f"Final usage: {json.dumps(people_mod.usage_status()['used'])}")


if __name__ == "__main__":
    main()
