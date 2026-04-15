from typing import Optional

from playwright.async_api import async_playwright

from scraper.base import JobPosting


async def parse(company_name: str, ats_identifier: str) -> "list[JobPosting]":
    """Fetch jobs from a Workday-hosted board.

    `ats_identifier` should be the full public Workday jobs URL, e.g.
    `https://workday.wd5.myworkdayjobs.com/Workday`.
    """
    url = ats_identifier.rstrip("/")
    base_prefix = url.split("/en-US/")[0]
    browser = None
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, wait_until="networkidle", timeout=40000)
            await page.wait_for_timeout(2000)

            cards = page.locator("li.css-1q2dra3")
            count = await cards.count()
            if count == 0:
                return []

            jobs = []
            for idx in range(min(count, 20)):
                card = cards.nth(idx)
                link = card.locator("a.css-19uc56f").first
                href = await link.get_attribute("href")
                title = (await link.inner_text()).strip()
                location = await _safe_detail(card, "locations")
                remote_type = await _safe_detail(card, "remote type")
                full_location = ", ".join([value for value in [remote_type, location] if value]) or None
                external_id = await _extract_external_id(card, href)
                full_url = href if (href and href.startswith("http")) else f"{base_prefix}{href}"
                jobs.append(
                    JobPosting(
                        title=title,
                        company=company_name,
                        external_id=external_id,
                        location=full_location,
                        url=full_url,
                    )
                )
            return jobs
    except Exception as exc:
        raise RuntimeError(f"Workday scrape failed for {company_name!r}: {exc}") from exc
    finally:
        if browser:
            await browser.close()


async def _safe_detail(card, label_text: str) -> Optional[str]:
    text = (await card.inner_text()).splitlines()
    text = [line.strip() for line in text if line.strip()]
    for idx, line in enumerate(text):
        if line.lower() == label_text.lower() and idx + 1 < len(text):
            return text[idx + 1]
    return None


async def _extract_external_id(card, href: Optional[str]) -> Optional[str]:
    text = (await card.inner_text()).splitlines()
    text = [line.strip() for line in text if line.strip()]
    for line in reversed(text):
        if line.startswith("JR-"):
            return line
    if href:
        return href.rstrip("/").split("_")[-1]
    return None
