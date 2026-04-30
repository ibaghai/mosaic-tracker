"""Ashby scraper.

Switched to the public REST `posting-api/job-board/<org>` endpoint, which
returns the full posting list — including `descriptionPlain` and
`descriptionHtml` — in a single call. The previous GraphQL query asked
only for id/title/team and got 0% description coverage in the DB.

Same code path is also used by `analysis/jd_fetch._try_ashby` for the
on-demand /jd-match URL fetch, so this consolidates two ways of talking
to Ashby into one shape.
"""

import re
from html import unescape
from typing import Optional

import aiohttp

from scraper.base import JobPosting

REST_URL = "https://api.ashbyhq.com/posting-api/job-board/{org}"


def _strip_html(html: Optional[str]) -> str:
    """Light HTML→text fallback for `descriptionHtml` when `descriptionPlain`
    isn't returned. Mirrors the helper in `analysis/jd_fetch._strip_html`."""
    if not html:
        return ""
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</p>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</li>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _description(posting: dict) -> Optional[str]:
    plain = (posting.get("descriptionPlain") or "").strip()
    if plain:
        return plain
    html = posting.get("descriptionHtml") or ""
    return _strip_html(html) or None


def _location(posting: dict) -> Optional[str]:
    loc = posting.get("location") or ""
    if isinstance(loc, dict):
        loc = loc.get("name") or ""
    if not loc and posting.get("isRemote"):
        loc = "Remote"
    return str(loc).strip() or None


async def parse(company_name: str, ats_identifier: str) -> "list[JobPosting]":
    url = REST_URL.format(org=ats_identifier)
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                params={"includeCompensation": "true"},
                timeout=aiohttp.ClientTimeout(total=20),
            ) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"HTTP {resp.status}")
                payload = await resp.json()
    except Exception as exc:
        raise RuntimeError(f"Ashby scrape failed for {company_name!r}: {exc}") from exc

    postings = payload.get("jobs") or payload.get("postings") or []
    return [
        JobPosting(
            title=(p.get("title") or "").strip(),
            company=company_name,
            external_id=p.get("id"),
            description=_description(p),
            location=_location(p),
            department=(p.get("team") or p.get("department") or "") or None,
            employment_type=p.get("employmentType"),
            url=p.get("jobUrl") or f"https://jobs.ashbyhq.com/{ats_identifier}/{p.get('id')}",
        )
        for p in postings
        if p.get("id") and p.get("title")
    ]
