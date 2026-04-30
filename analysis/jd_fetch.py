"""Fetch the text of a single job posting from its public URL.

Used by the /jd-match flow when the user wants to drop a link instead of
copy-pasting the JD body. Three paths, in order of preference:

1. **Greenhouse JSON API** — when the URL matches a Greenhouse board
   (`boards.greenhouse.io/<board>/jobs/<id>` or job-page redirects). Cheapest
   and most reliable: returns title + content + metadata directly.
2. **Lever JSON API** — when the URL matches `jobs.lever.co/<company>/<id>`.
3. **Generic HTML extraction** — strip <script>/<style>, drop tags, decode
   entities. Lossy but works on most ATS pages we don't have a custom
   path for (Ashby, Workable, Workday, custom careers pages).

Returns a dict with: {title, company, description, location, url, source}.
`source` is one of {"greenhouse", "lever", "html"} so callers can surface
which path was used (and warn when it's the lossy one).
"""

from __future__ import annotations

import asyncio
import json
import re
from html import unescape
from html.parser import HTMLParser
from typing import Optional
from urllib.parse import urlparse

import aiohttp


USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 MosaicTracker/1.0"
)
TIMEOUT_SECONDS = 15


# ── Public API ───────────────────────────────────────────────────────────────

async def fetch_jd_from_url(url: str) -> dict:
    """Resolve a JD URL → structured dict. Raises ValueError on bad input,
    aiohttp.ClientError on network failures.
    """
    url = (url or "").strip()
    if not url:
        raise ValueError("url is empty")
    if "://" not in url:
        url = "https://" + url

    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()

    timeout = aiohttp.ClientTimeout(total=TIMEOUT_SECONDS)
    async with aiohttp.ClientSession(
        timeout=timeout, headers={"User-Agent": USER_AGENT}
    ) as session:
        # Try ATS-specific JSON paths first.
        if "greenhouse.io" in host:
            data = await _try_greenhouse(session, url)
            if data:
                return data
        if "lever.co" in host:
            data = await _try_lever(session, url)
            if data:
                return data
        if "ashbyhq.com" in host:
            data = await _try_ashby(session, url)
            if data:
                return data
        # Fallback: fetch the page, strip HTML.
        return await _fetch_html(session, url)


# ── Greenhouse ───────────────────────────────────────────────────────────────

# Matches:
#   boards.greenhouse.io/<board>/jobs/<id>
#   job-boards.greenhouse.io/<board>/jobs/<id>      (newer hosted variant)
#   <co>.greenhouse.io/jobs/<id>                    (custom subdomain)
#   boards.greenhouse.io/embed/job_app?for=<board>&token=<id>
_GREENHOUSE_RE = re.compile(
    r"greenhouse\.io/(?:embed/job_app\?for=([^&/]+)&token=(\d+)|"
    r"([^/]+)/jobs/(\d+))"
)


async def _try_greenhouse(session: aiohttp.ClientSession, url: str) -> Optional[dict]:
    m = _GREENHOUSE_RE.search(url)
    if not m:
        return None
    board, job_id = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
    api_url = f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{job_id}"
    try:
        async with session.get(api_url) as resp:
            if resp.status != 200:
                return None
            payload = await resp.json()
    except (aiohttp.ClientError, asyncio.TimeoutError, json.JSONDecodeError):
        return None
    return {
        "title": payload.get("title", "").strip(),
        "company": (payload.get("company_name") or board or "").strip(),
        "description": _strip_html(payload.get("content") or ""),
        "location": ((payload.get("location") or {}).get("name") or "").strip(),
        "url": payload.get("absolute_url") or url,
        "source": "greenhouse",
    }


# ── Lever ────────────────────────────────────────────────────────────────────

_LEVER_RE = re.compile(r"jobs\.lever\.co/([^/]+)/([0-9a-f-]{8,})")


async def _try_lever(session: aiohttp.ClientSession, url: str) -> Optional[dict]:
    m = _LEVER_RE.search(url)
    if not m:
        return None
    company, posting_id = m.group(1), m.group(2)
    api_url = f"https://api.lever.co/v0/postings/{company}/{posting_id}"
    try:
        async with session.get(api_url) as resp:
            if resp.status != 200:
                return None
            payload = await resp.json()
    except (aiohttp.ClientError, asyncio.TimeoutError, json.JSONDecodeError):
        return None
    description = (payload.get("descriptionPlain") or "").strip()
    if not description:
        # `description` is HTML; convert. `lists` are bullet sections appended
        # after the main description in the Lever UI — fold them in.
        parts = [_strip_html(payload.get("description") or "")]
        for section in payload.get("lists") or []:
            text = section.get("text") or ""
            content = section.get("content") or ""
            if text:
                parts.append(text)
            if content:
                parts.append(_strip_html(content))
        description = "\n\n".join(p for p in parts if p)
    categories = payload.get("categories") or {}
    return {
        "title": payload.get("text", "").strip(),
        "company": company,
        "description": description,
        "location": (categories.get("location") or "").strip(),
        "url": payload.get("hostedUrl") or url,
        "source": "lever",
    }


# ── Ashby ────────────────────────────────────────────────────────────────────

# jobs.ashbyhq.com/<org>/<uuid>  — Ashby's public posting URL pattern.
# The page is a React SPA (HTML fallback returns no useful text), but Ashby
# exposes the full job board as JSON at api.ashbyhq.com/posting-api/job-board/<org>.
_ASHBY_RE = re.compile(
    r"jobs\.ashbyhq\.com/([^/]+)/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})",
    re.IGNORECASE,
)


async def _try_ashby(session: aiohttp.ClientSession, url: str) -> Optional[dict]:
    m = _ASHBY_RE.search(url)
    if not m:
        return None
    org, posting_id = m.group(1), m.group(2).lower()
    api_url = f"https://api.ashbyhq.com/posting-api/job-board/{org}?includeCompensation=true"
    try:
        async with session.get(api_url) as resp:
            if resp.status != 200:
                return None
            payload = await resp.json()
    except (aiohttp.ClientError, asyncio.TimeoutError, json.JSONDecodeError):
        return None
    postings = payload.get("jobs") or payload.get("postings") or []
    match = next((p for p in postings if (p.get("id") or "").lower() == posting_id), None)
    if not match:
        return None
    description = (match.get("descriptionPlain") or "").strip()
    if not description:
        description = _strip_html(match.get("descriptionHtml") or "")
    location_obj = match.get("location") or ""
    if isinstance(location_obj, dict):
        location_obj = location_obj.get("name") or ""
    if match.get("isRemote") and not location_obj:
        location_obj = "Remote"
    return {
        "title": (match.get("title") or "").strip(),
        "company": org,
        "description": description,
        "location": str(location_obj).strip(),
        "url": match.get("jobUrl") or url,
        "source": "ashby",
    }


# ── Generic HTML fallback ────────────────────────────────────────────────────

async def _fetch_html(session: aiohttp.ClientSession, url: str) -> dict:
    try:
        async with session.get(url) as resp:
            resp.raise_for_status()
            html = await resp.text()
    except aiohttp.ClientError as exc:
        raise RuntimeError(f"Failed to fetch {url}: {exc}") from exc

    title = _extract_title(html) or ""
    text = _extract_visible_text(html)
    return {
        "title": title.strip(),
        # We can't reliably extract company from arbitrary HTML; the LLM
        # parser will pick this up from the body via company_name_in_jd.
        "company": "",
        "description": text,
        "location": "",
        "url": url,
        "source": "html",
    }


_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)


def _extract_title(html: str) -> Optional[str]:
    m = _TITLE_RE.search(html)
    if not m:
        return None
    return unescape(m.group(1)).strip()


class _TextExtractor(HTMLParser):
    """Pull only visible text from an HTML document.

    Skips <script>, <style>, <noscript>, <head>; emits a newline after
    block-level tags so the LLM downstream sees a paragraph structure.
    """

    _SKIP_TAGS = {"script", "style", "noscript", "head"}
    _BLOCK_TAGS = {
        "p", "br", "div", "section", "article", "li", "ul", "ol",
        "h1", "h2", "h3", "h4", "h5", "h6", "tr", "td", "th",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs):  # type: ignore[override]
        if tag in self._SKIP_TAGS:
            self._skip_depth += 1
        elif tag in self._BLOCK_TAGS and self.parts and not self.parts[-1].endswith("\n"):
            self.parts.append("\n")

    def handle_endtag(self, tag: str):  # type: ignore[override]
        if tag in self._SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1
        elif tag in self._BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str):  # type: ignore[override]
        if self._skip_depth:
            return
        if data.strip():
            self.parts.append(data)


def _extract_visible_text(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html)
    raw = "".join(parser.parts)
    # Collapse runs of whitespace and blank lines.
    raw = re.sub(r"[ \t]+", " ", raw)
    raw = re.sub(r"\n{3,}", "\n\n", raw)
    return raw.strip()


def _strip_html(html: str) -> str:
    """Lighter-weight tag stripper for ATS payloads that already give us
    well-formed HTML in a single field (Greenhouse `content`, Lever `description`)."""
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
