"""
FastAPI REST API — thin wrapper over db/queries.py
Run with: uvicorn api.app:app --reload --port 8000
"""

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import os
from pydantic import BaseModel, Field

from db.models import init_db
from db import queries
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
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()
queries.scrub_resume_profile_pii()
queries.scrub_resume_fit_pii()


class SavedViewCreate(BaseModel):
    name: str
    view_type: str
    filters: dict = Field(default_factory=dict)
    persona: Optional[str] = None


class WatchlistCreate(BaseModel):
    name: str
    persona: Optional[str] = None


class WatchlistItemCreate(BaseModel):
    item_type: str
    item_value: str
    company_id: Optional[int] = None


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


# ── Saved Views ───────────────────────────────────────────────────────────────

@app.get("/api/saved-views")
def saved_views(view_type: Optional[str] = None):
    return queries.get_saved_views(view_type=view_type)


@app.post("/api/saved-views")
def create_saved_view(payload: SavedViewCreate):
    view_type = payload.view_type.strip().lower()
    if view_type not in {"jobs", "companies"}:
        raise HTTPException(status_code=400, detail="view_type must be jobs or companies")
    if not payload.name.strip():
        raise HTTPException(status_code=400, detail="name is required")
    return queries.create_saved_view(
        name=payload.name,
        view_type=view_type,
        filters=payload.filters,
        persona=payload.persona,
    )


@app.post("/api/saved-views/{view_id}/viewed")
def mark_saved_view_viewed(view_id: int):
    row = queries.mark_saved_view_viewed(view_id)
    if not row:
        raise HTTPException(status_code=404, detail="Saved view not found")
    return row


@app.delete("/api/saved-views/{view_id}")
def delete_saved_view(view_id: int):
    deleted = queries.delete_saved_view(view_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Saved view not found")
    return {"ok": True}


# ── Watchlists ────────────────────────────────────────────────────────────────

@app.get("/api/watchlists")
def watchlists(persona: Optional[str] = None):
    return queries.get_watchlists(persona=persona)


@app.post("/api/watchlists")
def create_watchlist(payload: WatchlistCreate):
    if not payload.name.strip():
        raise HTTPException(status_code=400, detail="name is required")
    return queries.create_watchlist(name=payload.name, persona=payload.persona)


@app.delete("/api/watchlists/{watchlist_id}")
def delete_watchlist(watchlist_id: int):
    deleted = queries.delete_watchlist(watchlist_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Watchlist not found")
    return {"ok": True}


@app.get("/api/watchlists/{watchlist_id}/items")
def watchlist_items(watchlist_id: int):
    return queries.get_watchlist_items(watchlist_id)


@app.post("/api/watchlists/{watchlist_id}/items")
def add_watchlist_item(watchlist_id: int, payload: WatchlistItemCreate):
    try:
        return queries.add_watchlist_item(
            watchlist_id=watchlist_id,
            item_type=payload.item_type,
            item_value=payload.item_value,
            company_id=payload.company_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.delete("/api/watchlists/{watchlist_id}/items")
def remove_watchlist_item(watchlist_id: int, item_type: str, item_value: str):
    deleted = queries.remove_watchlist_item(
        watchlist_id=watchlist_id,
        item_type=item_type,
        item_value=item_value,
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Watchlist item not found")
    return {"ok": True}


# ── Analyst ───────────────────────────────────────────────────────────────────

@app.get("/api/analyst/cohort")
def analyst_cohort(
    sector: Optional[str] = None,
    funding_round: Optional[str] = None,
    company_type: Optional[str] = None,
    ats_type: Optional[str] = None,
    weeks: int = 12,
):
    return queries.get_analyst_cohort_metrics(
        sector=sector,
        funding_round=funding_round,
        company_type=company_type,
        ats_type=ats_type,
        weeks=max(4, min(weeks, 26)),
    )


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
