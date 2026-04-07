"""
Post-scrape enrichment: seniority, work model, normalized department.
Idempotent — only fills NULL fields.
"""

import re
from db.models import get_connection

# ── Seniority ─────────────────────────────────────────────────────────────────

_SENIORITY_PATTERNS = [
    (re.compile(r'\bIntern\b', re.I), 'intern'),
    (re.compile(r'\bNew Grad\b|\bEntry[- ]Level\b', re.I), 'junior'),
    (re.compile(r'\bJunior\b|\bJr\.?\b', re.I), 'junior'),
    (re.compile(r'\bPrincipal\b', re.I), 'principal'),
    (re.compile(r'\bStaff\b', re.I), 'staff'),
    (re.compile(r'\bSenior\b|\bSr\.?\b', re.I), 'senior'),
    (re.compile(r'\bLead\b', re.I), 'lead'),
    (re.compile(r'\bHead of\b', re.I), 'head'),
    (re.compile(r'\bDirector\b', re.I), 'director'),
    (re.compile(r'\bVP\b|Vice President', re.I), 'vp'),
    (re.compile(r'\bC[A-Z]O\b|\bChief\b', re.I), 'c-level'),
    (re.compile(r'\bManager\b', re.I), 'manager'),
]


def _parse_seniority(title):
    # type: (str) -> str
    for pattern, level in _SENIORITY_PATTERNS:
        if pattern.search(title):
            return level
    return 'mid'


# ── Work Model ────────────────────────────────────────────────────────────────

def _classify_work_model(location, title):
    # type: (str, str) -> str
    text = "{} {}".format(location or '', title).lower()
    if 'remote' in text:
        return 'remote'
    if 'hybrid' in text:
        return 'hybrid'
    return 'onsite'


def _classify_remote_scope(location, title):
    text = "{} {}".format(location or '', title or '').lower()
    if 'anywhere' in text or 'worldwide' in text or 'global' in text:
        return 'global'
    if 'emea' in text:
        return 'emea'
    if 'europe' in text or 'eu only' in text:
        return 'europe'
    if 'canada' in text:
        return 'canada'
    if 'united states' in text or 'u.s.' in text or 'usa' in text or 'us only' in text:
        return 'us'
    return 'unspecified'


# ── Department Normalization ──────────────────────────────────────────────────

_DEPT_RULES = [
    (['engineer', 'software', 'hardware', 'platform', 'infrastructure',
      'r&d', 'developer', 'firmware', 'embedded', 'mobile', 'web',
      'frontend', 'backend', 'full stack', 'fullstack', 'devops', 'sre',
      'reliability'], 'Engineering'),
    (['ai ', 'research', 'data sci', 'machine learn', 'model '], 'AI / Research'),
    (['sales', 'account exec', 'business develop', 'revenue'], 'Sales'),
    (['market', 'growth', 'brand', 'comms', 'communications', 'content'], 'Marketing'),
    (['product'], 'Product'),
    (['design', 'ux', 'creative', 'ui '], 'Design'),
    (['customer', 'support', 'success', 'experience', 'cx '], 'Customer Success'),
    (['people', 'recruit', 'talent', 'hr', 'human resource'], 'People / HR'),
    (['finance', 'accounting', 'controller', 'tax', 'payroll'], 'Finance'),
    (['legal', 'compliance', 'policy', 'regulatory'], 'Legal'),
    (['operation', 'supply', 'logistics', 'professional serv'], 'Operations'),
    (['security', 'trust', 'infosec'], 'Security'),
    (['data', 'analytics', 'business intel', 'bi '], 'Data / Analytics'),
    (['it ', 'information tech'], 'IT'),
]


def _normalize_department(raw_dept):
    # type: (str) -> str
    if not raw_dept:
        return 'Other'
    lower = raw_dept.lower()
    for keywords, label in _DEPT_RULES:
        for kw in keywords:
            if kw in lower:
                # Special case: "product eng" → Engineering, not Product
                if label == 'Product' and 'eng' in lower:
                    return 'Engineering'
                return label
    return 'Other'


_ROLE_FAMILY_RULES = [
    (['machine learning', 'ml ', 'ai ', 'artificial intelligence', 'research scientist', 'llm', 'model'], 'ml_ai'),
    (['data engineer', 'data scientist', 'analytics', 'bi ', 'business intelligence', 'data analyst'], 'data'),
    (['product manager', 'product designer', 'product marketing'], 'product'),
    (['designer', 'ux', 'ui ', 'creative'], 'design'),
    (['account executive', 'sales', 'revenue', 'business development', 'go to market'], 'sales'),
    (['marketing', 'growth', 'demand gen', 'brand', 'content'], 'marketing'),
    (['customer success', 'support', 'solutions engineer', 'implementation', 'customer'], 'customer_success'),
    (['recruit', 'talent', 'people partner', 'human resources', 'hr '], 'people'),
    (['finance', 'accounting', 'controller', 'fp&a'], 'finance'),
    (['legal', 'compliance', 'counsel'], 'legal'),
    (['security', 'trust', 'infosec'], 'security'),
    (['operation', 'logistics', 'supply chain', 'program manager'], 'operations'),
    (['engineer', 'developer', 'sre', 'devops', 'platform', 'frontend', 'backend', 'full stack', 'mobile'], 'software_engineering'),
]


def _infer_role_family(title, department):
    text = "{} {}".format(title or '', department or '').lower()
    for keywords, label in _ROLE_FAMILY_RULES:
        for kw in keywords:
            if kw in text:
                return label
    return 'other'


_STATE_CODES = {
    'ca': 'California', 'ny': 'New York', 'wa': 'Washington', 'ma': 'Massachusetts',
    'tx': 'Texas', 'il': 'Illinois', 'co': 'Colorado', 'or': 'Oregon',
}


def _normalize_location_fields(location):
    raw = (location or '').strip()
    if not raw:
        return None, None, None
    lower = raw.lower()
    if 'remote' in lower:
        return None, None, 'Remote'
    parts = [p.strip() for p in raw.split(',') if p.strip()]
    city = parts[0] if parts else None
    region = None
    country = None
    if len(parts) >= 2:
        second = parts[1]
        region = _STATE_CODES.get(second.lower(), second)
    if len(parts) >= 3:
        country = parts[-1]
    elif len(parts) == 2 and parts[1].lower() not in _STATE_CODES:
        country = parts[1]
    elif len(parts) == 2:
        country = 'United States'
    return city, region, country


# ── Main Enrichment ───────────────────────────────────────────────────────────

def enrich_all():
    """Backfill normalized fields for all jobs."""
    conn = get_connection()

    # Fetch jobs missing any enrichment field
    rows = conn.execute("""
        SELECT id, title, location, location_raw, department, first_seen_at, posting_status
        FROM job_postings
        WHERE seniority IS NULL
           OR work_model IS NULL
           OR normalized_department IS NULL
           OR role_family IS NULL
           OR location_raw IS NULL
           OR location_city IS NULL
           OR location_region IS NULL
           OR location_country IS NULL
           OR remote_scope IS NULL
           OR posting_status IS NULL
           OR last_status_change_at IS NULL
    """).fetchall()

    if not rows:
        return 0

    updates = []
    for r in rows:
        city, region, country = _normalize_location_fields(r["location_raw"] or r["location"])
        updates.append((
            _parse_seniority(r["title"]),
            _classify_work_model(r["location"], r["title"]),
            _classify_remote_scope(r["location"], r["title"]),
            _normalize_department(r["department"]),
            _infer_role_family(r["title"], r["department"]),
            r["location_raw"] or r["location"],
            city,
            region,
            country,
            r["posting_status"] or 'active',
            r["first_seen_at"],
            r["id"],
        ))

    with conn:
        conn.executemany("""
            UPDATE job_postings
            SET seniority = ?,
                work_model = ?,
                remote_scope = COALESCE(remote_scope, ?),
                normalized_department = ?,
                role_family = ?,
                location_raw = COALESCE(location_raw, ?),
                location_city = ?,
                location_region = ?,
                location_country = ?,
                posting_status = COALESCE(posting_status, ?),
                last_status_change_at = COALESCE(last_status_change_at, ?)
            WHERE id = ?
        """, updates)

    count = len(updates)
    conn.close()
    return count
