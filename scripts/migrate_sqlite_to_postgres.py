#!/usr/bin/env python3

import argparse
import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from db.models import get_connection, init_db


TABLE_COLUMNS = {
    "companies": [
        "id",
        "name",
        "website",
        "ats_type",
        "ats_identifier",
        "funding_round",
        "funding_amount_m",
        "funding_date",
        "sector",
        "company_type",
        "hq_location",
        "employee_count_range",
        "founded_year",
        "is_active",
        "added_at",
    ],
    "job_postings": [
        "id",
        "company_id",
        "title",
        "department",
        "location",
        "location_raw",
        "location_city",
        "location_region",
        "location_country",
        "remote_scope",
        "external_id",
        "description",
        "normalized_department",
        "seniority",
        "work_model",
        "employment_type",
        "url",
        "canonical_url",
        "job_fingerprint",
        "role_family",
        "first_seen_at",
        "last_seen_at",
        "last_status_change_at",
        "posting_status",
        "is_active",
    ],
    "scrape_runs": [
        "id",
        "company_id",
        "run_at",
        "jobs_found",
        "jobs_added",
        "jobs_removed",
        "status",
        "error_msg",
        "batch_id",
    ],
    "run_jobs": ["run_id", "job_id"],
    "job_events": ["id", "job_id", "run_id", "event_type", "created_at"],
    "company_tags": ["company_id", "tag"],
    "job_skills": ["job_id", "skill"],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Copy tracker data from SQLite into Postgres.")
    parser.add_argument(
        "--sqlite-path",
        default=str(Path(__file__).parent.parent / "data" / "tracker.db"),
        help="Path to the source SQLite database.",
    )
    parser.add_argument(
        "--postgres-url",
        default=os.getenv("DATABASE_URL") or os.getenv("TRACKER_DATABASE_URL"),
        help="Target Postgres connection string.",
    )
    return parser.parse_args()


def fetch_sqlite_rows(sqlite_path: str, table: str, columns: list[str]) -> list[tuple]:
    conn = sqlite3.connect(sqlite_path)
    try:
        rows = conn.execute(
            f"SELECT {', '.join(columns)} FROM {table} ORDER BY 1"
        ).fetchall()
        return rows
    finally:
        conn.close()


def reset_sequences(conn) -> None:
    for table in ("companies", "job_postings", "scrape_runs", "job_events"):
        conn.execute(
            f"""
            SELECT setval(
                pg_get_serial_sequence('{table}', 'id'),
                COALESCE((SELECT MAX(id) FROM {table}), 1),
                (SELECT COUNT(*) > 0 FROM {table})
            )
            """
        )


def main() -> None:
    args = parse_args()
    if not args.postgres_url:
        raise SystemExit("Missing --postgres-url or DATABASE_URL.")

    os.environ["DATABASE_URL"] = args.postgres_url
    init_db()

    pg_conn = get_connection()
    if pg_conn.backend != "postgres":
        raise SystemExit("DATABASE_URL did not resolve to a Postgres backend.")

    with pg_conn:
        pg_conn.execute(
            """
            TRUNCATE TABLE
                job_skills,
                company_tags,
                job_events,
                run_jobs,
                job_postings,
                scrape_runs,
                companies
            RESTART IDENTITY CASCADE
            """
        )

        for table, columns in TABLE_COLUMNS.items():
            rows = fetch_sqlite_rows(args.sqlite_path, table, columns)
            if not rows:
                continue
            placeholders = ", ".join("?" for _ in columns)
            pg_conn.executemany(
                f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})",
                rows,
            )

        reset_sequences(pg_conn)

    pg_conn.close()
    print("SQLite to Postgres migration complete.")


if __name__ == "__main__":
    main()
