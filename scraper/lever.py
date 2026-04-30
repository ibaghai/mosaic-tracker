"""Lever scraper.

Lever returns the JD body in two places: `descriptionPlain` (free-text
intro) and `lists[]` (structured bullet sections — Responsibilities,
Requirements, Benefits, etc.). For ~4.5% of postings the intro alone is
empty and *all* the body lives in `lists[]`. The previous scraper only
read `descriptionPlain` so those rows landed with NULL description.

This version concatenates the intro plus each list's `text` (heading)
and `content` (HTML body) so the full JD is captured.
"""

import re
from html import unescape
from typing import Optional

import aiohttp

from scraper.base import JobPosting

BASE_URL = "https://api.lever.co/v0/postings/{slug}?mode=json"


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


def _full_description(posting: dict) -> Optional[str]:
    parts: list[str] = []
    intro = (posting.get("descriptionPlain") or "").strip()
    if intro:
        parts.append(intro)
    else:
        # Some postings put the entire body in `description` (HTML).
        html_intro = _strip_html(posting.get("description"))
        if html_intro:
            parts.append(html_intro)
    for section in posting.get("lists") or []:
        title = (section.get("text") or "").strip()
        body = _strip_html(section.get("content"))
        if not body:
            continue
        if title:
            parts.append(title)
        parts.append(body)
    out = "\n\n".join(parts).strip()
    return out or None


async def parse(company_name: str, ats_identifier: str) -> "list[JobPosting]":
    url = BASE_URL.format(slug=ats_identifier)
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=15),
                headers={"User-Agent": "Mozilla/5.0"},
            ) as resp:
                if resp.status == 404:
                    raise RuntimeError(f"Lever board not found for slug {ats_identifier!r}")
                if resp.status != 200:
                    raise RuntimeError(f"HTTP {resp.status}")
                postings = await resp.json()
                if not isinstance(postings, list):
                    return []
                return [
                    JobPosting(
                        title=p.get("text", ""),
                        company=company_name,
                        external_id=p.get("id"),
                        description=_full_description(p),
                        location=(p.get("categories") or {}).get("location"),
                        department=(p.get("categories") or {}).get("team"),
                        employment_type=(p.get("categories") or {}).get("commitment"),
                        url=p.get("hostedUrl"),
                    )
                    for p in postings
                    if p.get("text")
                ]
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(f"Lever scrape failed for {company_name!r}: {exc}") from exc
