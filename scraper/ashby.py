import aiohttp
from scraper.base import JobPosting

GRAPHQL_URL = "https://jobs.ashbyhq.com/api/non-user-graphql"

QUERY = """
query ApiJobBoardWithTeams($organizationHostedJobsPageName: String!) {
    jobBoard: jobBoardWithTeams(
        organizationHostedJobsPageName: $organizationHostedJobsPageName
    ) {
        teams { id name }
        jobPostings {
            id
            title
            locationName
            teamId
            employmentType
        }
    }
}
"""


async def parse(company_name: str, ats_identifier: str) -> "list[JobPosting]":
    payload = {
        "operationName": "ApiJobBoardWithTeams",
        "variables": {"organizationHostedJobsPageName": ats_identifier},
        "query": QUERY,
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                GRAPHQL_URL, json=payload, timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"HTTP {resp.status}")
                data = await resp.json()
                jb = (data.get("data") or {}).get("jobBoard") or {}
                teams = {t["id"]: t["name"] for t in jb.get("teams", [])}
                jobs = jb.get("jobPostings", []) or []
                return [
                    JobPosting(
                        title=j["title"],
                        company=company_name,
                        external_id=j["id"],
                        location=j.get("locationName"),
                        department=teams.get(j.get("teamId", ""), ""),
                        employment_type=j.get("employmentType"),
                        url=f"https://jobs.ashbyhq.com/{ats_identifier}/{j['id']}",
                    )
                    for j in jobs
                ]
    except Exception as exc:
        raise RuntimeError(f"Ashby scrape failed for {company_name!r}: {exc}") from exc
