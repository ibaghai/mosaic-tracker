"""SmartRecruiters scraper.

Two-step fetch:
1. List endpoint `/v1/companies/<slug>/postings` paginates IDs+summary
   (no description body).
2. Per-posting detail endpoint `/v1/companies/<slug>/postings/<id>` returns
   the full job ad — sections include `companyDescription`, `jobDescription`,
   `qualifications`, `additionalInformation`. We concatenate them with
   blank lines so the LLM downstream sees a clean paragraph structure.

The list is small (~300 jobs total in our DB) so the N+1 cost is fine.
We bound concurrency at 8 to be polite.
"""

import asyncio
import re
from html import unescape
from typing import Optional

import aiohttp

from scraper.base import JobPosting

LIST_URL = "https://api.smartrecruiters.com/v1/companies/{slug}/postings"
DETAIL_URL = "https://api.smartrecruiters.com/v1/companies/{slug}/postings/{posting_id}"
PAGE_SIZE = 100
DETAIL_CONCURRENCY = 8


def _strip_html(html: Optional[str]) -> str:
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


def _flatten_jobAd(ad: dict) -> str:
    """SR returns a structured `jobAd.sections` map. Concatenate the
    free-text sections in the order users would read them on the public page.
    """
    sections = (ad or {}).get("sections") or {}
    parts: list[str] = []
    # Order roughly matches the public job page.
    for key in ("companyDescription", "jobDescription", "qualifications", "additionalInformation"):
        s = sections.get(key) or {}
        title = (s.get("title") or "").strip()
        text = _strip_html(s.get("text"))
        if not text:
            continue
        if title:
            parts.append(title)
        parts.append(text)
    return "\n\n".join(parts).strip()


async def _fetch_detail(
    session: aiohttp.ClientSession,
    slug: str,
    posting_id: str,
    sem: asyncio.Semaphore,
) -> Optional[dict]:
    async with sem:
        try:
            async with session.get(
                DETAIL_URL.format(slug=slug, posting_id=posting_id),
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status != 200:
                    return None
                return await resp.json()
        except Exception:
            return None


async def parse(company_name: str, ats_identifier: str) -> "list[JobPosting]":
    """Fetch every active posting, then enrich each with its full body."""
    try:
        async with aiohttp.ClientSession() as session:
            # 1. Paginate the list endpoint.
            summaries: list[dict] = []
            offset = 0
            while True:
                async with session.get(
                    LIST_URL.format(slug=ats_identifier),
                    params={"limit": PAGE_SIZE, "offset": offset},
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    if resp.status == 404:
                        raise RuntimeError(
                            f"SmartRecruiters company not found for slug {ats_identifier!r}"
                        )
                    if resp.status != 200:
                        raise RuntimeError(f"HTTP {resp.status}")
                    data = await resp.json()
                total = data.get("totalFound", 0)
                content = data.get("content") or []
                summaries.extend(content)
                offset += len(content)
                if offset >= total or not content:
                    break

            # 2. Enrich each in parallel (bounded).
            sem = asyncio.Semaphore(DETAIL_CONCURRENCY)
            details = await asyncio.gather(
                *(
                    _fetch_detail(session, ats_identifier, str(j["id"]), sem)
                    for j in summaries
                    if j.get("id")
                )
            )

        # Stitch together.
        out: list[JobPosting] = []
        for summary, detail in zip(summaries, details):
            if not summary.get("id"):
                continue
            # Department: prefer customField "Team", fall back to function.label
            department = None
            for cf in summary.get("customField") or []:
                if cf.get("fieldLabel") == "Team":
                    department = cf.get("valueLabel")
                    break
            if not department:
                func = summary.get("function") or {}
                department = func.get("label")

            loc = summary.get("location") or {}
            emp = summary.get("typeOfEmployment") or {}
            description = _flatten_jobAd((detail or {}).get("jobAd")) or None
            job_url = (
                f"https://jobs.smartrecruiters.com/{ats_identifier}/{summary['id']}"
                if summary.get("id")
                else None
            )

            out.append(
                JobPosting(
                    title=summary.get("name", ""),
                    company=company_name,
                    external_id=str(summary["id"]),
                    description=description,
                    location=loc.get("fullLocation") or loc.get("city"),
                    department=department,
                    employment_type=emp.get("label"),
                    url=job_url,
                )
            )
        return out
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(f"SmartRecruiters scrape failed for {company_name!r}: {exc}") from exc
