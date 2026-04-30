import sqlite3
import os
from pathlib import Path

from db.env_loader import load_env_local

load_env_local()

_DEFAULT_DB_PATH = Path(__file__).parent.parent / "data" / "tracker.db"
DB_PATH = Path(os.getenv("TRACKER_DB_PATH", str(_DEFAULT_DB_PATH)))


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(row["name"] == column for row in rows)


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
                company_type     TEXT    DEFAULT 'startup',
                careers_url      TEXT,
                source_type      TEXT,
                source_confidence REAL,
                verification_status TEXT DEFAULT 'verified',
                last_verified_at DATETIME,
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
                source_type      TEXT,
                source_confidence REAL,
                verification_status TEXT DEFAULT 'verified',
                last_verified_at DATETIME,
                closure_reason   TEXT,
                last_liveness_check_at DATETIME,
                consecutive_misses INTEGER DEFAULT 0,
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
                error_msg       TEXT,
                batch_id        TEXT
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

            CREATE TABLE IF NOT EXISTS resume_profiles (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                resume_hash     TEXT NOT NULL UNIQUE,
                label           TEXT,
                profile_json    TEXT NOT NULL,
                provider        TEXT NOT NULL,
                model           TEXT NOT NULL,
                prompt_version  TEXT NOT NULL,
                created_at      DATETIME DEFAULT (datetime('now')),
                last_seen_at    DATETIME DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_resume_profiles_hash ON resume_profiles(resume_hash);

            CREATE TABLE IF NOT EXISTS resume_job_fits (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                resume_id           INTEGER NOT NULL REFERENCES resume_profiles(id) ON DELETE CASCADE,
                job_id              INTEGER NOT NULL REFERENCES job_postings(id) ON DELETE CASCADE,
                deterministic_score REAL NOT NULL,
                fit_score           INTEGER NOT NULL,
                verdict             TEXT NOT NULL,
                rationale_json      TEXT NOT NULL,
                gaps_json           TEXT NOT NULL,
                suggestions_json    TEXT NOT NULL,
                location_note       TEXT,
                location_blocker    BOOLEAN DEFAULT 0,
                provider            TEXT NOT NULL,
                model               TEXT NOT NULL,
                prompt_version      TEXT NOT NULL,
                created_at          DATETIME DEFAULT (datetime('now')),
                updated_at          DATETIME DEFAULT (datetime('now')),
                UNIQUE(resume_id, job_id, prompt_version)
            );
            CREATE INDEX IF NOT EXISTS idx_resume_job_fits_resume ON resume_job_fits(resume_id);
            CREATE INDEX IF NOT EXISTS idx_resume_job_fits_job ON resume_job_fits(job_id);

            CREATE TABLE IF NOT EXISTS people (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                apollo_id           TEXT,
                name                TEXT NOT NULL,
                title               TEXT,
                company_id          INTEGER REFERENCES companies(id) ON DELETE SET NULL,
                company_name        TEXT,
                linkedin_url        TEXT,
                email               TEXT,
                email_status        TEXT,
                phone               TEXT,
                bio_summary         TEXT,
                seniority           TEXT,
                departments_json    TEXT,
                tenure_start_date   DATE,
                archetype           TEXT,
                last_verified_at    DATETIME,
                source              TEXT,
                raw_payload_json    TEXT,
                created_at          DATETIME DEFAULT (datetime('now')),
                updated_at          DATETIME DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_people_company ON people(company_id);
            CREATE INDEX IF NOT EXISTS idx_people_apollo_id ON people(apollo_id);
            CREATE INDEX IF NOT EXISTS idx_people_archetype ON people(archetype);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_people_apollo_unique
                ON people(apollo_id) WHERE apollo_id IS NOT NULL;

            CREATE TABLE IF NOT EXISTS outreach_drafts (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                person_id       INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
                job_id          INTEGER NOT NULL REFERENCES job_postings(id) ON DELETE CASCADE,
                resume_id       INTEGER REFERENCES resume_profiles(id) ON DELETE SET NULL,
                archetype       TEXT,
                subject         TEXT,
                message         TEXT NOT NULL,
                rationale_json  TEXT,
                tone            TEXT,
                provider        TEXT NOT NULL,
                model           TEXT NOT NULL,
                prompt_version  TEXT NOT NULL,
                user_edits      TEXT,
                created_at      DATETIME DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_outreach_drafts_job ON outreach_drafts(job_id);
            CREATE INDEX IF NOT EXISTS idx_outreach_drafts_person ON outreach_drafts(person_id);

            CREATE TABLE IF NOT EXISTS tailored_resumes (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                resume_id           INTEGER NOT NULL REFERENCES resume_profiles(id) ON DELETE CASCADE,
                job_id              INTEGER NOT NULL REFERENCES job_postings(id) ON DELETE CASCADE,
                tailored_text       TEXT NOT NULL,
                diff_summary_json   TEXT,
                provider            TEXT NOT NULL,
                model               TEXT NOT NULL,
                prompt_version      TEXT NOT NULL,
                created_at          DATETIME DEFAULT (datetime('now')),
                UNIQUE(resume_id, job_id, prompt_version)
            );
            CREATE INDEX IF NOT EXISTS idx_tailored_resumes_resume ON tailored_resumes(resume_id);
            CREATE INDEX IF NOT EXISTS idx_tailored_resumes_job ON tailored_resumes(job_id);

            CREATE TABLE IF NOT EXISTS users (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                email           TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash   TEXT NOT NULL,
                created_at      DATETIME DEFAULT (datetime('now')),
                last_login_at   DATETIME
            );

            CREATE TABLE IF NOT EXISTS sessions (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                token_hash      TEXT NOT NULL UNIQUE,
                user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                created_at      DATETIME DEFAULT (datetime('now')),
                expires_at      DATETIME NOT NULL,
                last_used_at    DATETIME DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
            CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at);

            CREATE TABLE IF NOT EXISTS saved_searches (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                surface         TEXT NOT NULL,           -- "jobs" | "outreach" | "pipeline" | ...
                name            TEXT NOT NULL,
                params_json     TEXT NOT NULL,
                created_at      DATETIME DEFAULT (datetime('now')),
                last_run_at     DATETIME,
                UNIQUE(user_id, surface, name)
            );
            CREATE INDEX IF NOT EXISTS idx_saved_searches_user ON saved_searches(user_id);

            CREATE TABLE IF NOT EXISTS user_job_status (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id        INTEGER NOT NULL UNIQUE REFERENCES job_postings(id) ON DELETE CASCADE,
                status        TEXT NOT NULL,
                notes         TEXT,
                action_at     DATETIME DEFAULT (datetime('now')),
                outcome       TEXT,
                outcome_at    DATETIME,
                updated_at    DATETIME DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_user_job_status_status ON user_job_status(status);

            CREATE TABLE IF NOT EXISTS apollo_api_calls (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                endpoint        TEXT NOT NULL,
                request_summary TEXT,
                credits_used    INTEGER,
                status_code     INTEGER,
                error_msg       TEXT,
                called_at       DATETIME DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_apollo_api_calls_called_at ON apollo_api_calls(called_at);
        """)

        alterations = {
            "companies": [
                ("company_type", "TEXT DEFAULT 'startup'"),
                ("careers_url", "TEXT"),
                ("source_type", "TEXT"),
                ("source_confidence", "REAL"),
                ("verification_status", "TEXT DEFAULT 'verified'"),
                ("last_verified_at", "DATETIME"),
                ("apollo_organization_id", "TEXT"),
            ],
            "job_postings": [
                ("external_id", "TEXT"),
                ("description", "TEXT"),
                ("normalized_department", "TEXT"),
                ("seniority", "TEXT"),
                ("work_model", "TEXT"),
                ("location_raw", "TEXT"),
                ("location_city", "TEXT"),
                ("location_region", "TEXT"),
                ("location_country", "TEXT"),
                ("remote_scope", "TEXT"),
                ("role_family", "TEXT"),
                ("canonical_url", "TEXT"),
                ("job_fingerprint", "TEXT"),
                ("source_type", "TEXT"),
                ("source_confidence", "REAL"),
                ("verification_status", "TEXT DEFAULT 'verified'"),
                ("last_verified_at", "DATETIME"),
                ("closure_reason", "TEXT"),
                ("last_liveness_check_at", "DATETIME"),
                ("consecutive_misses", "INTEGER DEFAULT 0"),
                ("last_status_change_at", "DATETIME"),
                ("posting_status", "TEXT DEFAULT 'active'"),
            ],
            "scrape_runs": [
                ("batch_id", "TEXT"),
            ],
            "outreach_drafts": [
                # Lifecycle: draft (default) → sent → replied / no_reply / bounced
                ("status", "TEXT DEFAULT 'draft'"),
                ("sent_at", "DATETIME"),
                ("sent_via", "TEXT"),  # gmail | mail | linkedin | manual
                ("replied_at", "DATETIME"),
                ("reply_text", "TEXT"),
                ("reply_category", "TEXT"),  # positive | neutral | negative | interview
                ("follow_up_due_at", "DATETIME"),
                # Multi-tenant scope. Backfilled NULL on first migration; rows
                # without a user_id are hidden (we wipe in init_db on first run
                # of the auth migration).
                ("user_id", "INTEGER REFERENCES users(id) ON DELETE CASCADE"),
            ],
            "user_job_status": [
                ("user_id", "INTEGER REFERENCES users(id) ON DELETE CASCADE"),
            ],
            "resume_profiles": [
                ("user_id", "INTEGER REFERENCES users(id) ON DELETE CASCADE"),
            ],
            "tailored_resumes": [
                ("user_id", "INTEGER REFERENCES users(id) ON DELETE CASCADE"),
            ],
            "resume_job_fits": [
                ("user_id", "INTEGER REFERENCES users(id) ON DELETE CASCADE"),
            ],
        }

        for table, columns in alterations.items():
            for column, definition in columns:
                if not _column_exists(conn, table, column):
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_job_postings_ext_id
            ON job_postings(company_id, external_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_job_postings_canonical_url
            ON job_postings(company_id, canonical_url)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_job_postings_fingerprint
            ON job_postings(company_id, job_fingerprint)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_job_postings_role_family
            ON job_postings(role_family)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_outreach_drafts_status
            ON outreach_drafts(status, sent_at)
        """)

        # ── Auth migration ──────────────────────────────────────────────────
        # When the auth feature lands, every user-scoped table grows a user_id
        # column (above) and any pre-auth rows are abandoned. Detection: if
        # outreach_drafts has any rows whose user_id is NULL, this is the
        # first time we've seen the auth migration on this DB → wipe the
        # legacy rows. Idempotent: once all rows are scoped, the wipe is a
        # no-op.
        legacy = conn.execute(
            "SELECT 1 FROM outreach_drafts WHERE user_id IS NULL LIMIT 1"
        ).fetchone()
        if legacy:
            conn.executescript("""
                DELETE FROM outreach_drafts;
                DELETE FROM user_job_status;
                DELETE FROM resume_job_fits;
                DELETE FROM tailored_resumes;
                DELETE FROM resume_profiles;
            """)

        # The original user_job_status had `job_id INTEGER UNIQUE` — fine for
        # a single-user app, broken once two users want to save the same job.
        # Recreate with `UNIQUE(user_id, job_id)` if the old constraint is
        # still in place. SQLite doesn't allow dropping a column constraint
        # in place, so we rebuild the table. Safe because the wipe above just
        # cleared all rows.
        cols = conn.execute("PRAGMA table_info(user_job_status)").fetchall()
        idx_list = conn.execute("PRAGMA index_list(user_job_status)").fetchall()
        # Look for an auto-created unique index on (job_id) alone.
        legacy_unique = False
        for idx in idx_list:
            if not idx[2]:  # not UNIQUE
                continue
            cols_in_idx = conn.execute(
                f"PRAGMA index_info({idx[1]!r})"
            ).fetchall()
            names = [c[2] for c in cols_in_idx]
            if names == ["job_id"]:
                legacy_unique = True
                break
        if legacy_unique:
            conn.executescript("""
                CREATE TABLE user_job_status_new (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id        INTEGER NOT NULL REFERENCES job_postings(id) ON DELETE CASCADE,
                    status        TEXT NOT NULL,
                    notes         TEXT,
                    action_at     DATETIME DEFAULT (datetime('now')),
                    outcome       TEXT,
                    outcome_at    DATETIME,
                    updated_at    DATETIME DEFAULT (datetime('now')),
                    user_id       INTEGER REFERENCES users(id) ON DELETE CASCADE,
                    UNIQUE(user_id, job_id)
                );
                INSERT INTO user_job_status_new
                    (id, job_id, status, notes, action_at, outcome, outcome_at, updated_at, user_id)
                SELECT id, job_id, status, notes, action_at, outcome, outcome_at, updated_at, user_id
                FROM user_job_status;
                DROP TABLE user_job_status;
                ALTER TABLE user_job_status_new RENAME TO user_job_status;
                CREATE INDEX IF NOT EXISTS idx_user_job_status_status ON user_job_status(status);
                CREATE INDEX IF NOT EXISTS idx_user_job_status_user ON user_job_status(user_id);
            """)
    conn.close()
