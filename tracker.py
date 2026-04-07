#!/usr/bin/env python3
"""
Startup Job Tracker — main orchestrator.
Run with: python tracker.py
"""

import asyncio
import json
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
import scraper.playwright_scraper as playwright_scraper
import scraper.static_html as static_html_scraper

COMPANIES_FILE = Path(__file__).parent / "companies.json"
BATCH_ID = str(uuid.uuid4())[:8]


def load_companies() -> list:
    with open(COMPANIES_FILE) as f:
        return json.load(f)


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


async def run():
    init_db()
    companies = load_companies()

    # Upsert all companies and collect their DB ids
    company_ids: dict[str, int] = {}
    for c in companies:
        cid = queries.upsert_company({
            "name": c["name"],
            "website": c.get("website"),
            "ats_type": c["ats_type"],
            "ats_identifier": c.get("ats_identifier"),
            "funding_round": c.get("funding_round"),
            "funding_amount_m": c.get("funding_amount_m"),
            "funding_date": c.get("funding_date"),
            "sector": c.get("sector"),
        })
        company_ids[c["name"]] = cid

    print(f"\nTracking {len(companies)} companies...\n")
    print(f"{'Company':<25} {'ATS':<12} {'Jobs':>5} {'New':>5} {'Gone':>5}")
    print("-" * 58)

    tasks = [
        scrape_company(c, company_ids[c["name"]]) for c in companies
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
