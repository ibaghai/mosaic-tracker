"""Structured extraction from job descriptions via Groq.

Phase B's first step. Decouples *extraction* (verbatim from the JD, no inference)
from *inference* (downstream consumers use the parsed fields to make calls).
Hard rule in the prompt: do not infer reports-to from context — null if not stated.
"""

from __future__ import annotations

import json
import re
from typing import Optional

from analysis.llm import chat_json as _chat_json

PROMPT_VERSION = "jd-parse-v1"

# Top common titles → canonical (level, function). LLM fallback handles the tail.
_TITLE_ALIASES: dict[str, tuple[str, str]] = {
    "ceo": ("c_suite", "executive"),
    "cto": ("c_suite", "engineering"),
    "cpo": ("c_suite", "product"),
    "cfo": ("c_suite", "finance"),
    "coo": ("c_suite", "operations"),
    "cmo": ("c_suite", "marketing"),
    "vp engineering": ("vp", "engineering"),
    "vp of engineering": ("vp", "engineering"),
    "vp product": ("vp", "product"),
    "vp of product": ("vp", "product"),
    "vp design": ("vp", "design"),
    "vp of design": ("vp", "design"),
    "vp sales": ("vp", "sales"),
    "vp of sales": ("vp", "sales"),
    "vp marketing": ("vp", "marketing"),
    "vp of marketing": ("vp", "marketing"),
    "head of engineering": ("head", "engineering"),
    "head of product": ("head", "product"),
    "head of design": ("head", "design"),
    "head of growth": ("head", "growth"),
    "director of engineering": ("director", "engineering"),
    "director of product": ("director", "product"),
    "director of design": ("director", "design"),
    "director of marketing": ("director", "marketing"),
    "engineering manager": ("manager", "engineering"),
    "product manager": ("manager", "product"),
    "senior engineering manager": ("senior", "engineering"),
    "principal engineer": ("principal", "engineering"),
    "staff engineer": ("staff", "engineering"),
    "senior software engineer": ("senior", "engineering"),
    "software engineer": ("mid", "engineering"),
    "recruiter": ("manager", "human_resources"),
    "technical recruiter": ("manager", "human_resources"),
    "talent partner": ("manager", "human_resources"),
}


# ── Public API ────────────────────────────────────────────────────────────────

def parse_jd(jd_text: str, *, job_title: Optional[str] = None) -> dict:
    """Parse a job description into a structured dict. Hits Groq once.

    Returns a dict with this shape (all fields present, may be null/[]/{}):

      {
        "role_title": str,
        "role_title_normalized": str,
        "company_name_in_jd": str | null,            # company name as stated in JD body
        "level": "intern|junior|mid|senior|staff|principal|manager|director|head|vp|c_suite",
        "function": "engineering|product|design|sales|marketing|operations|...",
        "sub_function": str | null,
        "reports_to_phrase": str | null,             # verbatim, null if absent
        "reports_to_target": {                       # null if reports_to_phrase null
            "title": str, "team_or_org": str|null,
            "level": str|null, "function": str|null,
        } | null,
        "team_or_org": str | null,
        "geography": {"type": "remote|hybrid|onsite", "locations": [str]},
        "stack_signals": [str],
        "scope_signals": [str],
        "key_responsibilities": [str],
        "must_have_skills": [str],
        "nice_to_have_skills": [str],
      }
    """
    if not jd_text or not jd_text.strip():
        raise ValueError("parse_jd: jd_text is empty")

    system_prompt = (
        "You extract structured job-posting fields from a JD. Output strict JSON only. "
        "CRITICAL RULES:\n"
        "1. Extract ONLY what the JD explicitly states. Do NOT infer or guess.\n"
        "2. For reports_to_phrase: copy the verbatim phrase if present (e.g. \"reports to the VP of Engineering\"). "
        "   If the JD never explicitly states who this role reports to, return null. "
        "   Phrases like 'work closely with X' or 'partner with X' are NOT reports-to.\n"
        "3. For reports_to_target: parse the phrase you extracted. Null if reports_to_phrase is null. "
        "   Do NOT fall back to inference (e.g., 'Director probably reports to VP') in this step.\n"
        "4. team_or_org is the team this role JOINS, separate from reports-to (e.g. 'Platform team').\n"
        "5. level must be one of: intern, junior, mid, senior, staff, principal, manager, director, head, vp, c_suite.\n"
        "6. function should be a lowercase domain like engineering, product, design, sales, marketing, operations, "
        "finance, human_resources, customer_success, etc.\n"
        "7. company_name_in_jd: the most prominent company name in the JD body, exactly as written "
        "(e.g. 'LatchBio', 'Brex', 'OpenAI'). Null if not stated. This is the candidate's source of "
        "truth for who the role is at — used to detect when our tracker's company-name field is stale.\n"
    )

    user_payload = {
        "task": "parse_jd",
        "title_hint": job_title,
        "jd_text": jd_text[:12000],  # cap to keep prompt size bounded
        "schema": {
            "role_title": "string",
            "role_title_normalized": "string (lowercase, snake_case)",
            "company_name_in_jd": "string (verbatim) or null",
            "level": "intern|junior|mid|senior|staff|principal|manager|director|head|vp|c_suite",
            "function": "string",
            "sub_function": "string or null",
            "reports_to_phrase": "string (verbatim) or null",
            "reports_to_target": {
                "title": "string",
                "team_or_org": "string or null",
                "level": "string or null",
                "function": "string or null",
            },
            "team_or_org": "string or null",
            "geography": {
                "type": "remote|hybrid|onsite",
                "locations": ["string"],
            },
            "stack_signals": ["string"],
            "scope_signals": ["string"],
            "key_responsibilities": ["string (3-5 items)"],
            "must_have_skills": ["string"],
            "nice_to_have_skills": ["string"],
        },
    }

    data = _chat_json(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_payload)},
        ],
        temperature=0.0,
    )
    return _coerce_parse(data)


def normalize_title(title: str) -> Optional[tuple[str, str]]:
    """Cheap title normalization. Returns (level, function) or None for tail titles.

    Matches a hand-curated alias table. The LLM in `parse_jd` handles tail cases
    via the level + function fields.
    """
    if not title:
        return None
    t = re.sub(r"[^a-z0-9 ]", "", title.lower()).strip()
    t = re.sub(r"\s+", " ", t)
    if t in _TITLE_ALIASES:
        return _TITLE_ALIASES[t]
    # Fuzzy: try removing common filler words
    for filler in ["of the", "of", "the"]:
        candidate = t.replace(f" {filler} ", " ").strip()
        if candidate in _TITLE_ALIASES:
            return _TITLE_ALIASES[candidate]
    return None


# ── Internals ─────────────────────────────────────────────────────────────────

def _coerce_parse(raw: dict) -> dict:
    """Ensure all expected keys are present with sane defaults."""
    out = dict(raw or {})
    out.setdefault("role_title", None)
    out.setdefault("role_title_normalized", None)
    out.setdefault("company_name_in_jd", None)
    out.setdefault("level", None)
    out.setdefault("function", None)
    out.setdefault("sub_function", None)
    out.setdefault("reports_to_phrase", None)
    out.setdefault("reports_to_target", None)
    out.setdefault("team_or_org", None)
    geo = out.get("geography") or {}
    out["geography"] = {
        "type": geo.get("type"),
        "locations": _ensure_list(geo.get("locations")),
    }
    out["stack_signals"] = _ensure_list(out.get("stack_signals"))
    out["scope_signals"] = _ensure_list(out.get("scope_signals"))
    out["key_responsibilities"] = _ensure_list(out.get("key_responsibilities"))
    out["must_have_skills"] = _ensure_list(out.get("must_have_skills"))
    out["nice_to_have_skills"] = _ensure_list(out.get("nice_to_have_skills"))
    return out


def _ensure_list(v) -> list:
    if v is None:
        return []
    if isinstance(v, list):
        return [str(x) for x in v if x]
    return [str(v)]
