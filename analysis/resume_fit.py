import hashlib
import io
import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime
from typing import Optional

from db import queries


PROVIDER = "groq"
PROMPT_VERSION = "resume-fit-v1"
DEFAULT_MODEL = "llama-3.3-70b-versatile"
PROFILE_ALLOWED_KEYS = {
    "headline",
    "target_roles",
    "role_families",
    "seniority",
    "skills",
    "domains",
    "strengths",
    "remote_preference",
}
EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
PHONE_RE = re.compile(r"(?:\+?\d[\s().-]*){8,}\d")
URL_RE = re.compile(r"\b(?:https?://|www\.)\S+|\b(?:linkedin|github)\.com/\S+", re.I)
LEADING_NAME_RE = re.compile(r"^[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2}\s+(?=(?:is|has|with)\b)")
LEADING_NAME_COMMA_RE = re.compile(r"^[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2},\s+")

SENIORITY_ORDER = {
    "intern": 0,
    "junior": 1,
    "mid": 2,
    "senior": 3,
    "lead": 4,
    "staff": 4,
    "principal": 5,
    "manager": 4,
    "director": 5,
    "head": 6,
    "vp": 7,
    "c-level": 8,
}


def extract_resume_text(filename: str, content: bytes) -> str:
    suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else "txt"
    if suffix in {"txt", "md"}:
        return content.decode("utf-8", errors="replace").strip()
    if suffix == "pdf":
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise RuntimeError("Install pypdf to upload PDF resumes.") from exc
        reader = PdfReader(io.BytesIO(content))
        return "\n".join(page.extract_text() or "" for page in reader.pages).strip()
    if suffix == "docx":
        try:
            from docx import Document
        except ImportError as exc:
            raise RuntimeError("Install python-docx to upload DOCX resumes.") from exc
        doc = Document(io.BytesIO(content))
        return "\n".join(p.text for p in doc.paragraphs if p.text).strip()
    raise RuntimeError("Upload a .txt, .md, .pdf, or .docx resume.")


def analyze_resume_matches(
    resume_text: str,
    *,
    company_type: Optional[str] = None,
    limit: int = 20,
    shortlist_limit: int = 120,
) -> dict:
    if company_type not in {None, "startup", "bigco"}:
        raise ValueError("Choose startups, big companies, or both.")
    resume_hash = hashlib.sha256(resume_text.encode("utf-8")).hexdigest()
    model = _model()
    profile = parse_resume_profile(resume_text)
    resume_id = queries.upsert_resume_profile(
        resume_hash,
        profile,
        PROVIDER,
        model,
        PROMPT_VERSION,
    )

    pool = queries.get_jobs_for_fit_pool(
        **_candidate_filters(profile),
        company_type=company_type,
    )
    shortlisted = shortlist_jobs(profile, pool, limit=max(shortlist_limit, limit))
    matches = _evaluate_jobs(resume_id, profile, _hydrate_job_details(shortlisted[:limit]))
    matches.sort(key=lambda row: (row["fit_score"], row["deterministic_score"]), reverse=True)
    return {
        "resume_id": resume_id,
        "resume_hash": resume_hash,
        "provider": PROVIDER,
        "model": model,
        "prompt_version": PROMPT_VERSION,
        "profile": profile,
        "shortlist_count": len(shortlisted),
        "matches": matches,
    }


def analyze_single_job(resume_text: str, job_id: int) -> dict:
    resume_hash = hashlib.sha256(resume_text.encode("utf-8")).hexdigest()
    model = _model()
    profile = parse_resume_profile(resume_text)
    resume_id = queries.upsert_resume_profile(
        resume_hash,
        profile,
        PROVIDER,
        model,
        PROMPT_VERSION,
    )
    job = queries.get_job_for_fit(job_id)
    if not job:
        raise ValueError("Active job not found")
    scored = _score_job(profile, job)
    match = _evaluate_jobs(resume_id, profile, [scored])[0]
    return {
        "resume_id": resume_id,
        "resume_hash": resume_hash,
        "provider": PROVIDER,
        "model": model,
        "prompt_version": PROMPT_VERSION,
        "profile": profile,
        "match": match,
    }


def parse_resume_profile(resume_text: str) -> dict:
    resume_text = resume_text.strip()
    if len(resume_text) < 80:
        raise RuntimeError("Resume text is too short to analyze.")
    prompt = {
        "task": "Extract a structured resume profile for job matching.",
        "rules": [
            "Return only valid JSON.",
            "Do not infer skills that are not supported by the resume.",
            "Use concise arrays. Prefer canonical skill names.",
            "Do not extract or return the candidate's name, email, phone number, address, URLs, school IDs, or social profile handles.",
            "Do not include specific location preferences; only summarize remote preference using the schema enum.",
            "Write headline and strengths without direct personal identifiers.",
            "Location and remote preferences are context only, not scoring factors.",
        ],
        "schema": {
            "headline": "one sentence without name, email, phone, address, URL, or social handle",
            "target_roles": ["string"],
            "role_families": ["software_engineering", "ml_ai", "data", "product", "design", "sales", "marketing", "customer_success", "people", "finance", "legal", "security", "operations", "other"],
            "seniority": "intern|junior|mid|senior|lead|staff|principal|manager|director|head|vp|c-level|null",
            "skills": ["string"],
            "domains": ["string"],
            "strengths": ["short career strengths without personal identifiers"],
            "remote_preference": "remote_only|remote_preferred|hybrid_ok|onsite_ok|unknown",
        },
        "resume_text": resume_text[:24000],
    }
    profile = _chat_json([
        {"role": "system", "content": "You extract resume facts into strict JSON for a recruiting match engine."},
        {"role": "user", "content": json.dumps(prompt)},
    ])
    profile.setdefault("target_roles", [])
    profile.setdefault("role_families", [])
    profile.setdefault("skills", [])
    profile.setdefault("domains", [])
    profile.setdefault("strengths", [])
    profile.setdefault("remote_preference", "unknown")
    return sanitize_resume_profile(profile)


def shortlist_jobs(profile: dict, jobs: list[dict], *, limit: int = 120) -> list[dict]:
    scored = [_score_job(profile, job) for job in jobs]
    scored.sort(key=lambda row: row["deterministic_score"], reverse=True)
    return scored[:limit]


def _candidate_filters(profile: dict) -> dict:
    skills = []
    for skill in profile.get("skills") or []:
        text = str(skill).strip()
        if text:
            skills.extend([text, text.upper(), text.title()])
    seniority = profile.get("seniority")
    seniorities = _seniority_window(seniority) if seniority else []
    return {
        "skills": list(dict.fromkeys(skills))[:40],
        "role_families": list(dict.fromkeys(profile.get("role_families") or []))[:8],
        "seniorities": seniorities,
        "title_terms": _title_terms(profile.get("target_roles") or [])[:12],
        "domains": [str(d).strip() for d in (profile.get("domains") or []) if str(d).strip()][:8],
        "limit": 5000,
    }


def _seniority_window(seniority: str) -> list[str]:
    if seniority not in SENIORITY_ORDER:
        return [seniority]
    value = SENIORITY_ORDER[seniority]
    return [
        level for level, score in SENIORITY_ORDER.items()
        if abs(score - value) <= 1
    ]


def _title_terms(target_roles: list[str]) -> list[str]:
    terms = []
    for role in target_roles:
        for token in _tokens(role):
            if len(token) >= 4:
                terms.append(token)
    return list(dict.fromkeys(terms))


def _evaluate_jobs(resume_id: int, profile: dict, jobs: list[dict]) -> list[dict]:
    cached_or_pending = []
    pending = []
    for job in jobs:
        cached = queries.get_cached_resume_fit(resume_id, job["id"], PROMPT_VERSION)
        if cached:
            cached_or_pending.append(_merge_fit(job, cached))
        else:
            pending.append(job)

    for chunk in _chunks(pending, 8):
        fits = _request_fit_batch(profile, chunk)
        by_id = {int(row.get("job_id")): row for row in fits if row.get("job_id") is not None}
        for job in chunk:
            fit = _normalize_fit(by_id.get(job["id"]), job)
            queries.save_resume_fit(
                resume_id,
                job["id"],
                deterministic_score=job["deterministic_score"],
                fit_score=fit["fit_score"],
                verdict=fit["verdict"],
                why=fit["why"],
                gaps=fit["gaps"],
                resume_pointers=fit["resume_pointers"],
                location_note=fit.get("location_note"),
                location_blocker=fit.get("location_blocker", False),
                provider=PROVIDER,
                model=_model(),
                prompt_version=PROMPT_VERSION,
            )
            fit["cached"] = False
            cached_or_pending.append(_merge_fit(job, fit))
    return cached_or_pending


def _hydrate_job_details(jobs: list[dict]) -> list[dict]:
    detailed = []
    for job in jobs:
        full = queries.get_job_for_fit(job["id"]) or {}
        merged = {**job, **full}
        merged["skills"] = job.get("skills") or _split_skills(full.get("skills"))
        merged["matched_skills"] = job.get("matched_skills", [])
        merged["deterministic_score"] = job["deterministic_score"]
        merged["location_note"] = job.get("location_note")
        merged["location_blocker"] = job.get("location_blocker", False)
        detailed.append(merged)
    return detailed


def _request_fit_batch(profile: dict, jobs: list[dict]) -> list[dict]:
    packet = {
        "task": "Evaluate resume fit for each job. Return only valid JSON.",
        "rules": [
            "Score fit from 0 to 100.",
            "Do not score location or remote compatibility. Location can only appear in location_note/location_blocker.",
            "Use evidence from the resume profile and job fields only.",
            "If job descriptions are absent, say what is unknown instead of inventing requirements.",
            "Give direct resume pointers the candidate can act on.",
        ],
        "response_schema": {
            "fits": [{
                "job_id": 123,
                "fit_score": 0,
                "verdict": "strong fit|possible fit|stretch|weak fit",
                "why": ["string"],
                "gaps": ["string"],
                "resume_pointers": ["string"],
                "location_note": "string or null",
                "location_blocker": False,
            }]
        },
        "resume_profile": profile,
        "jobs": [_job_packet(job) for job in jobs],
    }
    data = _chat_json([
        {"role": "system", "content": "You are a careful career fit analyst. You produce strict JSON only."},
        {"role": "user", "content": json.dumps(packet)},
    ])
    fits = data.get("fits", data if isinstance(data, list) else [])
    return fits if isinstance(fits, list) else []


def _score_job(profile: dict, job: dict) -> dict:
    row = dict(job)
    job_skills = _split_skills(row.get("skills"))
    resume_skills = {_norm_skill(s) for s in profile.get("skills", []) if _norm_skill(s)}
    job_skill_norms = {_norm_skill(s) for s in job_skills if _norm_skill(s)}
    overlap = sorted(job_skill_norms & resume_skills)

    score = 0.0
    score += min(len(overlap) * 8.0, 40.0)

    profile_roles = set(profile.get("role_families") or [])
    if row.get("role_family") and row["role_family"] in profile_roles:
        score += 25.0

    if _seniority_compatible(profile.get("seniority"), row.get("seniority")):
        score += 15.0

    title_score = _title_similarity(profile.get("target_roles") or [], row.get("title") or "")
    score += title_score * 12.0

    if _sector_match(profile.get("domains") or [], row.get("sector") or ""):
        score += 5.0

    score += _freshness_score(row.get("first_seen_at"))

    row["skills"] = job_skills
    row["matched_skills"] = overlap
    row["deterministic_score"] = round(min(score, 100.0), 1)
    row["location_note"] = _location_note(profile, row)
    row["location_blocker"] = _location_blocker(profile, row)
    return row


def _chat_json(messages: list[dict]) -> dict:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("Set GROQ_API_KEY to enable LLM resume matching.")
    body = {
        "model": _model(),
        "messages": messages,
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
    }
    request = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 MosaicTracker/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Groq API error {exc.code}: {detail[:500]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Groq API request failed: {exc}") from exc
    content = payload["choices"][0]["message"]["content"]
    return _loads_json(content)


def _loads_json(content: str) -> dict:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, flags=re.S)
        if not match:
            raise
        return json.loads(match.group(0))


def _model() -> str:
    return os.getenv("LLM_MODEL") or os.getenv("GROQ_MODEL") or DEFAULT_MODEL


def sanitize_resume_profile(profile: dict) -> dict:
    """Keep only matching-useful profile fields and strip obvious direct PII."""
    clean = {key: profile.get(key) for key in PROFILE_ALLOWED_KEYS if key in profile}
    clean["headline"] = _redact_pii_text(clean.get("headline") or "")
    clean["target_roles"] = _clean_string_list(clean.get("target_roles"), limit=12)
    clean["role_families"] = _clean_string_list(clean.get("role_families"), limit=8)
    clean["skills"] = _clean_string_list(clean.get("skills"), limit=80)
    clean["domains"] = _clean_string_list(clean.get("domains"), limit=20)
    clean["strengths"] = _clean_string_list(clean.get("strengths"), limit=12)

    seniority = clean.get("seniority")
    clean["seniority"] = seniority if seniority in SENIORITY_ORDER else None

    remote_preference = clean.get("remote_preference")
    if remote_preference not in {"remote_only", "remote_preferred", "hybrid_ok", "onsite_ok", "unknown"}:
        remote_preference = "unknown"
    clean["remote_preference"] = remote_preference
    return clean


def _clean_string_list(value, *, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    rows = []
    for item in value:
        text = _redact_pii_text(str(item)).strip()
        if text and text != "[redacted]":
            rows.append(text[:120])
    return list(dict.fromkeys(rows))[:limit]


def _redact_pii_text(value: str) -> str:
    text = str(value or "")
    text = EMAIL_RE.sub("[redacted]", text)
    text = URL_RE.sub("[redacted]", text)
    text = PHONE_RE.sub("[redacted]", text)
    text = LEADING_NAME_RE.sub("Candidate ", text)
    text = LEADING_NAME_COMMA_RE.sub("", text)
    text = re.sub(
        r"\b(?:my name is|name is|candidate name is)\s+[^,.]+",
        "candidate",
        text,
        flags=re.I,
    )
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _split_skills(value) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(v) for v in value if v]
    return [part for part in str(value).split(",") if part]


def _norm_skill(value: str) -> str:
    return re.sub(r"[^a-z0-9+#.]+", " ", value.lower()).strip()


def _seniority_compatible(resume_level: Optional[str], job_level: Optional[str]) -> bool:
    if not resume_level or not job_level:
        return False
    if resume_level == job_level:
        return True
    rv = SENIORITY_ORDER.get(resume_level)
    jv = SENIORITY_ORDER.get(job_level)
    if rv is None or jv is None:
        return False
    return abs(rv - jv) <= 1


def _title_similarity(target_roles: list[str], title: str) -> float:
    title_tokens = _tokens(title)
    if not title_tokens:
        return 0.0
    best = 0.0
    for role in target_roles:
        role_tokens = _tokens(role)
        if not role_tokens:
            continue
        best = max(best, len(title_tokens & role_tokens) / len(role_tokens))
    return min(best, 1.0)


def _tokens(text: str) -> set[str]:
    stop = {"and", "or", "the", "of", "for", "to", "ii", "iii"}
    return {t for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in stop}


def _sector_match(domains: list[str], sector: str) -> bool:
    sector_tokens = _tokens(sector)
    for domain in domains:
        if _tokens(domain) & sector_tokens:
            return True
    return False


def _freshness_score(first_seen_at: Optional[str]) -> float:
    if not first_seen_at:
        return 0.0
    try:
        created = datetime.fromisoformat(first_seen_at.replace("Z", "+00:00").split("+")[0])
    except ValueError:
        return 0.0
    days = (datetime.utcnow() - created).days
    if days <= 7:
        return 3.0
    if days <= 30:
        return 1.5
    return 0.0


def _location_note(profile: dict, job: dict) -> Optional[str]:
    pref = profile.get("remote_preference") or "unknown"
    if pref == "remote_only" and job.get("work_model") != "remote":
        return f"Location was not scored, but the resume says remote-only and this job is {job.get('work_model') or 'unspecified'}."
    if job.get("location"):
        return f"Location was not scored. Job location: {job['location']}."
    return None


def _location_blocker(profile: dict, job: dict) -> bool:
    return profile.get("remote_preference") == "remote_only" and job.get("work_model") != "remote"


def _job_packet(job: dict) -> dict:
    return {
        "job_id": job["id"],
        "company": job.get("company_name"),
        "title": job.get("title"),
        "sector": job.get("sector"),
        "company_type": job.get("company_type"),
        "department": job.get("normalized_department") or job.get("department"),
        "role_family": job.get("role_family"),
        "seniority": job.get("seniority"),
        "employment_type": job.get("employment_type"),
        "work_model": job.get("work_model"),
        "location": job.get("location"),
        "known_skills": job.get("skills") or [],
        "matched_skills": job.get("matched_skills") or [],
        "deterministic_score": job.get("deterministic_score"),
        "description_excerpt": (job.get("description") or "")[:1200],
    }


def _normalize_fit(fit: Optional[dict], job: dict) -> dict:
    if not fit:
        return {
            "job_id": job["id"],
            "fit_score": int(job["deterministic_score"]),
            "verdict": "possible fit",
            "why": ["The LLM did not return a result for this job; this is based on the shortlist score."],
            "gaps": ["Run the comparison again for a fuller explanation."],
            "resume_pointers": ["Make sure the resume clearly lists the matched skills for this role."],
            "location_note": job.get("location_note"),
            "location_blocker": job.get("location_blocker", False),
        }
    return {
        "job_id": job["id"],
        "fit_score": max(0, min(100, int(fit.get("fit_score", job["deterministic_score"])))),
        "verdict": str(fit.get("verdict") or "possible fit"),
        "why": _string_list(fit.get("why")),
        "gaps": _string_list(fit.get("gaps")),
        "resume_pointers": _string_list(fit.get("resume_pointers")),
        "location_note": fit.get("location_note") or job.get("location_note"),
        "location_blocker": bool(fit.get("location_blocker", job.get("location_blocker", False))),
    }


def _merge_fit(job: dict, fit: dict) -> dict:
    return {
        "job": {
            "id": job["id"],
            "company_id": job.get("company_id"),
            "company_name": job.get("company_name"),
            "title": job.get("title"),
            "sector": job.get("sector"),
            "company_type": job.get("company_type"),
            "department": job.get("normalized_department") or job.get("department"),
            "role_family": job.get("role_family"),
            "seniority": job.get("seniority"),
            "work_model": job.get("work_model"),
            "location": job.get("location"),
            "url": job.get("url"),
            "first_seen_at": job.get("first_seen_at"),
        },
        "deterministic_score": job["deterministic_score"],
        "matched_skills": job.get("matched_skills", []),
        "fit_score": fit["fit_score"],
        "verdict": fit["verdict"],
        "why": fit.get("why", []),
        "gaps": fit.get("gaps", []),
        "resume_pointers": fit.get("resume_pointers", []),
        "location_note": fit.get("location_note"),
        "location_blocker": fit.get("location_blocker", False),
        "cached": fit.get("cached", False),
    }


def _string_list(value) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()][:6]
    if value:
        return [str(value)]
    return []


def _chunks(rows: list[dict], size: int):
    for i in range(0, len(rows), size):
        yield rows[i:i + size]
