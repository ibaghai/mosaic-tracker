import re
import aiohttp
from scraper.base import JobPosting

BASE_URL = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"

# Strip leading numeric IDs Greenhouse sometimes prepends to dept names e.g. "1195 Engineering"
_DEPT_PREFIX = re.compile(r"^\d+\s+")


def _clean_dept(name: str) -> str:
    return _DEPT_PREFIX.sub("", name).strip() if name else name


async def parse(company_name: str, ats_identifier: str) -> "list[JobPosting]":
    url = BASE_URL.format(slug=ats_identifier)
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 404:
                    raise RuntimeError(f"Greenhouse board not found for slug {ats_identifier!r}")
                if resp.status != 200:
                    raise RuntimeError(f"HTTP {resp.status}")
                data = await resp.json()
                jobs = data.get("jobs") or []
                return [
                    JobPosting(
                        title=j["title"],
                        company=company_name,
                        external_id=str(j["id"]),
                        description=j.get("content"),
                        location=(j.get("location") or {}).get("name"),
                        department=_clean_dept(
                            ((j.get("departments") or [{}])[0]).get("name", "")
                        ) or None,
                        employment_type=None,  # not exposed in Greenhouse public API
                        url=j.get("absolute_url"),
                    )
                    for j in jobs
                ]
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(f"Greenhouse scrape failed for {company_name!r}: {exc}") from exc
