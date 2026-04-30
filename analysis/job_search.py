"""Find similar jobs in the DB given a parsed JD.

Deterministic shortlister that reuses analysis.resume_fit's scoring
infrastructure by constructing a pseudo-profile from the parsed JD.

Future-options doc:
    See `docs/JOB_SEARCH_BACKLOG.md` for embedding-based semantic search
    (separate module, much heavier infra — pgvector / vector store + embedding
    cost on every job ingestion + every query).
"""

from __future__ import annotations

from typing import Optional

from db import queries
from analysis.resume_fit import shortlist_jobs, _candidate_filters

_JD_LEVEL_TO_RESUME_FIT = {
    # parse_jd.level → resume_fit.SENIORITY_ORDER vocabulary
    "intern": "intern",
    "junior": "junior",
    "mid": "mid",
    "senior": "senior",
    "staff": "staff",
    "principal": "principal",
    "manager": "manager",
    "director": "director",
    "head": "head",
    "vp": "vp",
    "c_suite": "c-level",
}


def find_similar_jobs(
    parsed_jd: dict,
    *,
    limit: int = 20,
    company_type: Optional[str] = None,
) -> dict:
    """Score every active job in the DB against a parsed JD.

    Returns:
        {
            "shortlist_count": int,           # size of pre-score candidate pool
            "matches": [job_with_score, ...], # top `limit` by deterministic_score
            "pseudo_profile": dict,           # what the parser constructed
        }
    """
    profile = _profile_from_jd(parsed_jd)
    pool = queries.get_jobs_for_fit_pool(
        **_candidate_filters(profile),
        company_type=company_type,
    )
    shortlisted = shortlist_jobs(profile, pool, limit=max(limit * 4, 80))
    return {
        "shortlist_count": len(shortlisted),
        "matches": shortlisted[:limit],
        "pseudo_profile": profile,
    }


def _profile_from_jd(parsed_jd: dict) -> dict:
    """Build a resume_fit-compatible 'profile' from a parsed JD."""
    raw_level = (parsed_jd.get("level") or "").lower().strip()
    seniority = _JD_LEVEL_TO_RESUME_FIT.get(raw_level, raw_level)

    skills: list[str] = []
    for key in ("must_have_skills", "nice_to_have_skills", "stack_signals"):
        for s in parsed_jd.get(key) or []:
            text = str(s).strip()
            if text:
                skills.append(text)

    function = (parsed_jd.get("function") or "").strip()
    sub_function = (parsed_jd.get("sub_function") or "").strip()
    role_families = [function] if function else []

    role_title = parsed_jd.get("role_title") or ""
    target_roles = [role_title] if role_title else []
    if sub_function:
        target_roles.append(f"{sub_function} {function}".strip())

    return {
        "headline": role_title,
        "target_roles": target_roles[:5],
        "role_families": role_families,
        "seniority": seniority or "",
        "skills": list(dict.fromkeys(skills))[:60],
        "domains": [],
        "strengths": [],
        "remote_preference": (parsed_jd.get("geography") or {}).get("type"),
    }
