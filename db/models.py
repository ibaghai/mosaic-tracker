import sqlite3
import os
from pathlib import Path

_DEFAULT_DB_PATH = Path(__file__).parent.parent / "data" / "tracker.db"
DB_PATH = Path(os.getenv("TRACKER_DB_PATH", str(_DEFAULT_DB_PATH)))


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = get_connection()
    with conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS companies (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                name             TEXT    NOT NULL UNIQUE,
                website          TEXT,
                ats_type         TEXT    NOT NULL,
                ats_identifier   TEXT,
                funding_round    TEXT,
                funding_amount_m REAL,
                funding_date     DATE,
                sector           TEXT,
                added_at         DATETIME DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS job_postings (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id       INTEGER NOT NULL REFERENCES companies(id),
                title            TEXT    NOT NULL,
                department       TEXT,
                location         TEXT,
                location_raw     TEXT,
                location_city    TEXT,
                location_region  TEXT,
                location_country TEXT,
                remote_scope     TEXT,
                external_id      TEXT,
                description      TEXT,
                normalized_department TEXT,
                seniority        TEXT,
                work_model       TEXT,
                employment_type  TEXT,
                url              TEXT,
                canonical_url    TEXT,
                job_fingerprint  TEXT,
                role_family      TEXT,
                first_seen_at    DATETIME DEFAULT (datetime('now')),
                last_seen_at     DATETIME DEFAULT (datetime('now')),
                last_status_change_at DATETIME DEFAULT (datetime('now')),
                posting_status   TEXT DEFAULT 'active',
                is_active        BOOLEAN  DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS scrape_runs (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id      INTEGER NOT NULL REFERENCES companies(id),
                run_at          DATETIME DEFAULT (datetime('now')),
                jobs_found      INTEGER  DEFAULT 0,
                jobs_added      INTEGER  DEFAULT 0,
                jobs_removed    INTEGER  DEFAULT 0,
                status          TEXT     DEFAULT 'success',
                error_msg       TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_job_postings_company ON job_postings(company_id);
            CREATE INDEX IF NOT EXISTS idx_job_postings_active  ON job_postings(is_active);
            CREATE INDEX IF NOT EXISTS idx_scrape_runs_company  ON scrape_runs(company_id);
            CREATE INDEX IF NOT EXISTS idx_scrape_runs_time     ON scrape_runs(run_at);

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

        alterations = [
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
        ]
        for stmt in alterations:
            try:
                conn.execute(stmt)
            except sqlite3.OperationalError as e:
                if "duplicate column" not in str(e).lower():
                    raise

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_job_postings_ext_id
            ON job_postings(company_id, external_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_job_postings_role_family
            ON job_postings(role_family)
        """)
    conn.close()
