import aiohttp
from scraper.base import JobPosting

BASE_URL = "https://api.smartrecruiters.com/v1/companies/{slug}/postings"
PAGE_SIZE = 100


async def parse(company_name: str, ats_identifier: str) -> "list[JobPosting]":
    try:
        all_postings = []  # type: list[JobPosting]
        offset = 0
        async with aiohttp.ClientSession() as session:
            while True:
                url = BASE_URL.format(slug=ats_identifier)
                params = {"limit": PAGE_SIZE, "offset": offset}
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status == 404:
                        raise RuntimeError(f"SmartRecruiters company not found for slug {ats_identifier!r}")
                    if resp.status != 200:
                        raise RuntimeError(f"HTTP {resp.status}")
                    data = await resp.json()

                total = data.get("totalFound", 0)
                content = data.get("content") or []
                for j in content:
                    # Department: prefer customField "Team", fall back to function.label
                    department = None
                    for cf in j.get("customField") or []:
                        if cf.get("fieldLabel") == "Team":
                            department = cf.get("valueLabel")
                            break
                    if not department:
                        func = j.get("function") or {}
                        department = func.get("label")

                    loc = j.get("location") or {}
                    emp = j.get("typeOfEmployment") or {}

                    job_url = f"https://jobs.smartrecruiters.com/{ats_identifier}/{j['id']}" if j.get("id") else None

                    all_postings.append(
                        JobPosting(
                            title=j.get("name", ""),
                            company=company_name,
                            external_id=str(j["id"]) if j.get("id") else None,
                            location=loc.get("fullLocation") or loc.get("city"),
                            department=department,
                            employment_type=emp.get("label"),
                            url=job_url,
                        )
                    )

                offset += len(content)
                if offset >= total or not content:
                    break

        return all_postings
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(f"SmartRecruiters scrape failed for {company_name!r}: {exc}") from exc
