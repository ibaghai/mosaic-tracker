"""
FastAPI REST API — thin wrapper over db/queries.py
Run with: uvicorn api.app:app --reload --port 8000
"""

from fastapi import Body, Cookie, Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import os

from db.models import init_db
from db import queries
from db import auth as auth_mod
from analysis.resume_fit import (
    analyze_resume_matches,
    analyze_single_job,
    extract_resume_text,
)

app = FastAPI(title="Mosaic — Startup Hiring Tracker API", version="2.0")

cors_origins = {
    "http://localhost:3000",
    "http://localhost:3001",
}

frontend_url = os.getenv("FRONTEND_URL")
if frontend_url:
    cors_origins.add(frontend_url.rstrip("/"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=sorted(cors_origins),
    allow_origin_regex=r"http://localhost:\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()
queries.scrub_resume_profile_pii()
queries.scrub_resume_fit_pii()
auth_mod.purge_expired_sessions()


# ── Auth ─────────────────────────────────────────────────────────────────────

# Cookie behaviour:
#   httponly       — JS can't read it; only same-origin fetches with `credentials: 'include'`.
#   samesite=lax   — works for typical app navigation; the dashboard fetches against
#                    a different localhost port in dev which counts as cross-site,
#                    but `lax` plus our explicit CORS allow_credentials=True is fine
#                    for fetch() calls. (If you ever serve dashboard + api from
#                    different parent domains in prod, switch to samesite=none + secure.)
#   secure         — set to True in prod (HTTPS); False in dev so localhost works.
_COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").strip().lower() in {"1", "true", "yes"}
_COOKIE_KW = {
    "httponly": True,
    "samesite": "lax",
    "secure": _COOKIE_SECURE,
    "path": "/",
}


def current_user(
    request: Request,
    session_token: Optional[str] = Cookie(default=None, alias=auth_mod.SESSION_COOKIE_NAME),
) -> dict:
    """FastAPI dependency: returns the logged-in user, or 401."""
    user = auth_mod.get_user_for_token(session_token)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


def optional_user(
    session_token: Optional[str] = Cookie(default=None, alias=auth_mod.SESSION_COOKIE_NAME),
) -> Optional[dict]:
    """For endpoints that should still respond when not logged in (e.g. /api/auth/me)."""
    return auth_mod.get_user_for_token(session_token)


@app.post("/api/auth/signup")
def auth_signup(
    response: Response,
    email: str = Body(..., embed=True),
    password: str = Body(..., embed=True),
):
    if not auth_mod.signups_allowed():
        raise HTTPException(403, "Signups are disabled.")
    try:
        user = auth_mod.create_user(email, password)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    token = auth_mod.create_session(user["id"])
    response.set_cookie(auth_mod.SESSION_COOKIE_NAME, token, **_COOKIE_KW)
    return {"id": user["id"], "email": user["email"]}


@app.post("/api/auth/login")
def auth_login(
    response: Response,
    email: str = Body(..., embed=True),
    password: str = Body(..., embed=True),
):
    user = auth_mod.verify_login(email, password)
    if not user:
        raise HTTPException(401, "Wrong email or password.")
    token = auth_mod.create_session(user["id"])
    response.set_cookie(auth_mod.SESSION_COOKIE_NAME, token, **_COOKIE_KW)
    return {"id": user["id"], "email": user["email"]}


@app.post("/api/auth/logout")
def auth_logout(
    response: Response,
    session_token: Optional[str] = Cookie(default=None, alias=auth_mod.SESSION_COOKIE_NAME),
):
    auth_mod.delete_session(session_token)
    response.delete_cookie(auth_mod.SESSION_COOKIE_NAME, path="/")
    return {"ok": True}


@app.get("/api/auth/me")
def auth_me(user: Optional[dict] = Depends(optional_user)):
    """Current user, or null if not logged in. Used by the frontend to gate UI."""
    return {"user": user, "signups_allowed": auth_mod.signups_allowed()}


# ── Overview ─────────────────────────────────────────────────────────────────

@app.get("/api/overview")
def overview(company_type: Optional[str] = None):
    return queries.get_overview_stats(company_type=company_type)


# ── Companies ────────────────────────────────────────────────────────────────

@app.get("/api/companies")
def companies():
    return queries.get_company_stats()


@app.get("/api/companies/velocity")
def company_velocity(days: int = 7):
    return queries.get_company_velocity(days=days)


@app.get("/api/companies/{company_id}")
def company_detail(company_id: int):
    detail = queries.get_company_detail(company_id)
    if not detail:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Company not found")
    skills = queries.get_company_skills(company_id)
    departments = queries.get_company_department_breakdown(company_id)
    return {**detail, "top_skills": skills, "departments": departments}


# ── Sectors ──────────────────────────────────────────────────────────────────

@app.get("/api/sectors")
def sectors():
    return queries.get_sector_breakdown()


# ── Departments ──────────────────────────────────────────────────────────────

@app.get("/api/departments")
def departments(company_type: Optional[str] = None):
    return queries.get_department_breakdown(company_type=company_type)


# ── Seniority ────────────────────────────────────────────────────────────────

@app.get("/api/seniority")
def seniority(company_type: Optional[str] = None):
    return queries.get_seniority_breakdown(company_type=company_type)


# ── Work Models ──────────────────────────────────────────────────────────────

@app.get("/api/work-models")
def work_models(company_type: Optional[str] = None):
    return queries.get_work_model_breakdown(company_type=company_type)


# ── Role Families / Freshness ────────────────────────────────────────────────

@app.get("/api/role-families")
def role_families(company_type: Optional[str] = None):
    return queries.get_role_family_breakdown(company_type=company_type)


@app.get("/api/jobs/freshness")
def job_freshness(company_type: Optional[str] = None):
    return queries.get_freshness_breakdown(company_type=company_type)


# ── Skills ───────────────────────────────────────────────────────────────────

@app.get("/api/skills")
def skills(company_type: Optional[str] = None, limit: int = 30):
    return queries.get_skill_counts(company_type=company_type, limit=limit)


# ── Jobs ─────────────────────────────────────────────────────────────────────

@app.get("/api/jobs")
def jobs(
    company_id: Optional[int] = None,
    sector: Optional[str] = None,
    search: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    location: Optional[str] = None,
    employment_type: Optional[str] = None,
    skill: Optional[str] = None,
    seniority: Optional[str] = None,
    work_model: Optional[str] = None,
    company_type: Optional[str] = None,
    department: Optional[str] = None,
    ats_type: Optional[str] = None,
    funding_round: Optional[str] = None,
):
    return queries.get_active_jobs(
        company_id=company_id,
        sector=sector,
        search=search,
        date_from=date_from,
        date_to=date_to,
        location=location,
        employment_type=employment_type,
        skill=skill,
        seniority=seniority,
        work_model=work_model,
        company_type=company_type,
        department=department,
        ats_type=ats_type,
        funding_round=funding_round,
    )


@app.get("/api/jobs/filters")
def job_filters():
    return queries.get_filter_options()


@app.get("/api/jobs/trends")
def job_trends():
    return queries.get_job_count_over_time()


@app.get("/api/jobs/{job_id}")
def job_detail(job_id: int):
    row = queries.get_active_job(job_id)
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    return row


# ── Changes ──────────────────────────────────────────────────────────────────

@app.get("/api/changes/events")
def change_events(
    limit: int = 500,
    event_type: Optional[str] = None,
    sector: Optional[str] = None,
    company_name: Optional[str] = None,
):
    return queries.get_recent_events(
        limit=limit,
        event_type=event_type,
        sector=sector,
        company_name=company_name,
    )


@app.get("/api/changes/movers")
def fastest_movers(days: int = 7):
    return queries.get_fastest_movers(days=days)


@app.get("/api/changes/sector-delta")
def sector_delta():
    return queries.get_sector_delta()


# ── Cross-Tabs ────────────────────────────────────────────────────────────────

@app.get("/api/cross/dept-sector")
def dept_sector_cross():
    return queries.get_dept_sector_cross()


@app.get("/api/cross/seniority-sector")
def seniority_sector_cross():
    return queries.get_seniority_sector_cross()


@app.get("/api/cross/remote-sector")
def remote_sector_cross(company_type: Optional[str] = "startup"):
    return queries.get_remote_mix_by_sector(company_type=company_type)


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/api/health")
def scraper_health():
    return queries.get_scraper_health()


# ── Resume Fit ────────────────────────────────────────────────────────────────

def _fit_error(exc: Exception) -> HTTPException:
    message = str(exc)
    if "GROQ_API_KEY" in message:
        return HTTPException(
            status_code=503,
            detail="Resume matching is not configured yet. Try again later.",
        )
    if "rate_limit_exceeded" in message or "429" in message:
        return HTTPException(
            status_code=429,
            detail="Resume matching is temporarily rate-limited. Try again in a few seconds or lower the match count.",
        )
    if "Groq API" in message:
        return HTTPException(
            status_code=503,
            detail="Resume matching is temporarily unavailable. Try again later.",
        )
    return HTTPException(status_code=400, detail=message)


@app.post("/api/fit/matches")
async def fit_matches(
    resume: UploadFile = File(...),
    company_type: Optional[str] = Form(None),
    limit: int = Form(20),
):
    try:
        content = await resume.read()
        resume_text = extract_resume_text(resume.filename or "resume.txt", content)
        return analyze_resume_matches(
            resume_text,
            company_type=company_type or None,
            limit=max(1, min(limit, 40)),
        )
    except (RuntimeError, ValueError) as exc:
        raise _fit_error(exc)


@app.post("/api/fit/jobs/{job_id}")
async def fit_job(
    job_id: int,
    resume: UploadFile = File(...),
):
    try:
        content = await resume.read()
        resume_text = extract_resume_text(resume.filename or "resume.txt", content)
        return analyze_single_job(resume_text, job_id)
    except (RuntimeError, ValueError) as exc:
        raise _fit_error(exc)


@app.post("/api/fit/from-jobs")
async def fit_from_jobs(
    resume: UploadFile = File(...),
    job_ids: str = Form(...),  # comma-separated to keep multipart simple
    limit: int = Form(20),
):
    """Score a resume against an explicit set of job ids — used by the
    "score against these filtered jobs" panel on /jobs.

    The candidate pool is exactly these ids (no profile-based pre-filter).
    Inactive ids are dropped silently. Capped at 500 ids per request.
    """
    try:
        ids = [int(x) for x in job_ids.split(",") if x.strip()]
    except ValueError:
        raise HTTPException(400, "job_ids must be comma-separated integers")
    if not ids:
        raise HTTPException(400, "job_ids is empty")
    if len(ids) > 500:
        raise HTTPException(400, "Cap is 500 jobs per scoring request — narrow your filters first.")
    try:
        content = await resume.read()
        resume_text = extract_resume_text(resume.filename or "resume.txt", content)
        return analyze_resume_matches(
            resume_text,
            limit=max(1, min(limit, 40)),
            restrict_to_job_ids=ids,
        )
    except (RuntimeError, ValueError) as exc:
        raise _fit_error(exc)


# ── Outreach (v1 personal job-search assistant) ───────────────────────────────

from analysis import people as people_mod
from analysis import jd_parse as jd_parse_mod
from analysis import outreach as outreach_mod
from analysis import resume_tailor as resume_tailor_mod
import json


def _outreach_error(exc: Exception) -> HTTPException:
    msg = str(exc)
    if isinstance(exc, people_mod.ApolloCapExceeded):
        return HTTPException(status_code=429, detail=msg)
    if isinstance(exc, people_mod.ApolloError):
        if "free plan" in msg.lower() or "API_INACCESSIBLE" in msg:
            return HTTPException(status_code=402, detail=msg)
        return HTTPException(status_code=502, detail=f"Apollo error: {msg}")
    if "GROQ_API_KEY" in msg:
        return HTTPException(status_code=503, detail="LLM not configured.")
    return HTTPException(status_code=400, detail=msg)


def _load_job_with_company(job_id: int) -> dict:
    from db.models import get_connection
    conn = get_connection()
    try:
        row = conn.execute("""
            SELECT jp.id, jp.title, jp.description, jp.url, jp.location,
                   jp.company_id, c.name AS company_name, c.website
            FROM job_postings jp JOIN companies c ON c.id = jp.company_id
            WHERE jp.id = ?
        """, (job_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"job {job_id} not found")
        return dict(row)
    finally:
        conn.close()


@app.get("/api/outreach/usage")
def outreach_usage():
    return people_mod.usage_status()


@app.post("/api/outreach/jobs/{job_id}/generate")
async def outreach_generate(
    job_id: int,
    resume: Optional[UploadFile] = File(None),
    archetypes: str = Form("recruiter,hiring_manager,recent_joiner"),
    enrich_top: int = Form(1),
    include_tailored_resume: bool = Form(True),
):
    """Run the full pipeline for one job: parse JD, find people per archetype,
    score HMs, enrich the top of each, generate outreach drafts, and (if a
    resume is uploaded) produce a tailored variant.

    Cost: ~1 search + ~enrich_top reveals per archetype, plus 1 LLM call each
    for parse/outreach/tailor. With archetypes=3 and enrich_top=1 ≈ 6 Apollo
    credits + ~5 Groq calls per click.
    """
    try:
        job = _load_job_with_company(job_id)
        archetype_list = [a.strip() for a in archetypes.split(",") if a.strip()]
        enrich_top = max(0, min(enrich_top, 3))

        # 1. Parse JD (cheap; Groq). Some jobs in the DB have empty/missing
        # `description` — the scraper didn't capture the body. Rather than
        # 400 the user with "jd_text is empty", fall back to an empty parsed
        # shape so outreach generation can still run with just title +
        # company. The LLM in step 4 handles a sparse parsed_jd gracefully.
        jd_text = (job.get("description") or "").strip()
        if len(jd_text) < 50:
            parsed_jd = {
                "role_title": job.get("title"),
                "level": None,
                "function": None,
                "sub_function": None,
                "reports_to_phrase": None,
                "reports_to_target": None,
                "team_or_org": None,
                "geography": {"type": None, "locations": []},
                "stack_signals": [],
                "scope_signals": [],
                "key_responsibilities": [],
                "must_have_skills": [],
                "nice_to_have_skills": [],
                "company_name_in_jd": None,
                "_jd_missing": True,
            }
        else:
            parsed_jd = jd_parse_mod.parse_jd(jd_text, job_title=job["title"])

        # 2. Optional resume profile, for grounding the outreach + tailoring.
        resume_text: Optional[str] = None
        asker_profile: dict = {}
        if resume is not None:
            content = await resume.read()
            resume_text = extract_resume_text(resume.filename or "resume.txt", content)
            from analysis.resume_fit import parse_resume_profile
            asker_profile = parse_resume_profile(resume_text)

        # 3. For each requested archetype: search + score + enrich top N.
        archetype_results: dict[str, list[dict]] = {}
        for archetype in archetype_list:
            try:
                candidates = _candidates_for_archetype(
                    archetype, job, parsed_jd
                )
            except (people_mod.ApolloCapExceeded, people_mod.ApolloError) as exc:
                archetype_results[archetype] = [{"_error": str(exc)}]
                continue

            ranked = candidates
            if archetype == "hiring_manager":
                ranked = people_mod.infer_hiring_manager(parsed_jd, candidates)

            top = ranked[:enrich_top] if enrich_top else ranked[:3]
            enriched: list[dict] = []
            for cand in top:
                try:
                    full = people_mod.enrich_person(cand, reveal_personal_emails=False)
                    full["hm_score"] = cand.get("hm_score")
                    full["hm_evidence"] = cand.get("hm_evidence")
                    full["archetype"] = archetype
                    enriched.append(full)
                except (people_mod.ApolloCapExceeded, people_mod.ApolloError) as exc:
                    cand["_enrich_error"] = str(exc)
                    enriched.append(cand)
                    break
            archetype_results[archetype] = enriched

        # 4. Generate one outreach draft per enriched person.
        # A resume is optional: with one, drafts are personalized; without,
        # the LLM falls back to a generic-but-honest message (handled inside
        # generate_outreach).
        drafts: list[dict] = []
        for archetype, people in archetype_results.items():
            for person in people:
                if person.get("_error") or person.get("_enrich_error"):
                    continue
                try:
                    draft = outreach_mod.generate_outreach(
                        job=job,
                        person=person,
                        asker_profile=asker_profile,
                        archetype=archetype,
                        parsed_jd=parsed_jd,
                    )
                except RuntimeError as exc:
                    drafts.append({
                        "person_id": person.get("id"),
                        "archetype": archetype,
                        "_error": str(exc),
                    })
                    continue
                # Drafts are ephemeral until the user explicitly saves them via
                # POST /api/outreach/drafts (Save as draft) or marks one sent.
                # We return id=None so the UI knows this draft isn't persisted,
                # plus job_id so the UI can hand it back when persisting.
                drafts.append({
                    "id": None,
                    "job_id": job_id,
                    "person_id": person.get("id"),
                    "person_name": person.get("name"),
                    "person_title": person.get("title"),
                    "person_linkedin_url": person.get("linkedin_url"),
                    "person_email": person.get("email"),
                    "archetype": archetype,
                    **draft,
                })

        # 5. Optional tailored resume.
        tailored = None
        if include_tailored_resume and resume_text:
            try:
                tailored = resume_tailor_mod.tailor_resume(
                    resume_text, job=job, parsed_jd=parsed_jd
                )
            except RuntimeError as exc:
                tailored = {"_error": str(exc)}

        return {
            "job": {
                "id": job["id"],
                "title": job["title"],
                "company_name": job["company_name"],
                "url": job.get("url"),
            },
            "parsed_jd": {
                "level": parsed_jd.get("level"),
                "function": parsed_jd.get("function"),
                "reports_to_phrase": parsed_jd.get("reports_to_phrase"),
                "reports_to_target": parsed_jd.get("reports_to_target"),
                "team_or_org": parsed_jd.get("team_or_org"),
                "must_have_skills": parsed_jd.get("must_have_skills") or [],
                "jd_missing": parsed_jd.get("_jd_missing", False),
            },
            "people_by_archetype": archetype_results,
            "drafts": drafts,
            "tailored_resume": tailored,
            "apollo_usage": people_mod.usage_status(),
        }
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise _outreach_error(exc)


def _candidates_for_archetype(archetype: str, job: dict, parsed_jd: dict) -> list[dict]:
    """Search Apollo for one archetype, with cache-first behavior.

    Returns persisted, normalized people (NOT yet enriched).
    """
    cached = queries.get_people_for_company(
        job["company_id"], archetype=archetype, fresh_within_days=30
    )
    # Ignore the apollo_mock cache when not in mock mode (and vice versa)
    expected_source = "apollo_mock" if people_mod._mock_mode() else "apollo"
    cached = [p for p in cached if p.get("source") == expected_source]
    # Drop cache entries whose Apollo org name doesn't match this company. The
    # cache was populated before the name-match guard existed, so it can hold
    # rows from a wrong-company match (e.g. tracker says "Latch" but Apollo
    # returned DOOR employees because the domain was shared).
    tracker_name = job.get("company_name")
    cached = [
        p for p in cached
        if people_mod._names_match(tracker_name, p.get("company_name"))
    ]
    if cached:
        return cached

    function = (parsed_jd.get("function") or "").lower()
    target_level = ((parsed_jd.get("reports_to_target") or {}).get("level") or "").lower()

    if archetype == "recruiter":
        # Bias the title search toward the role's function so a sales role
        # finds sales recruiters rather than technical recruiters (and vice versa).
        base_titles = ["recruiter", "talent partner", "talent acquisition"]
        function_titles: list[str] = []
        if function:
            function_titles = [
                f"{function} recruiter",
                f"recruiter {function}",
                f"{function} talent",
            ]
        return people_mod.find_people_at_company(
            job["company_id"],
            titles=function_titles + base_titles,
            archetype="recruiter",
            limit=8,
        )
    if archetype == "recent_joiner":
        # Same function as the role, no level filter — recent joiners can be any level
        results = people_mod.find_people_at_company(
            job["company_id"],
            titles=[function] if function else None,
            archetype="recent_joiner",
            limit=15,
        )
        # Filter to those with start dates in last 12 months
        from datetime import datetime, timedelta
        cutoff = datetime.utcnow() - timedelta(days=365)
        fresh = []
        for p in results:
            ts = p.get("tenure_start_date")
            if ts:
                try:
                    if datetime.fromisoformat(str(ts)) >= cutoff:
                        fresh.append(p)
                except (ValueError, TypeError):
                    pass
        return fresh or results[:5]  # fall back to all if no tenure-tagged
    # hiring_manager
    if not target_level:
        target_level = {
            "intern": "manager", "junior": "manager", "mid": "manager",
            "senior": "manager", "staff": "manager", "principal": "director",
            "manager": "director", "director": "vp", "head": "vp", "vp": "c_suite",
        }.get((parsed_jd.get("level") or "").lower(), "")

    title_terms: list[str] = []
    if function and target_level:
        if target_level == "vp":
            title_terms = [f"VP {function}", f"VP of {function}", f"Vice President {function}"]
        elif target_level == "director":
            title_terms = [f"Director {function}", f"Director of {function}", f"Head of {function}"]
        elif target_level == "manager":
            title_terms = [f"{function} manager", f"Senior {function} manager"]

    return people_mod.find_people_at_company(
        job["company_id"],
        titles=title_terms or None,
        seniorities=[target_level] if target_level else ["vp", "director"],
        archetype="hiring_manager",
        limit=10,
    )


@app.post("/api/outreach/people/{person_id}/enrich")
def outreach_enrich_person(person_id: int, reveal_personal_emails: bool = False):
    try:
        return people_mod.enrich_person(person_id, reveal_personal_emails=reveal_personal_emails)
    except (RuntimeError, ValueError) as exc:
        raise _outreach_error(exc)


@app.get("/api/outreach/jobs/{job_id}")
def outreach_get(job_id: int, user: dict = Depends(current_user)):
    """Read-only fetch of any cached drafts for this job."""
    drafts = queries.get_outreach_drafts_for_job(job_id, user_id=user["id"])
    return {"job_id": job_id, "drafts": drafts}


# ── Outreach lifecycle (sent / replied / status) ─────────────────────────────

@app.get("/api/outreach/drafts")
def outreach_list_drafts(
    status: Optional[str] = None,
    archetype: Optional[str] = None,
    overdue_only: bool = False,
    company_ids: Optional[str] = None,  # comma-separated for GET-friendliness
    job_id: Optional[int] = None,
    limit: int = 200,
    user: dict = Depends(current_user),
):
    """Cross-job listing for the /outreach page. Filterable by status,
    archetype, overdue-follow-ups-only, one-or-many company_ids, and job_id.

    company_ids is parsed as a comma-separated string so the URL stays simple
    (e.g. ?company_ids=49,1018).
    """
    company_ids_list: Optional[list[int]] = None
    if company_ids:
        try:
            company_ids_list = [int(x) for x in company_ids.split(",") if x.strip()]
        except ValueError:
            raise HTTPException(400, "company_ids must be comma-separated integers")
    drafts = queries.list_outreach_drafts(
        user_id=user["id"],
        status=status,
        archetype=archetype,
        overdue_only=overdue_only,
        company_ids=company_ids_list,
        job_id=job_id,
        limit=limit,
    )
    return {
        "drafts": drafts,
        "counts": queries.outreach_status_counts(user_id=user["id"]),
    }


@app.get("/api/outreach/companies")
def outreach_companies(user: dict = Depends(current_user)):
    """Distinct companies that have outreach drafts, with per-company counts.
    Powers the company multi-select on /outreach.
    """
    return {"companies": queries.list_outreach_companies(user_id=user["id"])}


@app.get("/api/outreach/counts")
def outreach_counts(user: dict = Depends(current_user)):
    """Lightweight aggregate for sidebar / dashboard badges."""
    return queries.outreach_status_counts(user_id=user["id"])


@app.get("/api/outreach/reply-breakdown")
def outreach_reply_breakdown(user: dict = Depends(current_user)):
    """Reply-category roll-up + reply rate, for the /outreach response panel."""
    return queries.outreach_reply_breakdown(user_id=user["id"])


@app.post("/api/outreach/summary/batch")
def outreach_summary_batch(
    job_ids: list[int] = Body(..., embed=True),
    user: dict = Depends(current_user),
):
    """Per-job outreach summary, keyed by job_id (string per JSON convention).
    Used to decorate /jobs and /companies/[id] rows with conversation stats.
    """
    return {
        str(k): v
        for k, v in queries.outreach_summary_for_jobs(job_ids, user_id=user["id"]).items()
    }


@app.post("/api/outreach/drafts")
def outreach_create_draft(
    payload: dict = Body(...),
    user: dict = Depends(current_user),
):
    """Persist a generated draft. Called when the user clicks Save as draft
    or Mark sent in the UI — the generation endpoint no longer persists.

    Required: person_id, job_id, message. Everything else passes through.
    Optional: status (defaults to 'draft'); when 'sent', also stamps sent_at
    and schedules the follow-up.
    """
    requested_status = (payload.get("status") or "draft").lower()
    if requested_status not in {"draft", "sent"}:
        raise HTTPException(400, "status must be 'draft' or 'sent'")

    rationale = payload.get("rationale")
    if isinstance(rationale, dict):
        rationale_json = json.dumps(rationale)
    else:
        rationale_json = payload.get("rationale_json") or json.dumps({})

    try:
        draft_id = queries.insert_outreach_draft({
            "person_id": payload.get("person_id"),
            "job_id": payload.get("job_id"),
            "resume_id": payload.get("resume_id"),
            "subject": payload.get("subject"),
            "message": payload.get("message"),
            "rationale_json": rationale_json,
            "tone": payload.get("tone"),
            "archetype": payload.get("archetype"),
            "provider": payload.get("provider"),
            "model": payload.get("model"),
            "prompt_version": payload.get("prompt_version"),
            "user_edits": payload.get("user_edits"),
        }, user_id=user["id"])
    except ValueError as exc:
        raise HTTPException(400, str(exc))

    if requested_status == "sent":
        row = queries.mark_outreach_sent(
            draft_id,
            user_id=user["id"],
            sent_via=payload.get("sent_via") or "manual",
            user_edits=payload.get("user_edits"),
        )
        return row or {"id": draft_id, "status": "sent"}

    # status='draft' — return the freshly-inserted row
    conn = queries.get_connection()
    row = conn.execute(
        "SELECT * FROM outreach_drafts WHERE id = ? AND user_id = ?",
        (draft_id, user["id"]),
    ).fetchone()
    conn.close()
    return dict(row) if row else {"id": draft_id, "status": "draft"}


@app.post("/api/outreach/drafts/{draft_id}/sent")
def outreach_mark_sent(
    draft_id: int,
    sent_via: Optional[str] = Body(None, embed=True),
    follow_up_days: int = Body(5, embed=True),
    user_edits: Optional[str] = Body(None, embed=True),
    user: dict = Depends(current_user),
):
    """Mark a draft as sent. Stamps sent_at and schedules a follow-up."""
    row = queries.mark_outreach_sent(
        draft_id,
        user_id=user["id"],
        sent_via=sent_via,
        follow_up_days=follow_up_days,
        user_edits=user_edits,
    )
    if not row:
        raise HTTPException(404, f"draft {draft_id} not found")
    return row


@app.post("/api/outreach/drafts/{draft_id}/reply")
def outreach_log_reply(
    draft_id: int,
    reply_text: Optional[str] = Body(None, embed=True),
    reply_category: Optional[str] = Body(None, embed=True),
    user: dict = Depends(current_user),
):
    """Record an inbound reply. Sets status='replied' and clears the follow-up."""
    row = queries.log_outreach_reply(
        draft_id,
        user_id=user["id"],
        reply_text=reply_text,
        reply_category=reply_category,
    )
    if not row:
        raise HTTPException(404, f"draft {draft_id} not found")
    return row


@app.post("/api/outreach/drafts/{draft_id}/status")
def outreach_set_status(
    draft_id: int,
    status: str = Body(..., embed=True),
    user: dict = Depends(current_user),
):
    """Generic status setter (no_reply / bounced / draft / sent / replied)."""
    try:
        row = queries.set_outreach_status(draft_id, status, user_id=user["id"])
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    if not row:
        raise HTTPException(404, f"draft {draft_id} not found")
    return row


# ── User job status (saved / applied / dismissed pipeline) ───────────────────

@app.post("/api/jobs/{job_id}/status")
def jobs_set_status(
    job_id: int,
    status: str = Body(..., embed=True),
    notes: Optional[str] = Body(None, embed=True),
    user: dict = Depends(current_user),
):
    """Set or upsert a user-action status on a job
    (saved | applied | interviewing | rejected | offered | dismissed)."""
    try:
        return queries.set_user_job_status(job_id, user_id=user["id"], status=status, notes=notes)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@app.delete("/api/jobs/{job_id}/status")
def jobs_clear_status(job_id: int, user: dict = Depends(current_user)):
    """Remove the user status — e.g. unsave."""
    queries.clear_user_job_status(job_id, user_id=user["id"])
    return {"job_id": job_id, "status": None}


@app.get("/api/jobs/{job_id}/status")
def jobs_get_status(job_id: int, user: dict = Depends(current_user)):
    row = queries.get_user_job_status(job_id, user_id=user["id"])
    return row or {"job_id": job_id, "status": None}


@app.get("/api/pipeline")
def pipeline_list(
    status: Optional[str] = None,
    limit: int = 500,
    user: dict = Depends(current_user),
):
    """List jobs grouped by user pipeline status. Used by the /pipeline page."""
    return {
        "jobs": queries.list_pipeline_jobs(user_id=user["id"], status=status, limit=limit),
        "counts": queries.pipeline_status_counts(user_id=user["id"]),
    }


@app.get("/api/pipeline/counts")
def pipeline_counts(user: dict = Depends(current_user)):
    return queries.pipeline_status_counts(user_id=user["id"])


@app.post("/api/jobs/status/batch")
def jobs_status_batch(
    job_ids: list[int] = Body(..., embed=True),
    user: dict = Depends(current_user),
):
    """Bulk lookup — return { job_id: status_row } for each requested id.
    Used by listing pages to render status pills without N+1 queries.
    """
    rows = queries.get_user_job_statuses_map(job_ids, user_id=user["id"])
    # Make sure JSON keys are strings (FastAPI does this anyway, but explicit).
    return {str(k): v for k, v in rows.items()}


# ── Saved searches ───────────────────────────────────────────────────────────

@app.get("/api/saved-searches")
def saved_searches_list(
    surface: Optional[str] = None,
    user: dict = Depends(current_user),
):
    return {"searches": queries.list_saved_searches(user_id=user["id"], surface=surface)}


@app.post("/api/saved-searches")
def saved_searches_create(
    payload: dict = Body(...),
    user: dict = Depends(current_user),
):
    surface = (payload.get("surface") or "").strip()
    name = (payload.get("name") or "").strip()
    params = payload.get("params") or {}
    try:
        return queries.create_saved_search(
            user_id=user["id"],
            surface=surface,
            name=name,
            params_json=json.dumps(params),
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@app.delete("/api/saved-searches/{search_id}")
def saved_searches_delete(search_id: int, user: dict = Depends(current_user)):
    if not queries.delete_saved_search(user_id=user["id"], search_id=search_id):
        raise HTTPException(404, f"saved search {search_id} not found")
    return {"ok": True}


# ── JD-similar job discovery ──────────────────────────────────────────────────

from fastapi import Body
from analysis import job_search as job_search_mod


from analysis import jd_fetch as jd_fetch_mod  # noqa: E402


@app.post("/api/jobs/similar-to-jd")
async def jobs_similar_to_jd(
    jd_text: Optional[str] = Body(None, embed=True),
    url: Optional[str] = Body(None, embed=True),
    limit: int = Body(20, embed=True),
    company_type: Optional[str] = Body(None, embed=True),
):
    """Given pasted JD text OR a URL, return the most similar active jobs in
    the DB.

    Single Groq call to parse the JD into structured fields, then deterministic
    scoring against every active job (no per-job LLM call).

    Exactly one of `jd_text` or `url` is required. If both are provided,
    `url` wins — we fetch + extract and use that as the source of truth.
    """
    fetched: Optional[dict] = None
    if url:
        try:
            fetched = await jd_fetch_mod.fetch_jd_from_url(url)
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(status_code=400, detail=f"Could not fetch URL: {exc}")
        jd_text = fetched.get("description") or ""
        title_hint = fetched.get("title") or None
    else:
        title_hint = None

    if not jd_text or len(jd_text.strip()) < 100:
        raise HTTPException(
            status_code=400,
            detail="Paste a JD (or URL pointing to one) of at least 100 characters.",
        )
    try:
        parsed = jd_parse_mod.parse_jd(jd_text, job_title=title_hint)
    except RuntimeError as exc:
        raise _outreach_error(exc)

    result = job_search_mod.find_similar_jobs(
        parsed,
        limit=max(1, min(limit, 50)),
        company_type=company_type,
    )

    response = {
        "parsed_jd": {
            "role_title": parsed.get("role_title"),
            "level": parsed.get("level"),
            "function": parsed.get("function"),
            "sub_function": parsed.get("sub_function"),
            "must_have_skills": (parsed.get("must_have_skills") or [])[:15],
            "team_or_org": parsed.get("team_or_org"),
        },
        "shortlist_count": result["shortlist_count"],
        "matches": result["matches"],
    }
    if fetched:
        response["fetched"] = {
            "title": fetched.get("title"),
            "company": fetched.get("company"),
            "location": fetched.get("location"),
            "url": fetched.get("url"),
            "source": fetched.get("source"),
            "char_count": len(jd_text),
        }
    return response
