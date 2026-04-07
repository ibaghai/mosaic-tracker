#!/usr/bin/env python3
"""
Batch-discover startups across ATS platforms.

Usage:
    python3 scripts/batch_discover.py candidates.txt

Takes a file of company names (one per line) and tests slug variations
against Greenhouse, Lever, Ashby, and Teamtailor APIs.
Outputs verified hits to stdout as JSON.
"""

import asyncio
import aiohttp
import json
import re
import sys
from pathlib import Path


def slugify(name: str) -> "list[str]":
    """Generate slug variations from a company name."""
    name = name.strip()
    if not name:
        return []
    base = re.sub(r"[^a-z0-9\s-]", "", name.lower()).strip()
    slug = re.sub(r"\s+", "-", base)
    nohyphen = slug.replace("-", "")
    variations = [slug]
    if nohyphen != slug:
        variations.append(nohyphen)
    # Common suffixes
    for suffix in ["inc", "hq", "io", "ai", "labs", "app"]:
        if not slug.endswith(suffix):
            variations.append(slug + suffix)
            variations.append(nohyphen + suffix)
    # Strip common suffixes to get shorter slug
    for suffix in ["-inc", "-ai", "-io", "-hq", "-labs"]:
        if slug.endswith(suffix):
            variations.append(slug[: -len(suffix)])
    return list(dict.fromkeys(variations))  # dedupe preserving order


async def test_greenhouse(session, slug):
    url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as r:
            if r.status == 200:
                data = await r.json()
                jobs = data.get("jobs", [])
                if jobs:
                    return ("greenhouse", slug, len(jobs))
    except:
        pass
    return None


async def test_lever(session, slug):
    url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as r:
            if r.status == 200:
                data = await r.json()
                if isinstance(data, list) and data:
                    return ("lever", slug, len(data))
    except:
        pass
    return None


async def test_ashby(session, slug):
    query = """query Q($n: String!) { jobBoard: jobBoardWithTeams(organizationHostedJobsPageName: $n) { jobPostings { id } } }"""
    payload = {
        "operationName": "Q",
        "variables": {"organizationHostedJobsPageName": slug},
        "query": query,
    }
    try:
        async with session.post(
            "https://jobs.ashbyhq.com/api/non-user-graphql",
            json=payload,
            timeout=aiohttp.ClientTimeout(total=10),
        ) as r:
            data = await r.json()
            if "error" in data:
                return None  # rate limited
            board = data.get("data", {}).get("jobBoard")
            if board and board.get("jobPostings"):
                return ("ashby", slug, len(board["jobPostings"]))
    except:
        pass
    return None


async def test_name(session, sem, name, tracked_slugs):
    """Test all slug variations for one company name."""
    slugs = slugify(name)
    # Skip already-tracked slugs
    slugs = [s for s in slugs if s not in tracked_slugs]
    if not slugs:
        return []

    hits = []
    async with sem:
        # Test Greenhouse (fastest, no rate limits)
        gh_tasks = [test_greenhouse(session, s) for s in slugs[:6]]
        gh_results = await asyncio.gather(*gh_tasks)
        for r in gh_results:
            if r:
                hits.append((name, r[0], r[1], r[2]))
                return hits  # found on GH, skip other platforms

        # Test Lever
        lv_tasks = [test_lever(session, s) for s in slugs[:4]]
        lv_results = await asyncio.gather(*lv_tasks)
        for r in lv_results:
            if r:
                hits.append((name, r[0], r[1], r[2]))
                return hits

        # Test Ashby (rate-limited, be conservative)
        for s in slugs[:2]:
            r = await test_ashby(session, s)
            if r:
                hits.append((name, r[0], r[1], r[2]))
                return hits
            await asyncio.sleep(1)

    return hits


async def main(candidates_file: str):
    # Load tracked companies
    companies_path = Path(__file__).parent.parent / "companies.json"
    with open(companies_path) as f:
        tracked = json.load(f)
    tracked_slugs = {c["ats_identifier"].lower() for c in tracked}
    tracked_names = {c["name"].lower() for c in tracked}

    # Load candidate names
    with open(candidates_file) as f:
        names = [line.strip() for line in f if line.strip()]

    # Skip already-tracked names
    names = [n for n in names if n.lower() not in tracked_names]
    print(f"Testing {len(names)} candidates (skipped {len(tracked_names)} already tracked)...", file=sys.stderr)

    sem = asyncio.Semaphore(20)
    all_hits = []

    async with aiohttp.ClientSession() as session:
        # Process in batches
        BATCH = 50
        for i in range(0, len(names), BATCH):
            batch = names[i : i + BATCH]
            tasks = [test_name(session, sem, n, tracked_slugs) for n in batch]
            results = await asyncio.gather(*tasks)
            for hits in results:
                all_hits.extend(hits)
            done = min(i + BATCH, len(names))
            print(f"  Progress: {done}/{len(names)}, {len(all_hits)} hits", file=sys.stderr)
            await asyncio.sleep(0.5)

    # Output results
    all_hits.sort(key=lambda x: -x[3])
    print(json.dumps(
        [{"name": h[0], "ats_type": h[1], "ats_identifier": h[2], "jobs": h[3]} for h in all_hits],
        indent=2,
    ))
    print(f"\nTotal: {len(all_hits)} new companies found", file=sys.stderr)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/batch_discover.py candidates.txt", file=sys.stderr)
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))
