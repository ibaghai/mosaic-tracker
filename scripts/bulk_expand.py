#!/usr/bin/env python3
"""
Bulk ATS probe and config generator.

Usage:
    python3 scripts/bulk_expand.py --candidates scripts/candidates.txt
    python3 scripts/bulk_expand.py --candidates scripts/candidates.txt --output portals.generated.yml
"""

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path

import aiohttp
import yaml
from playwright.async_api import async_playwright

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


async def probe_greenhouse(session: aiohttp.ClientSession, slug: str):
    url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
    except Exception:
        return None
    jobs = data.get("jobs") or []
    if not jobs:
        return None
    return {
        "ats_type": "greenhouse",
        "ats_identifier": slug,
        "careers_url": f"https://job-boards.greenhouse.io/{slug}",
        "confidence": 0.95,
        "jobs_found": len(jobs),
    }


async def probe_lever(session: aiohttp.ClientSession, slug: str):
    url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10), headers={"User-Agent": "Mozilla/5.0"}) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
    except Exception:
        return None
    if not isinstance(data, list) or not data:
        return None
    return {
        "ats_type": "lever",
        "ats_identifier": slug,
        "careers_url": f"https://jobs.lever.co/{slug}",
        "confidence": 0.9,
        "jobs_found": len(data),
    }


async def probe_ashby(session: aiohttp.ClientSession, slug: str):
    payload = {
        "operationName": "ApiJobBoardWithTeams",
        "variables": {"organizationHostedJobsPageName": slug},
        "query": """
            query ApiJobBoardWithTeams($organizationHostedJobsPageName: String!) {
              jobBoard: jobBoardWithTeams(organizationHostedJobsPageName: $organizationHostedJobsPageName) {
                jobPostings { id }
              }
            }
        """,
    }
    try:
        async with session.post(
            "https://jobs.ashbyhq.com/api/non-user-graphql",
            json=payload,
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
    except Exception:
        return None
    postings = ((data.get("data") or {}).get("jobBoard") or {}).get("jobPostings") or []
    if not postings:
        return None
    return {
        "ats_type": "ashby",
        "ats_identifier": slug,
        "careers_url": f"https://jobs.ashbyhq.com/{slug}",
        "confidence": 0.9,
        "jobs_found": len(postings),
    }


async def probe_workable(page, slug: str):
    url = f"https://apply.workable.com/{slug}/"
    try:
        response = await page.goto(url, wait_until="networkidle", timeout=25000)
        if response is None or response.status != 200:
            return None
        body_text = (await page.locator("body").inner_text()).lower()
        if "page not found" in body_text:
            return None
        cards = page.locator('li[data-ui="job"]')
        count = await cards.count()
        if count == 0:
            return None
        return {
            "ats_type": "workable",
            "ats_identifier": slug,
            "careers_url": url,
            "confidence": 0.85,
            "jobs_found": count,
        }
    except Exception:
        return None


async def probe_workday(page, slug: str):
    variants = [slug, slug.capitalize(), slug.upper()]
    candidates = [
        url
        for variant in variants
        for url in [
            f"https://{slug}.wd5.myworkdayjobs.com/{variant}",
            f"https://{slug}.wd5.myworkdayjobs.com/en-US/{variant}",
            f"https://{slug}.wd1.myworkdayjobs.com/{variant}",
            f"https://{slug}.wd5.myworkdayjobs.com/{variant}/jobs",
        ]
    ]
    for url in candidates:
        try:
            response = await page.goto(url, wait_until="domcontentloaded", timeout=20000)
            if response is None or response.status != 200:
                continue
            await page.wait_for_timeout(1500)
            body = await page.locator("body").inner_text()
            if "search for jobs page is loaded" not in body.lower():
                continue
            count = await page.locator("li.css-1q2dra3").count()
            if count == 0:
                continue
            return {
                "ats_type": "workday",
                "ats_identifier": url,
                "careers_url": url,
                "confidence": 0.75,
                "jobs_found": count,
            }
        except Exception:
            continue
    return None


async def probe_company(session: aiohttp.ClientSession, page, name: str, existing_names: set[str], existing_ats: set[tuple[str, str]]):
    if name.lower() in existing_names:
        return None
    slugs = slugify(name)
    for slug in slugs[:6]:
        if ("greenhouse", slug) not in existing_ats:
            hit = await probe_greenhouse(session, slug)
            if hit:
                return {"name": name, **hit}
    for slug in slugs[:4]:
        if ("lever", slug) not in existing_ats:
            hit = await probe_lever(session, slug)
            if hit:
                return {"name": name, **hit}
    for slug in slugs[:2]:
        if ("ashby", slug) not in existing_ats:
            hit = await probe_ashby(session, slug)
            if hit:
                return {"name": name, **hit}
    for slug in slugs[:2]:
        if ("workable", slug) not in existing_ats:
            hit = await probe_workable(page, slug)
            if hit:
                return {"name": name, **hit}
    for slug in slugs[:1]:
        hit = await probe_workday(page, slug)
        if hit and ("workday", hit["ats_identifier"]) not in existing_ats:
            return {"name": name, **hit}
    return None


def load_existing_targets() -> tuple[set[str], set[tuple[str, str]]]:
    init_db()
    companies = queries.get_all_companies()
    existing_names = {company["name"].lower() for company in companies}
    existing_ats = {
        (company.get("ats_type"), str(company.get("ats_identifier")))
        for company in companies
        if company.get("ats_type") and company.get("ats_identifier")
    }
    return existing_names, existing_ats


def render_yaml(records: list[dict]) -> str:
    payload = {"tracked_companies": []}
    for record in records:
        payload["tracked_companies"].append({
            "name": record["name"],
            "enabled": True,
            "ats_type": record["ats_type"],
            "ats_identifier": record["ats_identifier"],
            "careers_url": record["careers_url"],
            "source_confidence": record["confidence"],
        })
    return yaml.safe_dump(payload, sort_keys=False, allow_unicode=False)


async def main() -> int:
    parser = argparse.ArgumentParser(description="Bulk ATS probe and YAML config generator")
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("portals.generated.yml"))
    args = parser.parse_args()

    with open(args.candidates) as handle:
        candidates = [line.strip() for line in handle if line.strip()]

    existing_names, existing_ats = load_existing_targets()
    hits = []
    async with aiohttp.ClientSession() as session:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            for idx, name in enumerate(candidates, start=1):
                hit = await probe_company(session, page, name, existing_names, existing_ats)
                if hit:
                    hits.append(hit)
                    existing_names.add(name.lower())
                    existing_ats.add((hit["ats_type"], str(hit["ats_identifier"])))
                if idx % 25 == 0 or idx == len(candidates):
                    print(f"progress {idx}/{len(candidates)} -> {len(hits)} hits", file=sys.stderr)
            await browser.close()

    hits.sort(key=lambda row: (-row["jobs_found"], row["name"].lower()))
    args.output.write_text(render_yaml(hits))
    print(json.dumps(hits, indent=2))
    print(f"\nWrote {len(hits)} companies to {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
