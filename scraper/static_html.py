import re
import aiohttp
from scraper.base import JobPosting

CHARLIEHR_PATTERN = re.compile(
    r'href="(https://jobs\.recruit\.charliehr\.com/[^"]+)"[^>]*>([^<]+)<'
)


async def parse(company_name: str, url: str) -> "list[JobPosting]":
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"HTTP {resp.status}")
                html = await resp.text()

        matches = CHARLIEHR_PATTERN.findall(html)
        return [
            JobPosting(
                title=title.replace("-", "").replace(">>", "").strip(),
                company=company_name,
                url=job_url,
            )
            for job_url, title in matches
        ]
    except Exception as exc:
        raise RuntimeError(f"Static HTML scrape failed for {company_name!r}: {exc}") from exc
