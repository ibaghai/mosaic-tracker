"""Outreach draft generator.

Phase B's third step. Composes a personalized cold-outreach message per
(job, person, asker_resume_profile, archetype) tuple. Hard rule in the prompt:
do not invent shared history. Only reference real artifacts present in the
input (the person's bio, their actual title, the JD, the asker's resume).
"""

from __future__ import annotations

import json
from typing import Optional

from analysis.llm import chat_json as _chat_json, model_name as _model, provider_name

PROMPT_VERSION = "outreach-v1"


# Tone presets per archetype. Subject + body style differ meaningfully.
_TONE_PRESETS = {
    "recruiter": {
        "tone": "professional",
        "directive": (
            "Direct and concise. Treat them as a gatekeeper who reads dozens of "
            "messages a day. Lead with the role and your fit; don't ask for time "
            "as the first move."
        ),
    },
    "hiring_manager": {
        "tone": "direct_thoughtful",
        "directive": (
            "Direct but human. They're a peer you're appealing to. Lead with one "
            "specific thing about THEIR work or team that drew you in (only if "
            "the bio mentions it; otherwise lead with one specific thing about the "
            "company's product/mission that maps to your experience). End with a "
            "concrete, low-cost ask (15-min chat or a question they could answer "
            "in 2 lines)."
        ),
    },
    "recent_joiner": {
        "tone": "warm_collegial",
        "directive": (
            "Warm and curious. They have no gatekeeping power and the lowest "
            "downside to responding. Ask about their experience joining the team, "
            "not the open req. Implicitly: you're hoping they'll mention you "
            "internally if they like you. End with: 'Open to a quick chat about "
            "what the team's like?' rather than asking about the role itself."
        ),
    },
    "other": {
        "tone": "professional",
        "directive": "Direct, brief, focused on shared context.",
    },
}


def generate_outreach(
    *,
    job: dict,
    person: dict,
    asker_profile: dict,
    archetype: Optional[str] = None,
    parsed_jd: Optional[dict] = None,
) -> dict:
    """Generate a personalized cold-outreach draft.

    Inputs:
        job: row from job_postings (must have title, description, company name).
        person: row from people (Apollo-enriched preferred — has full name, bio).
        asker_profile: parsed resume profile (headline, skills, target_roles, etc.).
        archetype: 'recruiter' | 'hiring_manager' | 'recent_joiner' | 'other'.
        parsed_jd: optional output of analysis.jd_parse.parse_jd, for richer grounding.

    Returns:
        {
          "subject": str,
          "message": str,
          "rationale": {
              "person_artifacts_referenced": [str],   # what real things we cited
              "company_artifacts_referenced": [str],
              "matched_skills": [str],
          },
          "tone": str,
          "provider": "groq",
          "model": str,
          "prompt_version": str,
        }
    """
    archetype = archetype or person.get("archetype") or "other"
    preset = _TONE_PRESETS.get(archetype, _TONE_PRESETS["other"])

    person_card = _person_card(person)
    # Prefer the company name as the JD writes it (e.g. "LatchBio") over the
    # tracker's stored name (e.g. "Latch") — the JD body is the candidate's
    # source of truth for who the role is at.
    jd_company = (parsed_jd or {}).get("company_name_in_jd")
    company_name = jd_company or job.get("company_name") or job.get("company") or ""
    asker_card = _asker_card(asker_profile)
    jd_card = _jd_card(job, parsed_jd)

    system_prompt = (
        "You write thoughtful, *specific*, non-sloppy cold-outreach messages for a job seeker. "
        "Output strict JSON only.\n\n"
        "ABSOLUTE RULES:\n"
        "1. Only reference facts present in the input. Do NOT invent shared history, "
        "shared schools, mutual connections, talks the recipient gave, books they wrote, "
        "or anything that isn't explicitly in the person's bio or the company's JD.\n"
        "2. If the person's bio is sparse and the JD is generic, write a generically-honest "
        "message — DO NOT fabricate specificity to compensate. A short, honest message "
        "outperforms a fake-personal one.\n"
        "3. Subject line: under 60 characters. Specific to the role or person — never "
        "'Quick question' or 'Reaching out'.\n"
        "4. Message body: 80-150 words. No bullet points. No flattery. No '[Insert detail]' "
        "placeholders — if you don't have a detail, leave it out.\n"
        "5. End with one concrete ask appropriate to the recipient.\n"
        "6. Sign with '[Your name]' so the user fills it in.\n"
        "7. NEVER paraphrase or summarize the JD back to the recipient — they wrote it or work there. "
        "Reference the role by name once; spend the body on YOUR fit and your ask.\n"
        "8. NEVER comment on or compliment the recipient's resume / background / years of experience. "
        "Don't tell them what their job is or what they're good at. The message is from you to them, "
        "not a third-party endorsement of them.\n"
        "9. The first sentence should be about you (your situation / fit / why you're writing), "
        "not about the company or the recipient.\n\n"
        f"TONE GUIDANCE for archetype '{archetype}': {preset['directive']}"
    )

    user_payload = {
        "task": "generate_outreach",
        "archetype": archetype,
        "tone_preset": preset["tone"],
        "company_name": company_name,
        "recipient": person_card,
        "asker_resume_profile": asker_card,
        "job": jd_card,
        "output_schema": {
            "subject": "string (≤60 chars)",
            "message": "string (80-150 words)",
            "rationale": {
                "person_artifacts_referenced": ["string"],
                "company_artifacts_referenced": ["string"],
                "matched_skills": ["string"],
            },
        },
    }

    data = _chat_json(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_payload)},
        ],
        temperature=0.4,
    )

    return {
        "subject": (data.get("subject") or "").strip(),
        "message": (data.get("message") or "").strip(),
        "rationale": data.get("rationale") or {},
        "tone": preset["tone"],
        "archetype": archetype,
        "provider": provider_name(),
        "model": _model(),
        "prompt_version": PROMPT_VERSION,
    }


# ── Card builders (just slice the input down to what the LLM needs) ───────────

def _person_card(person: dict) -> dict:
    return {
        "name": person.get("name"),
        "title": person.get("title"),
        "linkedin_url": person.get("linkedin_url"),
        "bio": person.get("bio_summary"),
        "seniority": person.get("seniority"),
        "tenure_start_date": person.get("tenure_start_date"),
    }


def _asker_card(profile: dict) -> dict:
    return {
        "headline": profile.get("headline"),
        "target_roles": profile.get("target_roles") or [],
        "role_families": profile.get("role_families") or [],
        "seniority": profile.get("seniority"),
        "skills": (profile.get("skills") or [])[:40],
        "domains": profile.get("domains") or [],
        "strengths": (profile.get("strengths") or [])[:6],
    }


def _jd_card(job: dict, parsed: Optional[dict]) -> dict:
    body = (job.get("description") or "")[:3000]
    card = {
        "title": job.get("title"),
        "url": job.get("url"),
        "description_excerpt": body,
    }
    if parsed:
        card["parsed"] = {
            "level": parsed.get("level"),
            "function": parsed.get("function"),
            "team_or_org": parsed.get("team_or_org"),
            "key_responsibilities": (parsed.get("key_responsibilities") or [])[:5],
            "must_have_skills": (parsed.get("must_have_skills") or [])[:10],
        }
    return card


