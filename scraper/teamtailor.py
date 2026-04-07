import xml.etree.ElementTree as ET
import aiohttp
from scraper.base import JobPosting


async def parse(company_name: str, ats_identifier: str) -> "list[JobPosting]":
    """Fetch jobs from a Teamtailor RSS feed.

    ats_identifier should be the base URL of the Teamtailor career site,
    e.g. "https://jobs.spot.ai".  We append /jobs.rss automatically.
    """
    rss_url = ats_identifier.rstrip("/") + "/jobs.rss"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(rss_url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"HTTP {resp.status} for {rss_url}")
                text = await resp.text()

        root = ET.fromstring(text)
        channel = root.find("channel")
        if channel is None:
            return []

        ns = {"tt": "https://teamtailor.com/locations"}
        postings = []  # type: list[JobPosting]
        for item in channel.findall("item"):
            title_el = item.find("title")
            link_el = item.find("link")
            if title_el is None or not title_el.text:
                continue

            # Teamtailor uses a custom namespace for locations
            loc_els = item.findall("tt:location", ns)
            location = ", ".join(l.text for l in loc_els if l.text) or None

            desc_el = item.find("description")
            postings.append(
                JobPosting(
                    title=title_el.text.strip(),
                    company=company_name,
                    description=desc_el.text.strip() if desc_el is not None and desc_el.text else None,
                    location=location,
                    department=None,  # not available in RSS
                    employment_type=None,
                    url=link_el.text.strip() if link_el is not None and link_el.text else None,
                )
            )
        return postings
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(f"Teamtailor scrape failed for {company_name!r}: {exc}") from exc
