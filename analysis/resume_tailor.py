"""Resume tailoring for a specific job, with strict no-fabrication guardrails.

Phase C's first module. Three modes the LLM is allowed to operate in:

  1. REORDER  — promote items already in the resume that match the JD.
  2. EMPHASIZE — bold/expand existing bullets that align; demote others.
  3. REPHRASE — rewrite existing bullets using JD vocabulary, keeping facts.

Hard rule: the LLM may NOT add experience, claims, employers, dates, or skills
that aren't in the source resume. The diff_summary surfaces exactly what changed
so the user can verify nothing was fabricated.
"""

from __future__ import annotations

import json
import re
from typing import Optional

from analysis.llm import chat_json as _chat_json, model_name as _model, provider_name

PROMPT_VERSION = "tailor-v1"


def tailor_resume(
    resume_text: str,
    *,
    job: dict,
    parsed_jd: Optional[dict] = None,
) -> dict:
    """Produce a JD-tailored variant of the resume.

    Returns:
        {
          "tailored_text": str,
          "diff_summary": {
            "sections_changed": [str],
            "keywords_added": [str],
            "bullets_emphasized": [str],
            "bullets_rephrased": [{"before": str, "after": str}],
            "warnings": [str],            # raised if the LLM tries anything sketchy
          },
          "provider": "groq",
          "model": str,
          "prompt_version": str,
        }
    """
    if not resume_text or not resume_text.strip():
        raise ValueError("tailor_resume: resume_text is empty")
    if not job or not job.get("title"):
        raise ValueError("tailor_resume: job dict missing title")

    system_prompt = (
        "You produce a JD-tailored variant of a resume. Output strict JSON only.\n\n"
        "ABSOLUTE RULES — violating any of these is a critical bug:\n"
        "1. NEVER add experience, employers, job titles, dates, education, or "
        "certifications that don't appear in the source resume. The tailored "
        "resume must claim ZERO new facts.\n"
        "2. NEVER add specific quantitative claims (revenue numbers, team sizes, "
        "user counts, percentage improvements) that aren't in the source.\n"
        "3. NEVER add skills the resume doesn't mention. You may rephrase a "
        "skill to match JD vocabulary IFF the rephrasing is a true synonym "
        "(e.g., 'JS' → 'JavaScript'; 'Postgres' → 'PostgreSQL'). "
        "Adding a skill that isn't there at all is forbidden.\n"
        "4. You MAY: reorder sections to put JD-relevant content earlier; "
        "promote bullets that match JD priorities; rephrase existing bullets "
        "using JD vocabulary; demote or shorten irrelevant bullets.\n"
        "5. Preserve the resume's overall structure (sections, bullets) and "
        "first-person voice (or third-person if the source uses it).\n"
        "6. If you make ANY change that could be perceived as fabrication, "
        "include a clear note in diff_summary.warnings.\n"
    )

    user_payload = {
        "task": "tailor_resume",
        "source_resume": resume_text[:14000],
        "target_job": _job_card(job, parsed_jd),
        "output_schema": {
            "tailored_text": "string (full tailored resume body, plain text)",
            "diff_summary": {
                "sections_changed": ["string"],
                "keywords_added": ["string (only true synonyms of existing skills)"],
                "bullets_emphasized": ["string"],
                "bullets_rephrased": [{"before": "string", "after": "string"}],
                "warnings": ["string"],
            },
        },
    }

    data = _chat_json(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_payload)},
        ],
        temperature=0.2,
    )

    out = {
        "tailored_text": (data.get("tailored_text") or "").strip(),
        "diff_summary": _coerce_diff(data.get("diff_summary")),
        "provider": provider_name(),
        "model": _model(),
        "prompt_version": PROMPT_VERSION,
    }

    # Defense-in-depth: scan tailored output for tokens not in the source.
    # Catches the LLM hallucinating an employer name or framework.
    suspect = _detect_fabrications(resume_text, out["tailored_text"])
    if suspect:
        out["diff_summary"]["warnings"].extend(
            f"Possible fabrication — '{token}' appears in tailored output but not in source resume"
            for token in suspect[:5]
        )

    return out


def _job_card(job: dict, parsed: Optional[dict]) -> dict:
    body = (job.get("description") or "")[:3500]
    card = {
        "title": job.get("title"),
        "company_name": job.get("company_name"),
        "description_excerpt": body,
    }
    if parsed:
        card["parsed"] = {
            "level": parsed.get("level"),
            "function": parsed.get("function"),
            "must_have_skills": (parsed.get("must_have_skills") or [])[:15],
            "key_responsibilities": (parsed.get("key_responsibilities") or [])[:6],
            "stack_signals": (parsed.get("stack_signals") or [])[:15],
        }
    return card


def _coerce_diff(raw) -> dict:
    raw = raw or {}
    return {
        "sections_changed": _ensure_list(raw.get("sections_changed")),
        "keywords_added": _ensure_list(raw.get("keywords_added")),
        "bullets_emphasized": _ensure_list(raw.get("bullets_emphasized")),
        "bullets_rephrased": _ensure_pair_list(raw.get("bullets_rephrased")),
        "warnings": _ensure_list(raw.get("warnings")),
    }


def _ensure_list(v) -> list:
    if v is None:
        return []
    if isinstance(v, list):
        return [str(x) for x in v if x]
    return [str(v)]


def _ensure_pair_list(v) -> list:
    if not isinstance(v, list):
        return []
    out = []
    for entry in v:
        if isinstance(entry, dict) and entry.get("before") and entry.get("after"):
            out.append({"before": str(entry["before"]), "after": str(entry["after"])})
    return out


# ── Fabrication detector ─────────────────────────────────────────────────────

# Match Capitalized phrases connected only by spaces/tabs/hyphens — never
# across newlines or punctuation, which used to produce false positives like
# "GPA: 3.8\nFamiliar with..." → fake match "GPA Familiar".
_PROPER_NOUN_RE = re.compile(r"\b([A-Z][a-zA-Z0-9]+(?:[ \t\-][A-Z][a-zA-Z0-9]+){0,2})\b")
_NUMBER_CLAIM_RE = re.compile(r"\b(\d+(?:\.\d+)?[KMB]?\+?\s*(?:%|users|customers|revenue|MRR|ARR|engineers|reports))", re.I)

# Words that are common in resumes but aren't proper nouns. Each is checked
# *individually* against tokens, so "WA Bachelor" lookup will match because
# both "WA" and "Bachelor" are listed.
_COMMON_RESUME_TOKENS = {
    # English action verbs / pronouns
    "i", "we", "led", "built", "designed", "developed", "created", "managed",
    "delivered", "scaled", "drove", "owned", "launched", "shipped", "engineered",
    "implemented", "architected", "mentored", "collaborated", "partnered",
    "reduced", "increased", "improved", "optimized", "refactored", "ran",
    # Common resume nouns
    "senior", "staff", "principal", "director", "manager", "engineer", "lead",
    "software", "product", "engineering", "design", "marketing", "sales",
    "bachelor", "master", "phd", "doctorate", "associate", "diploma",
    # Resume-section acronyms
    "gpa", "mba", "bs", "ms", "ba", "ma", "ph", "cv", "it", "ai", "ml", "ui",
    "ux", "api", "sdk", "saas", "html", "css", "ios",
    # US state abbreviations + common geography prefixes
    "ny", "ca", "wa", "tx", "ma", "il", "fl", "co", "wa", "or", "az", "nj",
    "us", "usa", "uk", "eu", "emea", "apac", "latam",
    # Tech (these are also covered by case-insensitive .lower() match against source)
    "python", "javascript", "typescript", "react", "next", "node", "postgresql",
    "aws", "gcp", "azure", "docker", "kubernetes", "linux", "git",
    # Months
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
    "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "sept", "oct", "nov", "dec",
}


def _detect_fabrications(source: str, tailored: str) -> list[str]:
    """Return proper nouns + specific numeric claims in the tailored output
    that don't appear in the source. False-positive prone — surfaced as
    *warnings*, not blockers.
    """
    if not tailored:
        return []
    source_lower = source.lower()
    suspect = []

    for match in _PROPER_NOUN_RE.findall(tailored):
        if match.lower() in source_lower:
            continue
        # Drop matches where every token is a known common-English / acronym /
        # geo word. Removes most regex-noise false positives.
        tokens = re.split(r"[ \t\-]+", match)
        if all(t.lower() in _COMMON_RESUME_TOKENS for t in tokens):
            continue
        # Drop matches where every token (longer than 3 chars) appears in source.
        # Catches cases where the LLM rephrased existing tokens but the regex
        # spanned into a fresh noise-word.
        substantial = [t for t in tokens if len(t) > 3]
        if substantial and all(t.lower() in source_lower for t in substantial):
            continue
        suspect.append(match)

    for match in _NUMBER_CLAIM_RE.findall(tailored):
        if match.lower() not in source_lower:
            suspect.append(match)

    # Dedupe, preserve order
    seen, out = set(), []
    for s in suspect:
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


