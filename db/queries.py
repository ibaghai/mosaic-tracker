from datetime import datetime
from typing import Optional, List, Tuple
import hashlib
import re
from urllib.parse import urlsplit, urlunsplit
from db.models import get_connection


# ── Companies ─────────────────────────────────────────────────────────────────

def upsert_company(company: dict) -> int:  # noqa: E501
    """Insert or update a company. Returns its row id."""
    conn = get_connection()
    with conn:
        conn.execute("""
            INSERT INTO companies
                (name, website, ats_type, ats_identifier,
                 funding_round, funding_amount_m, funding_date, sector, company_type)
            VALUES
                (:name, :website, :ats_type, :ats_identifier,
                 :funding_round, :funding_amount_m, :funding_date, :sector, :company_type)
            ON CONFLICT(name) DO UPDATE SET
                website          = excluded.website,
                ats_type         = excluded.ats_type,
                ats_identifier   = excluded.ats_identifier,
                funding_round    = excluded.funding_round,
                funding_amount_m = excluded.funding_amount_m,
                funding_date     = excluded.funding_date,
                sector           = excluded.sector,
                company_type     = excluded.company_type
        """, company)
        row = conn.execute(
            "SELECT id FROM companies WHERE name = ?", (company["name"],)
        ).fetchone()
    conn.close()
    return row["id"]


def get_all_companies() -> List[dict]:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM companies ORDER BY name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Job Postings ───────────────────────────────────────────────────────────────

_MULTISPACE_RE = re.compile(r"\s+")


def _normalize_text(value: Optional[str]) -> str:
    if not value:
        return ""
    return _MULTISPACE_RE.sub(" ", value.strip().lower())


def _canonicalize_url(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    parts = urlsplit(value.strip())
    if not parts.scheme or not parts.netloc:
        return value.strip()
    path = parts.path.rstrip("/") or parts.path
    return urlunsplit((parts.scheme, parts.netloc.lower(), path, "", ""))


def _build_job_fingerprint(company_id: int, job: dict) -> str:
    ext_id = job.get("external_id")
    if ext_id:
        return f"ext:{company_id}:{ext_id}"
    canonical_url = _canonicalize_url(job.get("url")) or ""
    location = _normalize_text(job.get("location"))
    title = _normalize_text(job.get("title"))
    raw = f"{company_id}|{title}|{location}|{canonical_url}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()

def log_run(company_id: int, jobs_found: int, jobs_added: int,
            jobs_removed: int, status: str = "success",
            error_msg: Optional[str] = None,
            batch_id: Optional[str] = None) -> int:
    """Insert a scrape_run row and return its id."""
    conn = get_connection()
    with conn:
        cur = conn.execute("""
            INSERT INTO scrape_runs
                (company_id, jobs_found, jobs_added, jobs_removed, status, error_msg, batch_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (company_id, jobs_found, jobs_added, jobs_removed, status, error_msg, batch_id))
        run_id = cur.lastrowid
    conn.close()
    return run_id


def sync_jobs(company_id: int, run_id: int, scraped_jobs: List[dict]) -> Tuple[int, int]:
    """
    Event-driven job sync. Populates run_jobs and job_events.
    Returns (jobs_added, jobs_removed).
    """
    conn = get_connection()
    now = datetime.utcnow().isoformat()

    # Current active jobs for this company — prefer external_id matching
    existing = conn.execute(
        "SELECT id, title, external_id FROM job_postings WHERE company_id = ? AND is_active = 1",
        (company_id,)
    ).fetchall()

    # Build lookup: external_id → row_id, and title → row_id (fallback)
    by_ext_id = {}  # type: dict
    by_title = {}   # type: dict
    for r in existing:
        if r["external_id"]:
            by_ext_id[r["external_id"]] = r["id"]
        by_title[r["title"]] = r["id"]

    matched_ids = set()  # track which existing jobs were seen this run
    added = 0

    with conn:
        for job in scraped_jobs:
            ext_id = job.get("external_id")
            title = job["title"]
            canonical_url = _canonicalize_url(job.get("url"))
            fingerprint = _build_job_fingerprint(company_id, job)

            # Match by external_id first, then fall back to title
            existing_id = None
            if ext_id and ext_id in by_ext_id:
                existing_id = by_ext_id[ext_id]
            elif title in by_title:
                existing_id = by_title[title]

            if existing_id:
                # Existing job — update last_seen, backfill external_id + description
                matched_ids.add(existing_id)
                conn.execute("""
                    UPDATE job_postings
                    SET last_seen_at = ?,
                        last_status_change_at = CASE
                            WHEN posting_status IS NOT 'active' THEN ?
                            ELSE last_status_change_at
                        END,
                        posting_status = 'active',
                        external_id = COALESCE(external_id, ?),
                        description = COALESCE(description, ?),
                        canonical_url = COALESCE(canonical_url, ?),
                        job_fingerprint = COALESCE(job_fingerprint, ?),
                        location_raw = COALESCE(location_raw, location, ?)
                    WHERE id = ?
                """, (
                    now,
                    now,
                    ext_id,
                    job.get("description"),
                    canonical_url,
                    fingerprint,
                    job.get("location"),
                    existing_id,
                ))
                conn.execute(
                    "INSERT OR IGNORE INTO run_jobs (run_id, job_id) VALUES (?, ?)",
                    (run_id, existing_id)
                )
            else:
                # New job
                cur = conn.execute("""
                    INSERT INTO job_postings
                        (company_id, title, external_id, description, department,
                         location, location_raw, employment_type, url, canonical_url,
                         job_fingerprint, first_seen_at, last_seen_at, last_status_change_at,
                         posting_status, is_active)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', 1)
                """, (
                    company_id, title, ext_id,
                    job.get("description"), job.get("department"),
                    job.get("location"), job.get("location"), job.get("employment_type"),
                    job.get("url"), canonical_url, fingerprint, now, now, now,
                ))
                new_id = cur.lastrowid
                conn.execute(
                    "INSERT INTO run_jobs (run_id, job_id) VALUES (?, ?)",
                    (run_id, new_id)
                )
                conn.execute(
                    "INSERT INTO job_events (job_id, run_id, event_type) VALUES (?, ?, 'added')",
                    (new_id, run_id)
                )
                added += 1

        # Mark disappeared jobs inactive
        all_existing_ids = {r["id"] for r in existing}
        removed_ids = all_existing_ids - matched_ids
        removed = len(removed_ids)
        for job_id in removed_ids:
            conn.execute(
                """
                UPDATE job_postings
                SET is_active = 0,
                    posting_status = 'closed',
                    last_status_change_at = ?
                WHERE id = ?
                """,
                (now, job_id)
            )
            conn.execute(
                "INSERT INTO job_events (job_id, run_id, event_type) VALUES (?, ?, 'removed')",
                (job_id, run_id)
            )

    conn.close()
    return added, removed


# ── Dashboard Queries ──────────────────────────────────────────────────────────

def get_company_stats() -> list:
    """Companies with active job count and last scrape info."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT
            c.id,
            c.name,
            c.sector,
            c.company_type,
            c.ats_type,
            c.funding_round,
            c.funding_amount_m,
            c.funding_date,
            c.website,
            COALESCE(j.active_jobs, 0)   AS active_jobs,
            sr.last_scraped,
            COALESCE(sr.total_added, 0)   AS total_added,
            COALESCE(sr.total_removed, 0) AS total_removed
        FROM companies c
        LEFT JOIN (
            SELECT company_id, COUNT(*) AS active_jobs
            FROM job_postings
            WHERE is_active = 1
            GROUP BY company_id
        ) j ON j.company_id = c.id
        LEFT JOIN (
            SELECT company_id,
                   MAX(run_at)        AS last_scraped,
                   SUM(jobs_added)    AS total_added,
                   SUM(jobs_removed)  AS total_removed
            FROM scrape_runs
            GROUP BY company_id
        ) sr ON sr.company_id = c.id
        ORDER BY active_jobs DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_active_jobs(
    company_id: Optional[int] = None,
    exclude_company_ids: Optional[List[int]] = None,
    sector: Optional[str] = None,
    search: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    location: Optional[str] = None,
    employment_type: Optional[str] = None,
    skill: Optional[str] = None,
    seniority: Optional[str] = None,
    work_model: Optional[str] = None,
    company_type: Optional[str] = None,
    department: Optional[str] = None,
) -> list:
    """Active job postings with optional filters."""
    conn = get_connection()
    if skill:
        sql = """
            SELECT jp.*, c.name AS company_name, c.sector
            FROM job_postings jp
            JOIN companies c ON c.id = jp.company_id
            JOIN job_skills js ON js.job_id = jp.id
            WHERE jp.is_active = 1 AND js.skill = ?
        """
        params = [skill]
    else:
        sql = """
            SELECT jp.*, c.name AS company_name, c.sector
            FROM job_postings jp
            JOIN companies c ON c.id = jp.company_id
            WHERE jp.is_active = 1
        """
        params = []
    if company_id:
        sql += " AND jp.company_id = ?"
        params.append(company_id)
    if exclude_company_ids:
        placeholders = ",".join("?" for _ in exclude_company_ids)
        sql += f" AND jp.company_id NOT IN ({placeholders})"
        params.extend(exclude_company_ids)
    if sector:
        sql += " AND c.sector = ?"
        params.append(sector)
    if company_type:
        sql += " AND c.company_type = ?"
        params.append(company_type)
    if search:
        sql += " AND (jp.title LIKE ? OR jp.department LIKE ?)"
        params += [f"%{search}%", f"%{search}%"]
    if date_from:
        sql += " AND DATE(jp.first_seen_at) >= ?"
        params.append(date_from)
    if date_to:
        sql += " AND DATE(jp.first_seen_at) <= ?"
        params.append(date_to)
    if location:
        sql += " AND jp.location LIKE ?"
        params.append(f"%{location}%")
    if employment_type:
        sql += " AND jp.employment_type = ?"
        params.append(employment_type)
    if seniority:
        sql += " AND jp.seniority = ?"
        params.append(seniority)
    if work_model:
        sql += " AND jp.work_model = ?"
        params.append(work_model)
    if department:
        sql += " AND jp.normalized_department = ?"
        params.append(department)
    sql += " ORDER BY jp.first_seen_at DESC"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_role_family_breakdown(company_type=None):
    # type: (Optional[str]) -> list
    conn = get_connection()
    where = "WHERE jp.is_active = 1 AND jp.role_family IS NOT NULL"
    params = []
    if company_type:
        where += " AND c.company_type = ?"
        params.append(company_type)
    rows = conn.execute("""
        SELECT jp.role_family, COUNT(*) AS count
        FROM job_postings jp
        JOIN companies c ON c.id = jp.company_id
        {}
        GROUP BY jp.role_family
        ORDER BY count DESC
    """.format(where), params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_remote_mix_by_sector(company_type="startup"):
    # type: (Optional[str]) -> list
    conn = get_connection()
    where = "WHERE jp.is_active = 1 AND jp.work_model IS NOT NULL"
    params = []
    if company_type:
        where += " AND c.company_type = ?"
        params.append(company_type)
    rows = conn.execute("""
        SELECT c.sector, jp.work_model, COUNT(*) AS count
        FROM job_postings jp
        JOIN companies c ON c.id = jp.company_id
        {}
        GROUP BY c.sector, jp.work_model
        ORDER BY c.sector, count DESC
    """.format(where), params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_freshness_breakdown(company_type=None):
    # type: (Optional[str]) -> list
    conn = get_connection()
    where = "WHERE jp.is_active = 1"
    params = []
    if company_type:
        where += " AND c.company_type = ?"
        params.append(company_type)
    rows = conn.execute("""
        SELECT
            CASE
                WHEN julianday('now') - julianday(jp.first_seen_at) <= 3 THEN '0-3 days'
                WHEN julianday('now') - julianday(jp.first_seen_at) <= 7 THEN '4-7 days'
                WHEN julianday('now') - julianday(jp.first_seen_at) <= 14 THEN '8-14 days'
                WHEN julianday('now') - julianday(jp.first_seen_at) <= 30 THEN '15-30 days'
                ELSE '30+ days'
            END AS bucket,
            COUNT(*) AS count
        FROM job_postings jp
        JOIN companies c ON c.id = jp.company_id
        {}
        GROUP BY bucket
        ORDER BY
            CASE bucket
                WHEN '0-3 days' THEN 1
                WHEN '4-7 days' THEN 2
                WHEN '8-14 days' THEN 3
                WHEN '15-30 days' THEN 4
                ELSE 5
            END
    """.format(where), params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_company_velocity(days=7):
    # type: (int) -> list
    """Per-company net job change over the last N days."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT c.id AS company_id,
               SUM(CASE WHEN je.event_type = 'added' THEN 1 ELSE 0 END) AS added,
               SUM(CASE WHEN je.event_type = 'removed' THEN 1 ELSE 0 END) AS removed,
               SUM(CASE WHEN je.event_type = 'added' THEN 1 ELSE 0 END)
                 - SUM(CASE WHEN je.event_type = 'removed' THEN 1 ELSE 0 END) AS net
        FROM job_events je
        JOIN job_postings jp ON jp.id = je.job_id
        JOIN companies c ON c.id = jp.company_id
        WHERE je.created_at >= datetime('now', ?)
        GROUP BY c.id
    """, ("-{} days".format(days),)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_company_detail(company_id):
    # type: (int) -> Optional[dict]
    """Single company with stats for the detail page."""
    conn = get_connection()
    row = conn.execute("""
        SELECT c.*,
               COALESCE(j.active_jobs, 0) AS active_jobs,
               COALESCE(sr.total_added, 0) AS total_added,
               COALESCE(sr.total_removed, 0) AS total_removed,
               sr.last_scraped
        FROM companies c
        LEFT JOIN (
            SELECT company_id, COUNT(*) AS active_jobs
            FROM job_postings WHERE is_active = 1
            GROUP BY company_id
        ) j ON j.company_id = c.id
        LEFT JOIN (
            SELECT company_id,
                   MAX(run_at) AS last_scraped,
                   SUM(jobs_added) AS total_added,
                   SUM(jobs_removed) AS total_removed
            FROM scrape_runs GROUP BY company_id
        ) sr ON sr.company_id = c.id
        WHERE c.id = ?
    """, (company_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_company_skills(company_id, limit=15):
    # type: (int, int) -> list
    """Top skills for a specific company."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT js.skill, COUNT(*) AS count
        FROM job_skills js
        JOIN job_postings jp ON jp.id = js.job_id
        WHERE jp.company_id = ? AND jp.is_active = 1
        GROUP BY js.skill
        ORDER BY count DESC
        LIMIT ?
    """, (company_id, limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_company_department_breakdown(company_id):
    # type: (int) -> list
    """Department breakdown for a single company."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT normalized_department AS category, COUNT(*) AS job_count
        FROM job_postings
        WHERE company_id = ? AND is_active = 1 AND normalized_department IS NOT NULL
        GROUP BY normalized_department
        ORDER BY job_count DESC
    """, (company_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_scraper_health():
    # type: () -> list
    """Last scrape status per company for health monitoring."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT c.id, c.name, c.sector, c.ats_type,
               c.company_type,
               sr.run_at AS last_run,
               sr.status,
               sr.error_msg,
               sr.jobs_found,
               COALESCE(j.active_jobs, 0) AS active_jobs
        FROM companies c
        LEFT JOIN (
            SELECT company_id, MAX(run_at) AS max_run
            FROM scrape_runs GROUP BY company_id
        ) latest ON latest.company_id = c.id
        LEFT JOIN scrape_runs sr
            ON sr.company_id = c.id AND sr.run_at = latest.max_run
        LEFT JOIN (
            SELECT company_id, COUNT(*) AS active_jobs
            FROM job_postings WHERE is_active = 1
            GROUP BY company_id
        ) j ON j.company_id = c.id
        ORDER BY sr.run_at DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_filter_options() -> dict:
    """Distinct values for filter dropdowns."""
    conn = get_connection()
    locations = [
        r[0] for r in conn.execute(
            "SELECT DISTINCT location FROM job_postings WHERE is_active=1 AND location IS NOT NULL ORDER BY location"
        ).fetchall()
    ]
    emp_types = [
        r[0] for r in conn.execute(
            "SELECT DISTINCT employment_type FROM job_postings WHERE is_active=1 AND employment_type IS NOT NULL ORDER BY employment_type"
        ).fetchall()
    ]
    conn.close()
    return {"locations": locations, "employment_types": emp_types}


def get_job_count_over_time() -> list:
    """Daily active job count per startup company for trend charts.
    Uses the latest run per company per day to avoid double-counting."""
    conn = get_connection()
    rows = conn.execute("""
        WITH latest_per_day AS (
            SELECT
                sr.company_id,
                DATE(sr.run_at)   AS date,
                MAX(sr.run_at)    AS latest_run
            FROM scrape_runs sr
            JOIN companies c ON c.id = sr.company_id
            WHERE sr.status = 'success'
              AND c.company_type = 'startup'
            GROUP BY sr.company_id, DATE(sr.run_at)
        )
        SELECT
            c.name      AS company,
            c.sector,
            lpd.date,
            sr.jobs_found AS job_count
        FROM latest_per_day lpd
        JOIN scrape_runs sr
          ON sr.company_id = lpd.company_id
         AND sr.run_at = lpd.latest_run
        JOIN companies c ON c.id = lpd.company_id
        ORDER BY lpd.date
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_sector_breakdown() -> list:
    """Active job counts grouped by sector."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT c.sector, COUNT(*) AS job_count
        FROM job_postings jp
        JOIN companies c ON c.id = jp.company_id
        WHERE jp.is_active = 1
        GROUP BY c.sector
        ORDER BY job_count DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_department_breakdown(company_type=None):
    # type: (Optional[str]) -> list
    """Active job counts using pre-computed normalized_department."""
    conn = get_connection()
    where = "WHERE jp.is_active = 1 AND jp.normalized_department IS NOT NULL"
    params = []  # type: list
    if company_type:
        where += " AND c.company_type = ?"
        params.append(company_type)
    rows = conn.execute("""
        SELECT jp.normalized_department AS category, COUNT(*) AS job_count
        FROM job_postings jp
        JOIN companies c ON c.id = jp.company_id
        {}
        GROUP BY jp.normalized_department
        ORDER BY job_count DESC
    """.format(where), params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_overview_stats(company_type=None):
    # type: (Optional[str]) -> dict
    conn = get_connection()
    ct_clause = f" AND c.company_type = '{company_type}'" if company_type else ""
    ct_where  = f" WHERE company_type = '{company_type}'" if company_type else ""

    total_companies = conn.execute(
        f"SELECT COUNT(*) FROM companies{ct_where}"
    ).fetchone()[0]
    total_active_jobs = conn.execute(
        f"SELECT COUNT(*) FROM job_postings jp JOIN companies c ON c.id = jp.company_id WHERE jp.is_active = 1{ct_clause}"
    ).fetchone()[0]
    last_run = conn.execute(
        "SELECT MAX(run_at) FROM scrape_runs WHERE status = 'success'"
    ).fetchone()[0]

    # Net change from last batch (filtered by company_type if supplied)
    last_batch = conn.execute(
        "SELECT batch_id FROM scrape_runs WHERE batch_id IS NOT NULL ORDER BY run_at DESC LIMIT 1"
    ).fetchone()
    net_added = 0
    net_removed = 0
    if last_batch:
        bid = last_batch[0]
        if company_type:
            r = conn.execute(
                """SELECT COALESCE(SUM(sr.jobs_added),0), COALESCE(SUM(sr.jobs_removed),0)
                   FROM scrape_runs sr
                   JOIN companies c ON c.id = sr.company_id
                   WHERE sr.batch_id = ? AND c.company_type = ?""",
                (bid, company_type)
            ).fetchone()
        else:
            r = conn.execute(
                "SELECT COALESCE(SUM(jobs_added),0), COALESCE(SUM(jobs_removed),0) FROM scrape_runs WHERE batch_id = ?",
                (bid,)
            ).fetchone()
        net_added = r[0]
        net_removed = r[1]

    conn.close()
    return {
        "total_companies": total_companies,
        "total_active_jobs": total_active_jobs,
        "last_run": last_run,
        "net_added": net_added,
        "net_removed": net_removed,
    }


# ── New Dashboard Queries ─────────────────────────────────────────────────────

def get_recent_events(limit=200, event_type=None, sector=None, company_name=None):
    # type: (int, Optional[str], Optional[str], Optional[str]) -> list
    """Recent job events for the Changes page."""
    conn = get_connection()
    where = "WHERE 1=1"
    params = []  # type: list
    if event_type:
        where += " AND je.event_type = ?"
        params.append(event_type)
    if sector:
        where += " AND c.sector = ?"
        params.append(sector)
    if company_name:
        where += " AND c.name = ?"
        params.append(company_name)
    params.append(limit)
    rows = conn.execute("""
        SELECT je.event_type, je.created_at,
               jp.title, jp.department, jp.location, jp.normalized_department,
               c.name AS company, c.id AS company_id, c.sector, c.company_type
        FROM job_events je
        JOIN job_postings jp ON jp.id = je.job_id
        JOIN companies c ON c.id = jp.company_id
        {}
        ORDER BY je.created_at DESC
        LIMIT ?
    """.format(where), params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_fastest_movers(days=7):
    # type: (int) -> list
    """Companies ranked by absolute net change in the last N days."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT c.name, c.id AS company_id, c.sector, c.company_type,
               SUM(CASE WHEN je.event_type = 'added' THEN 1 ELSE 0 END) AS added,
               SUM(CASE WHEN je.event_type = 'removed' THEN 1 ELSE 0 END) AS removed,
               SUM(CASE WHEN je.event_type = 'added' THEN 1 ELSE 0 END)
                 - SUM(CASE WHEN je.event_type = 'removed' THEN 1 ELSE 0 END) AS net
        FROM job_events je
        JOIN job_postings jp ON jp.id = je.job_id
        JOIN companies c ON c.id = jp.company_id
        WHERE je.created_at >= datetime('now', ?)
        GROUP BY c.id
        ORDER BY ABS(SUM(CASE WHEN je.event_type = 'added' THEN 1 ELSE 0 END)
                    - SUM(CASE WHEN je.event_type = 'removed' THEN 1 ELSE 0 END)) DESC
        LIMIT 20
    """, ("-{} days".format(days),)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_seniority_breakdown(company_type=None):
    # type: (Optional[str]) -> list
    conn = get_connection()
    where = "WHERE jp.is_active = 1 AND jp.seniority IS NOT NULL"
    params = []  # type: list
    if company_type:
        where += " AND c.company_type = ?"
        params.append(company_type)
    rows = conn.execute("""
        SELECT jp.seniority, COUNT(*) AS count
        FROM job_postings jp
        JOIN companies c ON c.id = jp.company_id
        {}
        GROUP BY jp.seniority
        ORDER BY count DESC
    """.format(where), params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_work_model_breakdown(company_type=None):
    # type: (Optional[str]) -> list
    conn = get_connection()
    where = "WHERE jp.is_active = 1 AND jp.work_model IS NOT NULL"
    params = []  # type: list
    if company_type:
        where += " AND c.company_type = ?"
        params.append(company_type)
    rows = conn.execute("""
        SELECT jp.work_model, COUNT(*) AS count
        FROM job_postings jp
        JOIN companies c ON c.id = jp.company_id
        {}
        GROUP BY jp.work_model
        ORDER BY count DESC
    """.format(where), params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_skill_counts(company_type=None, limit=30):
    # type: (Optional[str], int) -> list
    conn = get_connection()
    where = "WHERE jp.is_active = 1"
    params = []  # type: list
    if company_type:
        where += " AND c.company_type = ?"
        params.append(company_type)
    params.append(limit)
    rows = conn.execute("""
        SELECT js.skill, COUNT(*) AS count
        FROM job_skills js
        JOIN job_postings jp ON jp.id = js.job_id
        JOIN companies c ON c.id = jp.company_id
        {}
        GROUP BY js.skill
        ORDER BY count DESC
        LIMIT ?
    """.format(where), params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_sector_delta():
    # type: () -> list
    """Net change by sector from the latest batch run."""
    conn = get_connection()
    last_batch = conn.execute(
        "SELECT batch_id FROM scrape_runs WHERE batch_id IS NOT NULL ORDER BY run_at DESC LIMIT 1"
    ).fetchone()
    if not last_batch:
        conn.close()
        return []
    rows = conn.execute("""
        SELECT c.sector,
               SUM(sr.jobs_added) AS added,
               SUM(sr.jobs_removed) AS removed,
               SUM(sr.jobs_added) - SUM(sr.jobs_removed) AS net
        FROM scrape_runs sr
        JOIN companies c ON c.id = sr.company_id
        WHERE sr.batch_id = ? AND sr.status = 'success'
        GROUP BY c.sector
        ORDER BY net DESC
    """, (last_batch[0],)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_dept_sector_cross(top_sectors=8, top_depts=6):
    # type: (int, int) -> list
    """Department × Sector cross-tab for startups (active jobs only)."""
    conn = get_connection()
    # Get top sectors by total active jobs
    top_sec = [r[0] for r in conn.execute("""
        SELECT c.sector, COUNT(*) AS n
        FROM job_postings jp JOIN companies c ON c.id = jp.company_id
        WHERE jp.is_active = 1 AND c.company_type = 'startup' AND c.sector IS NOT NULL
        GROUP BY c.sector ORDER BY n DESC LIMIT ?
    """, (top_sectors,)).fetchall()]
    # Get top departments overall
    top_dep = [r[0] for r in conn.execute("""
        SELECT jp.normalized_department, COUNT(*) AS n
        FROM job_postings jp JOIN companies c ON c.id = jp.company_id
        WHERE jp.is_active = 1 AND c.company_type = 'startup'
          AND jp.normalized_department IS NOT NULL
        GROUP BY jp.normalized_department ORDER BY n DESC LIMIT ?
    """, (top_depts,)).fetchall()]
    if not top_sec or not top_dep:
        conn.close()
        return []
    sec_placeholders = ",".join("?" for _ in top_sec)
    dep_placeholders = ",".join("?" for _ in top_dep)
    rows = conn.execute(f"""
        SELECT c.sector, jp.normalized_department AS department, COUNT(*) AS job_count
        FROM job_postings jp JOIN companies c ON c.id = jp.company_id
        WHERE jp.is_active = 1 AND c.company_type = 'startup'
          AND c.sector IN ({sec_placeholders})
          AND jp.normalized_department IN ({dep_placeholders})
        GROUP BY c.sector, jp.normalized_department
        ORDER BY c.sector, job_count DESC
    """, top_sec + top_dep).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_seniority_sector_cross(top_sectors=10):
    # type: (int) -> list
    """Seniority × Sector cross-tab for startups (active jobs only)."""
    conn = get_connection()
    top_sec = [r[0] for r in conn.execute("""
        SELECT c.sector, COUNT(*) AS n
        FROM job_postings jp JOIN companies c ON c.id = jp.company_id
        WHERE jp.is_active = 1 AND c.company_type = 'startup'
          AND c.sector IS NOT NULL AND jp.seniority IS NOT NULL
        GROUP BY c.sector ORDER BY n DESC LIMIT ?
    """, (top_sectors,)).fetchall()]
    if not top_sec:
        conn.close()
        return []
    placeholders = ",".join("?" for _ in top_sec)
    rows = conn.execute(f"""
        SELECT c.sector, jp.seniority, COUNT(*) AS job_count
        FROM job_postings jp JOIN companies c ON c.id = jp.company_id
        WHERE jp.is_active = 1 AND c.company_type = 'startup'
          AND c.sector IN ({placeholders}) AND jp.seniority IS NOT NULL
        GROUP BY c.sector, jp.seniority
        ORDER BY c.sector, job_count DESC
    """, top_sec).fetchall()
    conn.close()
    return [dict(r) for r in rows]
