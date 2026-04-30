"""Apollo.io wrapper for the v1 personal job-search assistant.

Phase A: people discovery only. JD-to-HM inference and outreach generation
land in Phase B (analysis/jd_parse.py + analysis/outreach.py).

Cost guards
    Daily and monthly caps on both calls and credits, read from env. The
    wrapper refuses to call Apollo once any cap is hit. All calls (including
    failures) are persisted to the apollo_api_calls table for audit.

Mock mode
    If APOLLO_API_KEY is empty or APOLLO_MOCK=1, the wrapper returns canned
    fake people so the rest of the pipeline can be smoke-tested without
    spending real credits.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Iterable, Optional
from urllib.parse import urlsplit

from db import queries
from db.models import get_connection


SOURCE_NAME = "apollo"
APOLLO_BASE = "https://api.apollo.io/api/v1"
USER_AGENT = "Mozilla/5.0 MosaicTracker/1.0"
HTTP_TIMEOUT = 60


class ApolloCapExceeded(RuntimeError):
    """Raised when a configured Apollo usage cap has been hit."""


class ApolloError(RuntimeError):
    """Raised on HTTP / API errors that aren't cap-related."""


# ── Configuration ─────────────────────────────────────────────────────────────

def _api_key() -> Optional[str]:
    key = os.getenv("APOLLO_API_KEY", "").strip()
    return key or None


def _mock_mode() -> bool:
    if os.getenv("APOLLO_MOCK", "").strip() in {"1", "true", "yes"}:
        return True
    return _api_key() is None


def _caps() -> dict:
    def _int(name: str, default: int) -> int:
        try:
            return int(os.getenv(name, str(default)))
        except ValueError:
            return default
    return {
        "calls_daily": _int("APOLLO_DAILY_CAP_CALLS", 50),
        "calls_monthly": _int("APOLLO_MONTHLY_CAP_CALLS", 500),
        "credits_daily": _int("APOLLO_DAILY_CAP_CREDITS", 200),
        "credits_monthly": _int("APOLLO_MONTHLY_CAP_CREDITS", 2000),
    }


def _check_caps() -> None:
    caps = _caps()
    used = queries.apollo_usage_summary()
    if used["calls_today"] >= caps["calls_daily"]:
        raise ApolloCapExceeded(
            f"Apollo daily call cap reached ({used['calls_today']}/{caps['calls_daily']}). "
            f"Raise APOLLO_DAILY_CAP_CALLS or wait until UTC midnight."
        )
    if used["calls_month"] >= caps["calls_monthly"]:
        raise ApolloCapExceeded(
            f"Apollo monthly call cap reached ({used['calls_month']}/{caps['calls_monthly']})."
        )
    if used["credits_today"] >= caps["credits_daily"]:
        raise ApolloCapExceeded(
            f"Apollo daily credit cap reached ({used['credits_today']}/{caps['credits_daily']})."
        )
    if used["credits_month"] >= caps["credits_monthly"]:
        raise ApolloCapExceeded(
            f"Apollo monthly credit cap reached ({used['credits_month']}/{caps['credits_monthly']})."
        )


def usage_status() -> dict:
    """Return current Apollo usage vs caps. Useful for surfacing in the UI."""
    return {"caps": _caps(), "used": queries.apollo_usage_summary(), "mock_mode": _mock_mode()}


# ── HTTP ──────────────────────────────────────────────────────────────────────

def _post(endpoint: str, body: dict, *, request_summary: Optional[str] = None) -> dict:
    """POST to Apollo. Logs every call (success or failure) for audit + cap tracking."""
    _check_caps()

    api_key = _api_key()
    if not api_key:
        raise ApolloError("APOLLO_API_KEY is not set. Set it or use APOLLO_MOCK=1 for fake data.")

    url = f"{APOLLO_BASE}/{endpoint.lstrip('/')}"
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Cache-Control": "no-cache",
            "User-Agent": USER_AGENT,
            "x-api-key": api_key,
        },
        method="POST",
    )
    status_code: Optional[int] = None
    credits_used: Optional[int] = None
    error_msg: Optional[str] = None
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            status_code = resp.status
            credits_used = _read_credit_header(resp)
            payload = json.loads(resp.read().decode("utf-8"))
        return payload
    except urllib.error.HTTPError as exc:
        status_code = exc.code
        try:
            credits_used = _read_credit_header(exc)
        except Exception:
            credits_used = None
        body_text = exc.read().decode("utf-8", errors="replace")[:500]
        error_msg = f"HTTP {exc.code}: {body_text}"
        raise ApolloError(error_msg) from exc
    except urllib.error.URLError as exc:
        error_msg = f"URLError: {exc.reason}"
        raise ApolloError(error_msg) from exc
    finally:
        queries.log_apollo_call(
            endpoint,
            request_summary=request_summary,
            credits_used=credits_used,
            status_code=status_code,
            error_msg=error_msg,
        )


def _read_credit_header(resp_or_exc) -> Optional[int]:
    headers = getattr(resp_or_exc, "headers", None)
    if not headers:
        return None
    val = headers.get("x-credits-consumed") or headers.get("x-24-hour-usage")
    try:
        return int(val) if val is not None else None
    except (TypeError, ValueError):
        return None


# ── Domain helpers ────────────────────────────────────────────────────────────

def _company_domain(company: dict) -> Optional[str]:
    """Resolve a company to a domain for Apollo's q_organization_domains_list.

    Order of preference:
        1. Stored `website` field on the company row (parsed for hostname).
        2. Best-effort guess from the company name (e.g., "Checkr" → "checkr.com").

    The guess is right ~80% of the time for SaaS / tech companies. When wrong,
    Apollo returns 0 people, which is recoverable — much better than erroring.
    """
    website = (company.get("website") or "").strip()
    if website:
        if "://" not in website:
            website = "https://" + website
        host = urlsplit(website).hostname or ""
        host = host.lower()
        if host.startswith("www."):
            host = host[4:]
        if host:
            return host

    # Fallback: guess from name. Strip non-alphanumeric, lowercase, append .com.
    name = (company.get("name") or "").strip()
    if not name:
        return None
    clean = re.sub(r"[^a-z0-9]", "", name.lower())
    return f"{clean}.com" if clean else None


def _load_company(company_id: int) -> Optional[dict]:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id, name, website, apollo_organization_id FROM companies WHERE id = ?",
            (company_id,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


_COMPANY_SUFFIX_RE = re.compile(
    r"\b(inc|llc|corp|corporation|ltd|limited|gmbh|s\.a|sa|co)\.?$",
    re.IGNORECASE,
)


def _normalize_company_name(name: Optional[str]) -> str:
    """Normalize a company name for fuzzy comparison.

    Lowercase, strip surrounding whitespace, remove common legal suffixes,
    drop non-alphanumerics. Returns "" for missing input. Used to detect
    when Apollo's organization.name disagrees with our tracker's name
    (signals wrong-company match).
    """
    if not name:
        return ""
    s = name.strip().rstrip(",.").strip()
    s = _COMPANY_SUFFIX_RE.sub("", s).strip()
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _names_match(tracker_name: Optional[str], apollo_name: Optional[str]) -> bool:
    """Heuristic: do these two company names refer to the same entity?

    True when one normalized form contains the other (case- and suffix-
    insensitive). Matches "OpenAI" ~ "OpenAI, Inc.", "LatchBio" ~ "Latch Bio",
    but NOT "Latch" vs "DOOR" — the wrong-company case we're guarding against.
    """
    a = _normalize_company_name(tracker_name)
    b = _normalize_company_name(apollo_name)
    if not a or not b:
        return True  # missing data on either side: don't reject defensively
    return a in b or b in a


# ── Apollo response normalization ─────────────────────────────────────────────

def _normalize_person(
    raw: dict,
    *,
    company_id: Optional[int] = None,
    archetype: Optional[str] = None,
) -> dict:
    organization = raw.get("organization") or {}
    departments = raw.get("departments") or []
    return {
        "apollo_id": raw.get("id"),
        "name": raw.get("name") or " ".join(
            x for x in [raw.get("first_name"), raw.get("last_name")] if x
        ).strip(),
        "title": raw.get("title"),
        "company_id": company_id,
        "company_name": organization.get("name"),
        "linkedin_url": raw.get("linkedin_url"),
        "email": raw.get("email"),
        "email_status": raw.get("email_status"),
        "phone": (raw.get("phone_numbers") or [{}])[0].get("raw_number")
            if raw.get("phone_numbers") else None,
        "bio_summary": raw.get("headline"),
        "seniority": raw.get("seniority"),
        "departments_json": json.dumps(departments) if departments else None,
        "tenure_start_date": _parse_tenure_start(raw),
        "archetype": archetype,
        "source": SOURCE_NAME,
        "raw_payload_json": json.dumps(raw)[:10000],
    }


def _parse_tenure_start(raw: dict) -> Optional[str]:
    """Apollo sometimes provides employment_history; pick the current one's start."""
    history = raw.get("employment_history") or []
    for entry in history:
        if entry.get("current"):
            start = entry.get("start_date")
            if start and re.match(r"^\d{4}-\d{2}-\d{2}", start):
                return start[:10]
    return None


# ── Public API ────────────────────────────────────────────────────────────────

def enrich_person(
    person_or_id: dict | int | str,
    *,
    reveal_personal_emails: bool = False,
    persist: bool = True,
) -> dict:
    """Reveal full identity for a person via Apollo's /people/match.

    Accepts: an existing people-row dict, a people.id (int), or an apollo_id (str).
    Costs ~1 Apollo credit per call; +1 if reveal_personal_emails=True.

    Returns the enriched normalized person dict. If `persist=True` and the row
    exists in the people table, the new fields are merged in via upsert_person.
    """
    apollo_id: Optional[str] = None
    existing_row: Optional[dict] = None

    if isinstance(person_or_id, dict):
        existing_row = person_or_id
        apollo_id = person_or_id.get("apollo_id")
        if not apollo_id and person_or_id.get("id"):
            db_row = queries.get_person(int(person_or_id["id"]))
            if db_row:
                existing_row = db_row
                apollo_id = db_row.get("apollo_id")
    elif isinstance(person_or_id, int):
        existing_row = queries.get_person(person_or_id)
        apollo_id = existing_row and existing_row.get("apollo_id")
    elif isinstance(person_or_id, str):
        apollo_id = person_or_id

    if not apollo_id:
        raise ValueError("enrich_person: could not resolve an apollo_id from input")

    if _mock_mode():
        return _mock_enrich(apollo_id, existing_row)

    body = {"id": apollo_id, "reveal_personal_emails": reveal_personal_emails}
    summary = f"enrich apollo_id={apollo_id} reveal_personal={reveal_personal_emails}"
    payload = _post("people/match", body, request_summary=summary)
    raw = payload.get("person") or payload.get("matched_people", [{}])[0] or {}
    if not raw:
        raise ApolloError(f"Apollo returned no match for apollo_id={apollo_id}")

    # Preserve company_id and archetype from the existing row if we have it.
    company_id = (existing_row or {}).get("company_id")
    archetype = (existing_row or {}).get("archetype")
    enriched = _normalize_person(raw, company_id=company_id, archetype=archetype)

    if persist:
        try:
            pid = queries.upsert_person(enriched)
            enriched["id"] = pid
        except Exception as exc:  # noqa: BLE001
            enriched["_persist_error"] = str(exc)

    return enriched


def infer_hiring_manager(
    parsed_jd: dict,
    candidates: list[dict],
) -> list[dict]:
    """Score Apollo candidates against a parsed JD's reports-to-target.

    Returns the candidates list with two new keys per row:
        hm_score: float in [0, 1]
        hm_evidence: list[str] explaining the score components
    Sorted descending by score. The caller decides what to do with confidence —
    typically: top score > 0.7 = high, 0.4-0.7 = medium with ambiguity caveat,
    < 0.4 = low / fall back to recruiter or recent-joiner.

    Hard rule: this function does NOT call the LLM or Apollo. It's pure scoring
    over already-fetched data, so it's cheap to re-run as the user filters.
    """
    target = (parsed_jd or {}).get("reports_to_target") or {}
    target_title = (target.get("title") or "").lower().strip()
    target_team = (target.get("team_or_org") or (parsed_jd or {}).get("team_or_org") or "").lower().strip()
    target_level = (target.get("level") or "").lower().strip() or None
    target_function = (target.get("function") or (parsed_jd or {}).get("function") or "").lower().strip() or None

    # If JD didn't state a reports-to, infer from the ROLE's own level + function
    # (the role's manager is one tier up from the role itself).
    # Marked "inferred" so callers can lower confidence accordingly.
    inferred = False
    role_level = (parsed_jd or {}).get("level")
    role_function = (parsed_jd or {}).get("function")
    if not target_title and role_level and role_function:
        inferred = True
        target_title, target_level, target_function = _infer_reports_to_from_role(
            role_level, role_function
        )

    out: list[dict] = []
    for person in candidates:
        score, evidence = _score_hm_candidate(
            person,
            target_title=target_title,
            target_team=target_team,
            target_level=target_level,
            target_function=target_function,
        )
        if inferred:
            evidence.insert(0, "Reports-to inferred from role level (JD didn't state it)")
            score *= 0.7  # confidence ceiling for inferred matches
        row = dict(person)
        row["hm_score"] = round(score, 3)
        row["hm_evidence"] = evidence
        out.append(row)

    out.sort(key=lambda r: r["hm_score"], reverse=True)
    return out


def _score_hm_candidate(
    person: dict,
    *,
    target_title: str,
    target_team: str,
    target_level: Optional[str],
    target_function: Optional[str],
) -> tuple[float, list[str]]:
    """Hand-tuned weighted score in [0, 1] with per-component evidence."""
    title_lower = (person.get("title") or "").lower()
    bio_lower = (person.get("bio_summary") or "").lower()
    seniority = (person.get("seniority") or "").lower()
    departments_raw = person.get("departments_json") or ""

    score = 0.0
    evidence: list[str] = []

    # --- title match (heaviest weight) -----------------------------------
    if target_title and title_lower:
        title_match = _title_overlap(target_title, title_lower) * \
            _cross_function_penalty(title_lower, target_function)
        if title_match >= 0.7:
            score += 0.45
            evidence.append(f"Title matches reports-to target ({person.get('title')!r} ≈ {target_title!r})")
        elif title_match >= 0.45:
            score += 0.30
            evidence.append(f"Title partially matches reports-to target ({person.get('title')!r})")
        elif title_match >= 0.25:
            score += 0.10
            evidence.append("Title weakly matches reports-to target")

    # --- level alignment --------------------------------------------------
    if target_level:
        if seniority == target_level:
            score += 0.20
            evidence.append(f"Seniority matches ({seniority})")
        elif _level_within_one(seniority, target_level):
            score += 0.10
            evidence.append(f"Seniority within one level ({seniority} vs target {target_level})")

    # --- function / department match -------------------------------------
    if target_function:
        if target_function in title_lower or target_function in bio_lower or target_function in departments_raw.lower():
            score += 0.15
            evidence.append(f"Function ({target_function}) matches title/bio/department")

    # --- team mention -----------------------------------------------------
    if target_team:
        if target_team in title_lower or target_team in bio_lower:
            score += 0.15
            evidence.append(f"Team match: '{target_team}' appears in profile")

    # --- tenure plausibility ----------------------------------------------
    tenure = person.get("tenure_start_date")
    if tenure:
        # Anyone in the seat for <3mo is unlikely to be the HM for an open req
        from datetime import datetime, timezone
        try:
            start = datetime.fromisoformat(str(tenure))
            months = (datetime.now(timezone.utc).replace(tzinfo=None) - start).days / 30
            if months < 3:
                score *= 0.6
                evidence.append(f"Penalty: only {months:.0f}mo tenure (might not be the HM yet)")
        except (ValueError, TypeError):
            pass

    return min(score, 1.0), evidence


def _title_overlap(target: str, title: str) -> float:
    """Symmetric Jaccard score between two normalized titles.

    Penalizes both missing target tokens (low recall) AND extra unrelated
    tokens in the candidate (low precision) — so 'VP, Deputy General Counsel,
    Privacy, Product, IP & Compliance' won't fully match 'VP Product'.
    """
    target_tokens = _normalize_title_tokens(target)
    title_tokens = _normalize_title_tokens(title)
    if not target_tokens or not title_tokens:
        return 0.0
    overlap = target_tokens & title_tokens
    union = target_tokens | title_tokens
    jaccard = len(overlap) / len(union)
    # Boost if every target token is present (strong indicator the role is here)
    recall = len(overlap) / len(target_tokens)
    if recall == 1.0:
        return min(1.0, jaccard + 0.25)
    return jaccard


def _normalize_title_tokens(text: str) -> set[str]:
    """Lowercase, expand common abbreviations, drop stopwords, return token set."""
    if not text:
        return set()
    s = text.lower()
    # Expand abbreviations BEFORE tokenizing
    for short, long in _TITLE_NORMALIZATIONS:
        s = re.sub(rf"\b{short}\b", long, s)
    tokens = set(re.findall(r"[a-z]+", s))
    return tokens - _STOPWORDS - _GENERIC_TITLE_NOISE


_STOPWORDS = {"of", "the", "and", "for", "to", "a", "an", "at", "in", "on", "with"}

# Words that appear in many titles but don't disambiguate function. Drop them
# so a 'VP, Deputy General Counsel' doesn't match 'VP Product' through 'vp'.
_GENERIC_TITLE_NOISE = {"vice", "president", "vp", "director", "head", "manager",
                       "senior", "sr", "junior", "jr", "lead", "principal",
                       "staff", "deputy", "global", "regional", "associate"}

_TITLE_NORMALIZATIONS = [
    (r"v\.?p\.?", "vice president"),
    (r"sr\.?", "senior"),
    (r"jr\.?", "junior"),
    (r"mgr\.?", "manager"),
    (r"eng\.?", "engineering"),
    (r"prod\.?", "product"),
    (r"hr\b", "human resources"),
]


# Coarse function keywords for cross-function-penalty detection.
_FUNCTION_KEYWORDS = {
    "product": {"product"},
    "engineering": {"engineering", "engineer", "platform", "infrastructure", "software"},
    "design": {"design", "ux", "ui"},
    "marketing": {"marketing"},
    "sales": {"sales", "revenue", "account"},
    "data": {"data", "analytics"},
    "legal": {"legal", "counsel", "compliance"},
    "human_resources": {"recruiting", "recruiter", "talent", "people"},
    "operations": {"operations"},
    "finance": {"finance", "accounting"},
}


def _cross_function_penalty(title_lower: str, target_function: Optional[str]) -> float:
    """Penalize when the title mixes target-function with a competing function.

    Example: target_function='product', title='VP Product Marketing' → 0.6
    (penalized because 'marketing' is a competing function keyword).

    Returns a multiplier in [0.6, 1.0]. Conservative — only penalizes when both
    sides have evidence; never zeros out a match.
    """
    if not target_function or target_function not in _FUNCTION_KEYWORDS:
        return 1.0
    target_kws = _FUNCTION_KEYWORDS[target_function]
    has_target = any(kw in title_lower for kw in target_kws)
    if not has_target:
        return 1.0
    for fn, kws in _FUNCTION_KEYWORDS.items():
        if fn == target_function:
            continue
        if any(kw in title_lower for kw in kws):
            return 0.6
    return 1.0

_LEVEL_ORDER = ["intern", "junior", "mid", "senior", "staff", "principal",
                "manager", "director", "head", "vp", "c_suite"]


def _level_within_one(a: str, b: str) -> bool:
    if a not in _LEVEL_ORDER or b not in _LEVEL_ORDER:
        return False
    return abs(_LEVEL_ORDER.index(a) - _LEVEL_ORDER.index(b)) <= 1


def _infer_reports_to_from_role(level: Optional[str], function: Optional[str]) -> tuple[str, Optional[str], Optional[str]]:
    """When the JD doesn't say who the role reports to, guess from level + function.

    Conservative: only return high-confidence implications.
    Returns (title_text, level, function).
    """
    if not level or not function:
        return ("", None, None)
    level = level.lower()
    function = function.lower()
    if level in ("intern", "junior", "mid", "senior", "staff"):
        return (f"manager {function}", "manager", function)
    if level == "manager":
        return (f"director {function}", "director", function)
    if level == "director":
        return (f"vp {function}", "vp", function)
    if level == "head":
        return (f"vp {function}", "vp", function)
    if level == "vp":
        return ("c_suite", "c_suite", function)
    return ("", None, None)


def find_and_enrich_top(
    company_id: int,
    *,
    archetype: str,
    titles: Optional[Iterable[str]] = None,
    seniorities: Optional[Iterable[str]] = None,
    departments: Optional[Iterable[str]] = None,
    search_limit: int = 25,
    enrich_top: int = 3,
    reveal_personal_emails: bool = False,
) -> list[dict]:
    """Search + enrich the top N hits in one call.

    Use when you want a fully-revealed candidate list ready to surface in the UI
    (the auto-enrich-top-N strategy). Total credit cost ≈ 1 search + N enrichments.
    """
    candidates = find_people_at_company(
        company_id,
        titles=titles,
        seniorities=seniorities,
        departments=departments,
        archetype=archetype,
        limit=search_limit,
        persist=True,
    )
    enriched: list[dict] = []
    for person in candidates[:enrich_top]:
        try:
            full = enrich_person(person, reveal_personal_emails=reveal_personal_emails)
            enriched.append(full)
        except (ApolloCapExceeded, ApolloError) as exc:
            person["_enrich_error"] = str(exc)
            enriched.append(person)
            break  # don't keep burning credits if caps were hit
    return enriched


def find_people_at_company(
    company_id: int,
    *,
    titles: Optional[Iterable[str]] = None,
    seniorities: Optional[Iterable[str]] = None,
    departments: Optional[Iterable[str]] = None,
    limit: int = 25,
    archetype: Optional[str] = None,
    persist: bool = True,
) -> list[dict]:
    """Search Apollo for current employees at a company, narrowed by title/seniority.

    archetype: tag the persisted records with one of {recruiter, hiring_manager,
        recent_joiner, other}. Caller decides this based on the search filter
        being run (e.g., search by `titles=["recruiter"]` → archetype="recruiter").
    persist: if True, write each result to the people table via upsert_person.
    Returns the normalized people (whether or not they were persisted).
    """
    company = _load_company(company_id)
    if not company:
        raise ValueError(f"company_id {company_id} not found")

    if _mock_mode():
        people = _mock_people(company, titles=titles, archetype=archetype, limit=limit)
    else:
        people = _real_people_search(
            company,
            titles=titles,
            seniorities=seniorities,
            departments=departments,
            limit=limit,
            archetype=archetype,
        )

    if persist:
        for person in people:
            person["company_id"] = company_id
            try:
                pid = queries.upsert_person(person)
                person["id"] = pid
            except Exception as exc:  # noqa: BLE001
                # Don't let one bad row sink the batch; log and continue.
                person["_persist_error"] = str(exc)

    return people


def _real_people_search(
    company: dict,
    *,
    titles: Optional[Iterable[str]],
    seniorities: Optional[Iterable[str]],
    departments: Optional[Iterable[str]],
    limit: int,
    archetype: Optional[str],
) -> list[dict]:
    body: dict = {
        "page": 1,
        "per_page": min(max(limit, 1), 100),
    }

    pinned_org_id = (company.get("apollo_organization_id") or "").strip()
    if pinned_org_id:
        # Strict: search by Apollo's numeric org id. Set once, manually verified.
        body["organization_ids"] = [pinned_org_id]
    else:
        # Fall back to domain. Domains can collide (e.g. "latch.com" → DOOR after merger),
        # so the post-search name-mismatch guard below filters bad results.
        domain = _company_domain(company)
        if not domain:
            raise ApolloError(
                f"Could not resolve a domain for company {company['name']!r} (id={company['id']}). "
                f"Set companies.website or companies.apollo_organization_id manually."
            )
        body["q_organization_domains_list"] = [domain]

    if titles:
        body["person_titles"] = list(titles)
    if seniorities:
        body["person_seniorities"] = list(seniorities)
    if departments:
        body["person_departments"] = list(departments)

    summary = f"company={company['name']!r} titles={list(titles or [])} archetype={archetype!r}"
    payload = _post("mixed_people/api_search", body, request_summary=summary)
    raw_people = payload.get("people") or payload.get("contacts") or []

    normalized = [
        _normalize_person(p, company_id=company["id"], archetype=archetype)
        for p in raw_people[:limit]
    ]

    # Defensive guard: drop people whose Apollo organization name doesn't match
    # the tracker's company name. Catches wrong-company matches when the domain
    # is shared (mergers, parked domains) and we haven't pinned an org_id yet.
    tracker_name = company.get("name")
    return [p for p in normalized if _names_match(tracker_name, p.get("company_name"))]


# ── Mock mode ─────────────────────────────────────────────────────────────────

_MOCK_TEMPLATES = [
    {
        "id_suffix": "vp-eng",
        "first_name": "Sarah", "last_name": "Chen",
        "title": "VP Engineering",
        "headline": "VP Engineering at {company}, leading the platform team.",
        "seniority": "vp",
        "departments": ["engineering"],
        "linkedin_url": "https://www.linkedin.com/in/example-sarah-chen/",
        "default_archetype": "hiring_manager",
        "current_start": "2022-04-01",
    },
    {
        "id_suffix": "tech-recruiter",
        "first_name": "Mike", "last_name": "Rao",
        "title": "Senior Technical Recruiter",
        "headline": "Hiring engineers at {company}.",
        "seniority": "manager",
        "departments": ["human_resources"],
        "linkedin_url": "https://www.linkedin.com/in/example-mike-rao/",
        "default_archetype": "recruiter",
        "current_start": "2021-09-01",
    },
    {
        "id_suffix": "recent-eng",
        "first_name": "Dana", "last_name": "Patel",
        "title": "Senior Software Engineer",
        "headline": "Backend engineer at {company}, recently joined.",
        "seniority": "senior",
        "departments": ["engineering"],
        "linkedin_url": "https://www.linkedin.com/in/example-dana-patel/",
        "default_archetype": "recent_joiner",
        "current_start": "2026-02-15",
    },
    {
        "id_suffix": "director-eng",
        "first_name": "Alex", "last_name": "Kim",
        "title": "Director of Engineering",
        "headline": "Eng leader at {company}, growth team.",
        "seniority": "director",
        "departments": ["engineering"],
        "linkedin_url": "https://www.linkedin.com/in/example-alex-kim/",
        "default_archetype": "hiring_manager",
        "current_start": "2023-06-01",
    },
]


def _mock_people(
    company: dict,
    *,
    titles: Optional[Iterable[str]],
    archetype: Optional[str],
    limit: int,
) -> list[dict]:
    name = company["name"]
    domain = _company_domain(company) or "example.com"
    title_filters = [t.lower() for t in (titles or [])]
    archetype_filter = archetype

    out: list[dict] = []
    for tmpl in _MOCK_TEMPLATES:
        if archetype_filter and tmpl["default_archetype"] != archetype_filter:
            continue
        if title_filters and not any(t in tmpl["title"].lower() for t in title_filters):
            continue
        raw = {
            "id": f"mock-{company['id']}-{tmpl['id_suffix']}",
            "first_name": tmpl["first_name"],
            "last_name": tmpl["last_name"],
            "name": f"{tmpl['first_name']} {tmpl['last_name']}",
            "title": tmpl["title"],
            "headline": tmpl["headline"].format(company=name),
            "linkedin_url": tmpl["linkedin_url"],
            "seniority": tmpl["seniority"],
            "departments": tmpl["departments"],
            "organization": {"name": name, "primary_domain": domain},
            "employment_history": [
                {"current": True, "start_date": tmpl["current_start"], "title": tmpl["title"]}
            ],
            "email": None,
            "email_status": "mock",
        }
        person = _normalize_person(
            raw,
            company_id=company["id"],
            archetype=archetype or tmpl["default_archetype"],
        )
        person["source"] = "apollo_mock"
        out.append(person)
        if len(out) >= limit:
            break
    return out


def _mock_enrich(apollo_id: str, existing_row: Optional[dict]) -> dict:
    """Simulate /people/match: return the same person with full fields populated."""
    base = dict(existing_row or {})
    base["apollo_id"] = apollo_id
    if not base.get("name"):
        base["name"] = "Sarah Chen"
    elif " " not in base["name"]:
        base["name"] = base["name"] + " (Last)"
    company_name = base.get("company_name") or "Acme"
    domain = (company_name.lower().replace(" ", "") + ".com")[:40]
    handle = base["name"].lower().replace(" ", ".").replace("(", "").replace(")", "")
    base["email"] = base.get("email") or f"{handle}@{domain}"
    base["email_status"] = "mock_verified"
    base["linkedin_url"] = base.get("linkedin_url") or f"https://www.linkedin.com/in/mock-{apollo_id}/"
    base["bio_summary"] = base.get("bio_summary") or f"{base.get('title') or 'Leader'} at {company_name}."
    base["source"] = "apollo_mock"
    return base
