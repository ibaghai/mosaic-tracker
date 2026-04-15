#!/usr/bin/env python3
"""
Hybrid discovery runner.

Stages company and job discoveries without promoting them into canonical tables.

Usage:
    python3 scripts/hybrid_discover.py --candidates scripts/candidates.txt
    python3 scripts/hybrid_discover.py --discoveries-json /path/to/discoveries.json
"""

import argparse
import asyncio
import json
import re
import sys
import uuid
from pathlib import Path

import aiohttp

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db.models import init_db  # noqa: E402
from db import queries  # noqa: E402


def slugify(name: str) -> "list[str]":
    name = name.strip()
    if not name:
        return []
    base = re.sub(r"[^a-z0-9\s-]", "", name.lower()).strip()
    slug = re.sub(r"\s+", "-", base)
    nohyphen = slug.replace("-", "")
    variations = [slug]
    if nohyphen != slug:
        variations.append(nohyphen)
    for suffix in ["inc", "hq", "io", "ai", "labs", "app"]:
        if not slug.endswith(suffix):
            variations.append(slug + suffix)
            variations.append(nohyphen + suffix)
    for suffix in ["-inc", "-ai", "-io", "-hq", "-labs"]:
        if slug.endswith(suffix):
            variations.append(slug[: -len(suffix)])
    return list(dict.fromkeys(variations))


async def fetch_greenhouse_jobs(session: aiohttp.ClientSession, slug: str) -> list[dict]:
    url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"
    async with session.get(url, timeout=aiohttp.ClientTimeout(total=12)) as resp:
        if resp.status != 200:
            return []
        data = await resp.json()
    jobs = []
    for row in data.get("jobs") or []:
        jobs.append({
            "title": row.get("title"),
            "external_id": str(row["id"]) if row.get("id") else None,
            "location": (row.get("location") or {}).get("name"),
            "department": ((row.get("departments") or [{}])[0]).get("name"),
            "employment_type": None,
            "url": row.get("absolute_url"),
            "description": row.get("content"),
        })
    return [job for job in jobs if job.get("title")]


async def fetch_lever_jobs(session: aiohttp.ClientSession, slug: str) -> list[dict]:
    url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
    async with session.get(
        url,
        timeout=aiohttp.ClientTimeout(total=12),
        headers={"User-Agent": "Mozilla/5.0"},
    ) as resp:
        if resp.status != 200:
            return []
        data = await resp.json()
    if not isinstance(data, list):
        return []
    jobs = []
    for row in data:
        categories = row.get("categories") or {}
        jobs.append({
            "title": row.get("text"),
            "external_id": row.get("id"),
            "location": categories.get("location"),
            "department": categories.get("team"),
            "employment_type": categories.get("commitment"),
            "url": row.get("hostedUrl"),
            "description": row.get("descriptionPlain"),
        })
    return [job for job in jobs if job.get("title")]


async def fetch_ashby_jobs(session: aiohttp.ClientSession, slug: str) -> list[dict]:
    payload = {
        "operationName": "ApiJobBoardWithTeams",
        "variables": {"organizationHostedJobsPageName": slug},
        "query": """
            query ApiJobBoardWithTeams($organizationHostedJobsPageName: String!) {
              jobBoard: jobBoardWithTeams(
                organizationHostedJobsPageName: $organizationHostedJobsPageName
              ) {
                teams { id name }
                jobPostings {
                  id
                  title
                  locationName
                  teamId
                  employmentType
                }
              }
            }
        """,
    }
    async with session.post(
        "https://jobs.ashbyhq.com/api/non-user-graphql",
        json=payload,
        timeout=aiohttp.ClientTimeout(total=12),
    ) as resp:
        if resp.status != 200:
            return []
        data = await resp.json()
    board = (data.get("data") or {}).get("jobBoard") or {}
    teams = {team["id"]: team["name"] for team in board.get("teams") or []}
    jobs = []
    for row in board.get("jobPostings") or []:
        jobs.append({
            "title": row.get("title"),
            "external_id": row.get("id"),
            "location": row.get("locationName"),
            "department": teams.get(row.get("teamId")),
            "employment_type": row.get("employmentType"),
            "url": f"https://jobs.ashbyhq.com/{slug}/{row['id']}" if row.get("id") else None,
            "description": None,
        })
    return [job for job in jobs if job.get("title")]


async def discover_company(session: aiohttp.ClientSession, name: str, tracked_slugs: set[str]) -> list[dict]:
    slugs = [slug for slug in slugify(name) if slug not in tracked_slugs]
    if not slugs:
        return []

    for slug in slugs[:6]:
        jobs = await fetch_greenhouse_jobs(session, slug)
        if jobs:
            return [{
                "raw_name": name,
                "ats_type": "greenhouse",
                "ats_identifier": slug,
                "careers_url": f"https://job-boards.greenhouse.io/{slug}",
                "source_type": "ats_probe",
                "source_detail": "greenhouse_api",
                "confidence": 0.95,
                "jobs": jobs,
            }]

    for slug in slugs[:4]:
        jobs = await fetch_lever_jobs(session, slug)
        if jobs:
            return [{
                "raw_name": name,
                "ats_type": "lever",
                "ats_identifier": slug,
                "careers_url": f"https://jobs.lever.co/{slug}",
                "source_type": "ats_probe",
                "source_detail": "lever_api",
                "confidence": 0.9,
                "jobs": jobs,
            }]

    for slug in slugs[:2]:
        jobs = await fetch_ashby_jobs(session, slug)
        if jobs:
            return [{
                "raw_name": name,
                "ats_type": "ashby",
                "ats_identifier": slug,
                "careers_url": f"https://jobs.ashbyhq.com/{slug}",
                "source_type": "ats_probe",
                "source_detail": "ashby_graphql",
                "confidence": 0.9,
                "jobs": jobs,
            }]
        await asyncio.sleep(0.5)

    return []


def infer_liveness(job: dict) -> str:
    if job.get("url"):
        return "active"
    return "unknown"


def stage_discovery_records(records: list[dict]) -> dict:
    companies_staged = 0
    jobs_staged = 0
    duplicate_companies = 0
    duplicate_jobs = 0

    for record in records:
        company_payload = {
            "raw_name": record["raw_name"],
            "website": record.get("website"),
            "careers_url": record.get("careers_url"),
            "ats_type": record.get("ats_type"),
            "ats_identifier": record.get("ats_identifier"),
            "source_type": record.get("source_type", "discovery"),
            "source_detail": record.get("source_detail"),
            "confidence": record.get("confidence", 0.5),
            "evidence_json": json.dumps({
                "ats_type": record.get("ats_type"),
                "ats_identifier": record.get("ats_identifier"),
                "job_count": len(record.get("jobs") or []),
            }),
        }
        match = queries.match_company(company_payload)
        if match:
            duplicate_companies += 1
            company_payload["status"] = "duplicate"
            company_payload["matched_company_id"] = match["id"]
        company_discovery_id = queries.upsert_company_discovery(company_payload)
        companies_staged += 1

        for job in record.get("jobs") or []:
            matched_company_id = match["id"] if match else None
            job_payload = {
                "company_discovery_id": company_discovery_id,
                "matched_company_id": matched_company_id,
                "title": job.get("title"),
                "location": job.get("location"),
                "department": job.get("department"),
                "employment_type": job.get("employment_type"),
                "url": job.get("url"),
                "external_id": job.get("external_id"),
                "description": job.get("description"),
                "source_type": record.get("source_type", "discovery"),
                "source_detail": record.get("source_detail"),
                "confidence": record.get("confidence", 0.5),
                "liveness_status": infer_liveness(job),
            }
            job_match = queries.match_job(matched_company_id, job_payload) if matched_company_id else None
            if job_match:
                duplicate_jobs += 1
                job_payload["status"] = "duplicate"
                job_payload["matched_job_id"] = job_match["id"]
            queries.upsert_job_discovery(job_payload)
            jobs_staged += 1

    return {
        "companies_staged": companies_staged,
        "jobs_staged": jobs_staged,
        "duplicate_companies": duplicate_companies,
        "duplicate_jobs": duplicate_jobs,
    }


def load_discoveries_json(path: Path) -> list[dict]:
    with open(path) as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        raise ValueError("discoveries json must be a list")
    records = []
    for row in data:
        if not isinstance(row, dict):
            continue
        jobs = row.get("jobs")
        if not isinstance(jobs, list):
            jobs = []
        record = {
            "raw_name": row.get("raw_name") or row.get("name"),
            "website": row.get("website"),
            "careers_url": row.get("careers_url"),
            "ats_type": row.get("ats_type"),
            "ats_identifier": row.get("ats_identifier"),
            "source_type": row.get("source_type", "file_import"),
            "source_detail": row.get("source_detail", path.name),
            "confidence": row.get("confidence", 0.7),
            "jobs": jobs,
        }
        if record["raw_name"]:
            records.append(record)
    return records


async def run_live_discovery(candidates_file: Path) -> list[dict]:
    companies_path = ROOT / "companies.json"
    with open(companies_path) as handle:
        tracked = json.load(handle)
    tracked_slugs = {
        str(company.get("ats_identifier", "")).lower()
        for company in tracked
        if company.get("ats_identifier")
    }
    tracked_names = {company["name"].lower() for company in tracked}

    with open(candidates_file) as handle:
        names = [line.strip() for line in handle if line.strip()]
    names = [name for name in names if name.lower() not in tracked_names]

    sem = asyncio.Semaphore(10)
    records = []

    async with aiohttp.ClientSession() as session:
        async def wrapped(name: str) -> list[dict]:
            async with sem:
                return await discover_company(session, name, tracked_slugs)

        tasks = [wrapped(name) for name in names]
        for index, result in enumerate(await asyncio.gather(*tasks), start=1):
            records.extend(result)
            if index % 25 == 0 or index == len(tasks):
                print(f"discovery progress {index}/{len(tasks)} -> {len(records)} hits", file=sys.stderr)
    return records


async def main() -> int:
    parser = argparse.ArgumentParser(description="Stage hybrid company/job discoveries")
    parser.add_argument("--candidates", type=Path, help="candidate company names file")
    parser.add_argument("--discoveries-json", type=Path, help="offline discoveries json file")
    args = parser.parse_args()

    if not args.candidates and not args.discoveries_json:
        parser.error("one of --candidates or --discoveries-json is required")

    init_db()
    batch_id = str(uuid.uuid4())[:8]
    run_id = queries.start_discovery_run("hybrid_discover", batch_id=batch_id)

    try:
        if args.discoveries_json:
            records = load_discoveries_json(args.discoveries_json)
        else:
            records = await run_live_discovery(args.candidates)

        stats = stage_discovery_records(records)
        queries.finish_discovery_run(
            run_id,
            status="success",
            companies_found=stats["companies_staged"],
            jobs_found=stats["jobs_staged"],
        )
        print(json.dumps({
            "batch_id": batch_id,
            "records": len(records),
            **stats,
        }, indent=2))
        return 0
    except Exception as exc:
        queries.finish_discovery_run(run_id, status="failed", error_msg=str(exc))
        print(f"hybrid_discover failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
