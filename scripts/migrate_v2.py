#!/usr/bin/env python3
"""
Schema migration for v2: adds run_jobs, job_events, company_tags, job_skills
tables and new columns on job_postings, scrape_runs, companies.
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "tracker.db"


def migrate():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    with conn:
        # ── New tables ────────────────────────────────────────────────────

        conn.executescript("""
            CREATE TABLE IF NOT EXISTS run_jobs (
                run_id  INTEGER NOT NULL REFERENCES scrape_runs(id),
                job_id  INTEGER NOT NULL REFERENCES job_postings(id),
                PRIMARY KEY (run_id, job_id)
            ) WITHOUT ROWID;

            CREATE INDEX IF NOT EXISTS idx_run_jobs_job ON run_jobs(job_id);

            CREATE TABLE IF NOT EXISTS job_events (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id      INTEGER NOT NULL REFERENCES job_postings(id),
                run_id      INTEGER NOT NULL REFERENCES scrape_runs(id),
                event_type  TEXT NOT NULL,
                created_at  DATETIME DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_job_events_run       ON job_events(run_id);
            CREATE INDEX IF NOT EXISTS idx_job_events_type_date  ON job_events(event_type, created_at);
            CREATE INDEX IF NOT EXISTS idx_job_events_job        ON job_events(job_id);

            CREATE TABLE IF NOT EXISTS company_tags (
                company_id INTEGER NOT NULL REFERENCES companies(id),
                tag        TEXT NOT NULL,
                PRIMARY KEY (company_id, tag)
            ) WITHOUT ROWID;

            CREATE INDEX IF NOT EXISTS idx_company_tags_tag ON company_tags(tag);

            CREATE TABLE IF NOT EXISTS job_skills (
                job_id  INTEGER NOT NULL REFERENCES job_postings(id),
                skill   TEXT NOT NULL,
                PRIMARY KEY (job_id, skill)
            ) WITHOUT ROWID;

            CREATE INDEX IF NOT EXISTS idx_job_skills_skill ON job_skills(skill);
        """)

        # ── New columns (safe: ALTER ignores if column exists in newer SQLite,
        #    but we catch the error for older versions) ────────────────────

        alterations = [
            # job_postings
            "ALTER TABLE job_postings ADD COLUMN external_id TEXT",
            "ALTER TABLE job_postings ADD COLUMN description TEXT",
            "ALTER TABLE job_postings ADD COLUMN normalized_department TEXT",
            "ALTER TABLE job_postings ADD COLUMN seniority TEXT",
            "ALTER TABLE job_postings ADD COLUMN work_model TEXT",
            "ALTER TABLE job_postings ADD COLUMN location_raw TEXT",
            "ALTER TABLE job_postings ADD COLUMN location_city TEXT",
            "ALTER TABLE job_postings ADD COLUMN location_region TEXT",
            "ALTER TABLE job_postings ADD COLUMN location_country TEXT",
            "ALTER TABLE job_postings ADD COLUMN remote_scope TEXT",
            "ALTER TABLE job_postings ADD COLUMN role_family TEXT",
            "ALTER TABLE job_postings ADD COLUMN canonical_url TEXT",
            "ALTER TABLE job_postings ADD COLUMN job_fingerprint TEXT",
            "ALTER TABLE job_postings ADD COLUMN last_status_change_at DATETIME",
            "ALTER TABLE job_postings ADD COLUMN posting_status TEXT DEFAULT 'active'",
            # scrape_runs
            "ALTER TABLE scrape_runs ADD COLUMN batch_id TEXT",
            # companies
            "ALTER TABLE companies ADD COLUMN company_type TEXT DEFAULT 'startup'",
            "ALTER TABLE companies ADD COLUMN hq_location TEXT",
            "ALTER TABLE companies ADD COLUMN employee_count_range TEXT",
            "ALTER TABLE companies ADD COLUMN founded_year INTEGER",
            "ALTER TABLE companies ADD COLUMN is_active BOOLEAN DEFAULT 1",
        ]

        for stmt in alterations:
            try:
                conn.execute(stmt)
            except sqlite3.OperationalError as e:
                if "duplicate column" in str(e).lower():
                    pass
                else:
                    raise

        # ── Composite index for external_id matching ──────────────────────
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_job_postings_ext_id
            ON job_postings(company_id, external_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_job_postings_role_family
            ON job_postings(role_family)
        """)

    conn.execute("PRAGMA optimize")
    conn.close()
    print("Migration complete.")


if __name__ == "__main__":
    migrate()
