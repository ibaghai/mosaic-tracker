from typing import Optional

from playwright.async_api import async_playwright

from scraper.base import JobPosting


async def parse(company_name: str, ats_identifier: str) -> "list[JobPosting]":
    """Fetch jobs from a Workable-hosted careers page.

    `ats_identifier` can be either the Workable slug (e.g. "doist")
    or the full careers URL (e.g. "https://apply.workable.com/doist/").
    """
    if ats_identifier.startswith("http://") or ats_identifier.startswith("https://"):
        url = ats_identifier
    else:
        url = f"https://apply.workable.com/{ats_identifier.strip('/')}/"

    browser = None
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(1500)

            cards = page.locator('li[data-ui="job"]')
            count = await cards.count()
            if count == 0:
                return []

            jobs = []
            for idx in range(count):
                card = cards.nth(idx)
                href = await card.locator('a[href*="/j/"]').first.get_attribute("href")
                if not href:
                    continue
                title = (await card.locator('[data-ui="job-title"]').first.inner_text()).strip()
                workplace = await _safe_inner_text(card, '[data-ui="job-workplace"]')
                location = await _safe_inner_text(card, '[data-ui="job-location"]')
                full_location = ", ".join([value for value in [workplace, location] if value]) or None
                full_url = href if href.startswith("http") else f"https://apply.workable.com{href}"
                external_id = href.rstrip("/").split("/")[-1]
                jobs.append(
                    JobPosting(
                        title=title,
                        company=company_name,
                        external_id=external_id or None,
                        location=full_location,
                        url=full_url,
                    )
                )
            return jobs
    except Exception as exc:
        raise RuntimeError(f"Workable scrape failed for {company_name!r}: {exc}") from exc
    finally:
        if browser:
            await browser.close()


async def _safe_inner_text(card, selector: str) -> Optional[str]:
    locator = card.locator(selector)
    if await locator.count() == 0:
        return None
    value = (await locator.first.inner_text()).strip()
    return value or None
