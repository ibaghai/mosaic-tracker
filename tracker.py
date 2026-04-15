#!/usr/bin/env python3
"""
Startup Job Tracker — main orchestrator.
Run with: python tracker.py
"""

import asyncio
import json
import os
import sys
import uuid
from pathlib import Path

from db.models import init_db
from db import queries
import scraper.ashby as ashby_scraper
import scraper.greenhouse as greenhouse_scraper
import scraper.lever as lever_scraper
import scraper.smartrecruiters as smartrecruiters_scraper
import scraper.teamtailor as teamtailor_scraper
import scraper.workable as workable_scraper
import scraper.workday as workday_scraper
import scraper.playwright_scraper as playwright_scraper
import scraper.static_html as static_html_scraper

try:
    import yaml
except ImportError:  # pragma: no cover - optional until dependency is installed
    yaml = None

COMPANIES_FILE = Path(__file__).parent / "companies.json"
PORTALS_FILE = Path(__file__).parent / "portals.yml"
BATCH_ID = str(uuid.uuid4())[:8]
SCRAPE_CONCURRENCY = int(os.getenv("SCRAPE_CONCURRENCY", "25"))
COMPANY_SOURCE = os.getenv("TRACKER_COMPANY_SOURCE", "merged").strip().lower()


def _normalize_company(row: dict) -> dict:
    return {
        "name": row["name"],
        "website": row.get("website"),
        "careers_url": row.get("careers_url"),
        "ats_type": row["ats_type"],
        "ats_identifier": row.get("ats_identifier") or row.get("careers_url"),
        "sector": row.get("sector"),
        "funding_round": row.get("funding_round"),
        "funding_amount_m": row.get("funding_amount_m"),
        "funding_date": row.get("funding_date"),
        "company_type": row.get("company_type", "startup"),
        "selectors": row.get("selectors"),
        "source_type": row.get("source_type"),
        "source_confidence": row.get("source_confidence"),
        "verification_status": row.get("verification_status"),
        "last_verified_at": row.get("last_verified_at"),
    }


def _load_seed_companies() -> tuple[list[dict], set[str]]:
    """Load configured companies from portals.yml or companies.json."""
    disabled_names = set()
    if PORTALS_FILE.exists():
        if yaml is None:
            raise RuntimeError("PyYAML is required to load portals.yml")
        with open(PORTALS_FILE) as f:
            data = yaml.safe_load(f) or {}
        tracked = data.get("tracked_companies") or []
        companies = []
        for row in tracked:
            if not row.get("enabled", True):
                if row.get("name"):
                    disabled_names.add(str(row["name"]).strip().lower())
                continue
            companies.append(_normalize_company(row))
        return companies, disabled_names
    if not COMPANIES_FILE.exists():
        return [], disabled_names
    with open(COMPANIES_FILE) as f:
        rows = json.load(f)
    return [_normalize_company(row) for row in rows], disabled_names


def _load_db_companies(*, excluded_names: set[str]) -> list[dict]:
    """Load all tracked companies currently in the DB."""
    from db.models import get_connection

    conn = get_connection()
    rows = conn.execute(
        """
        SELECT c.*
        FROM companies c
        WHERE NOT EXISTS (
            SELECT 1
            FROM company_tags ct
            WHERE ct.company_id = c.id
              AND ct.tag IN ('disabled', 'disabled_autoprune')
        )
        ORDER BY c.name
        """
    ).fetchall()
    conn.close()

    companies = []
    for row in rows:
        normalized = _normalize_company(dict(row))
        if normalized["name"].strip().lower() in excluded_names:
            continue
        companies.append(normalized)
    return companies


def _load_tag_disabled_names() -> set[str]:
    from db.models import get_connection

    conn = get_connection()
    rows = conn.execute(
        """
        SELECT LOWER(TRIM(c.name)) AS normalized_name
        FROM companies c
        JOIN company_tags ct ON ct.company_id = c.id
        WHERE ct.tag IN ('disabled', 'disabled_autoprune')
        """
    ).fetchall()
    conn.close()
    return {row["normalized_name"] for row in rows if row["normalized_name"]}


def _merge_companies(seed_companies: list[dict], db_companies: list[dict]) -> list[dict]:
    """
    Merge DB and config companies by name.
    DB is baseline; config overlays non-null values (e.g. selectors, latest metadata).
    """
    merged: dict[str, dict] = {c["name"]: dict(c) for c in db_companies}
    for c in seed_companies:
        existing = merged.get(c["name"], {})
        combined = dict(existing)
        for key, value in c.items():
            if value is not None:
                combined[key] = value
        merged[c["name"]] = combined
    return sorted(merged.values(), key=lambda c: c["name"].lower())


def load_companies() -> list:
    seed_companies, disabled_names = _load_seed_companies()
    excluded_names = set(disabled_names)
    excluded_names.update(_load_tag_disabled_names())

    seed_companies = [
        c for c in seed_companies
        if c["name"].strip().lower() not in excluded_names
    ]

    if COMPANY_SOURCE == "config":
        return seed_companies

    db_companies = _load_db_companies(excluded_names=excluded_names)
    if COMPANY_SOURCE == "db":
        return db_companies

    # Default mode: merge configured companies with everything already tracked in DB.
    return _merge_companies(seed_companies, db_companies)


async def scrape_company(company: dict, company_id: int):
    """Scrape one company. Returns (jobs_found, jobs_added, jobs_removed)."""
    name = company["name"]
    ats = company["ats_type"]

    try:
        if ats == "ashby":
            jobs = await ashby_scraper.parse(name, company["ats_identifier"])
        elif ats == "greenhouse":
            jobs = await greenhouse_scraper.parse(name, company["ats_identifier"])
        elif ats == "lever":
            jobs = await lever_scraper.parse(name, company["ats_identifier"])
        elif ats == "smartrecruiters":
            jobs = await smartrecruiters_scraper.parse(name, company["ats_identifier"])
        elif ats == "teamtailor":
            jobs = await teamtailor_scraper.parse(name, company["ats_identifier"])
        elif ats == "workable":
            jobs = await workable_scraper.parse(name, company["ats_identifier"])
        elif ats == "workday":
            jobs = await workday_scraper.parse(name, company["ats_identifier"])
        elif ats == "playwright":
            jobs = await playwright_scraper.parse(
                name, company["ats_identifier"], selectors=company.get("selectors")
            )
        elif ats == "static":
            jobs = await static_html_scraper.parse(name, company["ats_identifier"])
        else:
            raise ValueError(f"Unknown ATS type: {ats!r}")

        job_dicts = [j.to_dict() for j in jobs]

        # Create the run record first, then sync jobs against it
        run_id = queries.log_run(
            company_id, len(jobs), 0, 0,
            status="success", batch_id=BATCH_ID,
        )
        added, removed = queries.sync_jobs(company_id, run_id, job_dicts)

        # Update the run with actual add/remove counts
        from db.models import get_connection
        conn = get_connection()
        with conn:
            conn.execute(
                "UPDATE scrape_runs SET jobs_added = ?, jobs_removed = ? WHERE id = ?",
                (added, removed, run_id),
            )
        conn.close()

        return len(jobs), added, removed

    except Exception as exc:
        queries.log_run(
            company_id, 0, 0, 0,
            status="failed", error_msg=str(exc), batch_id=BATCH_ID,
        )
        return 0, 0, 0


async def scrape_company_limited(semaphore: asyncio.Semaphore, company: dict, company_id: int):
    async with semaphore:
        return await scrape_company(company, company_id)


async def run():
    init_db()
    companies = load_companies()

    # Upsert all companies and collect their DB ids
    company_ids: dict[str, int] = {}
    for c in companies:
        source_type = c.get("source_type") or "config"
        source_confidence = c.get("source_confidence")
        if source_confidence is None and source_type == "config":
            source_confidence = 1.0

        cid = queries.upsert_company({
            "name": c["name"],
            "website": c.get("website"),
            "ats_type": c["ats_type"],
            "ats_identifier": c.get("ats_identifier"),
            "funding_round": c.get("funding_round"),
            "funding_amount_m": c.get("funding_amount_m"),
            "funding_date": c.get("funding_date"),
            "sector": c.get("sector"),
            "company_type": c.get("company_type", "startup"),
            "careers_url": c.get("careers_url"),
            "source_type": source_type,
            "source_confidence": source_confidence,
            "verification_status": c.get("verification_status") or "verified",
            "last_verified_at": c.get("last_verified_at"),
        })
        company_ids[c["name"]] = cid

    print(f"\nTracking {len(companies)} companies...\n")
    print(f"{'Company':<25} {'ATS':<12} {'Jobs':>5} {'New':>5} {'Gone':>5}")
    print("-" * 58)

    semaphore = asyncio.Semaphore(SCRAPE_CONCURRENCY)
    tasks = [
        scrape_company_limited(semaphore, c, company_ids[c["name"]]) for c in companies
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    total_jobs = total_added = total_removed = 0
    for company, result in zip(companies, results):
        if isinstance(result, Exception):
            print(f"  {company['name']:<23} ERROR: {result}")
            continue
        found, added, removed = result
        total_jobs += found
        total_added += added
        total_removed += removed
        new_tag = f"+{added}" if added else ""
        gone_tag = f"-{removed}" if removed else ""
        print(f"  {company['name']:<23} {company['ats_type']:<12} {found:>5} {new_tag:>5} {gone_tag:>5}")

    print("-" * 58)
    print(f"  {'TOTAL':<23} {'':12} {total_jobs:>5} {f'+{total_added}':>5} {f'-{total_removed}':>5}")

    # ── Enrichment pipeline ───────────────────────────────────────────
    from scraper.enrichment import enrich_all
    enriched = enrich_all()
    if enriched:
        print(f"\nEnriched {enriched} jobs (seniority, work model, department)")

    # ── NLP skill extraction ──────────────────────────────────────────
    from analysis.nlp import extract_all_skills
    skills = extract_all_skills()
    if skills:
        print(f"Extracted {skills} skill tags from job descriptions")

    print(f"\nDone. Run 'streamlit run dashboard.py' to view the dashboard.\n")


if __name__ == "__main__":
    asyncio.run(run())
