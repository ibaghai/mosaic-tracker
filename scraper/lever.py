import aiohttp
from scraper.base import JobPosting

BASE_URL = "https://api.lever.co/v0/postings/{slug}?mode=json"


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
                        description=p.get("descriptionPlain"),
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
