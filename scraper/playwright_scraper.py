from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
from scraper.base import JobPosting

DEFAULT_SELECTORS = {
    "job_container": '[data-testid="job-posting"], .job-listing, .position',
    "title": "h3, .job-title, .position-title",
    "location": '[data-testid="location"], .location, .job-location',
    "department": '[data-testid="department"], .department, .team',
    "link": "a",
}


async def parse(company_name: str, url: str, selectors: dict = None) -> "list[JobPosting]":
    sel = {**DEFAULT_SELECTORS, **(selectors or {})}
    browser = None
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, wait_until="networkidle", timeout=30000)

            try:
                await page.wait_for_selector(sel["job_container"], timeout=10000)
            except PlaywrightTimeout:
                raise RuntimeError(f"No job container found at {url}")

            jobs_data = await page.evaluate(f"""() => {{
                const containers = document.querySelectorAll('{sel["job_container"]}');
                return Array.from(containers).map(c => ({{
                    title:      c.querySelector('{sel["title"]}')?.textContent?.trim() || '',
                    location:   c.querySelector('{sel["location"]}')?.textContent?.trim() || '',
                    department: c.querySelector('{sel["department"]}')?.textContent?.trim() || '',
                    url:        c.querySelector('{sel["link"]}')?.href || '',
                }})).filter(j => j.title);
            }}""")

            return [
                JobPosting(
                    title=j["title"],
                    company=company_name,
                    location=j.get("location") or None,
                    department=j.get("department") or None,
                    url=j.get("url") or None,
                )
                for j in jobs_data
            ]
    except Exception as exc:
        raise RuntimeError(f"Playwright scrape failed for {company_name!r}: {exc}") from exc
    finally:
        if browser:
            await browser.close()
