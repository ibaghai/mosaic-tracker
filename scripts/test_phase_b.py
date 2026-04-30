"""End-to-end Phase B smoke test.

For one real job in the v1 DB:
  1. Parse the JD via Groq → structured fields
  2. Search Apollo for HM candidates (by reports-to-target title)
  3. Run hand-tuned HM inference scoring
  4. Enrich the top HM candidate (1 reveal credit)
  5. Generate one outreach draft for the enriched candidate
  6. Print everything + final Apollo usage

Usage:
    python scripts/test_phase_b.py            # picks a job automatically
    python scripts/test_phase_b.py --job 12345 # specific job id
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db.models import init_db, get_connection  # noqa: E402
from analysis import people as people_mod  # noqa: E402
from analysis import jd_parse, outreach  # noqa: E402


def _pick_job(job_id: int | None) -> dict:
    init_db()
    conn = get_connection()
    try:
        if job_id:
            sql = """
                SELECT jp.id, jp.title, jp.description, jp.url,
                       jp.company_id, c.name AS company_name, c.website
                FROM job_postings jp JOIN companies c ON c.id = jp.company_id
                WHERE jp.id = ?
            """
            row = conn.execute(sql, (job_id,)).fetchone()
        else:
            row = conn.execute("""
                SELECT jp.id, jp.title, jp.description, jp.url,
                       jp.company_id, c.name AS company_name, c.website
                FROM job_postings jp JOIN companies c ON c.id = jp.company_id
                WHERE jp.is_active = 1
                  AND c.website IS NOT NULL
                  AND length(jp.description) > 800
                ORDER BY jp.first_seen_at DESC
                LIMIT 1
            """).fetchone()
        if not row:
            raise SystemExit("no suitable job found in v1 DB")
        return dict(row)
    finally:
        conn.close()


def _print_section(title: str) -> None:
    print(f"\n{'─' * 70}\n {title}\n{'─' * 70}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job", type=int, default=None)
    parser.add_argument("--enrich-top", type=int, default=1,
                        help="how many HM candidates to enrich (1 credit each)")
    args = parser.parse_args()

    job = _pick_job(args.job)
    print(f"Job: #{job['id']}  {job['title']}  @  {job['company_name']}")

    _print_section("1. Parse JD via Groq")
    parsed = jd_parse.parse_jd(job["description"], job_title=job["title"])
    print(json.dumps({
        "role_title": parsed.get("role_title"),
        "level": parsed.get("level"),
        "function": parsed.get("function"),
        "reports_to_phrase": parsed.get("reports_to_phrase"),
        "reports_to_target": parsed.get("reports_to_target"),
        "team_or_org": parsed.get("team_or_org"),
        "must_have_skills": parsed.get("must_have_skills")[:6],
    }, indent=2))

    _print_section("2. Search Apollo for HM candidates")
    target = parsed.get("reports_to_target") or {}
    # Build a tighter title filter from JD function so we don't get every senior person.
    function = (target.get("function") or parsed.get("function") or "").lower()
    target_level = (target.get("level") or "").lower()
    if not target_level:
        # Infer one tier up from the role's own level.
        role_level = (parsed.get("level") or "").lower()
        target_level = {
            "intern": "manager", "junior": "manager", "mid": "manager",
            "senior": "manager", "staff": "manager", "principal": "director",
            "manager": "director", "director": "vp", "head": "vp", "vp": "c_suite",
        }.get(role_level, "")
    seniorities = [target_level] if target_level else ["vp", "director", "head"]

    # Title filter: combine seniority + function for a sharper match
    title_terms = []
    if function:
        if target_level == "vp":
            title_terms = [f"VP {function}", f"VP of {function}", f"Vice President {function}"]
        elif target_level == "director":
            title_terms = [f"Director {function}", f"Director of {function}", f"Head of {function}"]
        elif target_level == "manager":
            title_terms = [f"{function} manager", f"Senior {function} manager"]

    candidates = people_mod.find_people_at_company(
        job["company_id"],
        titles=title_terms or None,
        seniorities=seniorities,
        archetype="hiring_manager",
        limit=10,
        persist=True,
    )
    print(f"Apollo: seniorities={seniorities} titles={title_terms} → {len(candidates)} candidates")
    for p in candidates[:5]:
        print(f"  • {p['name']} — {p.get('title')}")

    _print_section("3. Score with hand-tuned HM inference")
    ranked = people_mod.infer_hiring_manager(parsed, candidates)
    for p in ranked[:5]:
        print(f"  [{p['hm_score']:.2f}] {p['name']} — {p.get('title')}")
        for ev in p["hm_evidence"][:3]:
            print(f"        • {ev}")

    if not ranked:
        print("\nNo candidates ranked. Stopping before enrichment.")
        return

    _print_section(f"4. Enrich top {args.enrich_top} candidate(s)")
    enriched = []
    for cand in ranked[:args.enrich_top]:
        full = people_mod.enrich_person(cand, reveal_personal_emails=False)
        full["hm_score"] = cand["hm_score"]
        full["hm_evidence"] = cand["hm_evidence"]
        full["archetype"] = full.get("archetype") or "hiring_manager"
        enriched.append(full)
        print(f"  ✓ {full['name']} — {full.get('title')}")
        print(f"    linkedin: {full.get('linkedin_url')}")
        print(f"    email:    {full.get('email')} ({full.get('email_status')})")

    _print_section("5. Generate outreach for top enriched candidate")
    target_person = enriched[0]
    asker_profile = {
        "headline": "Senior product/engineering leader",
        "target_roles": ["VP Engineering", "Director of Engineering", "Head of Product"],
        "role_families": ["engineering_leadership", "product_leadership"],
        "seniority": "senior",
        "skills": ["Python", "FastAPI", "Postgres", "AWS", "Next.js", "TypeScript"],
        "domains": ["fintech", "developer_tools"],
        "strengths": ["0-1 product launch", "team building"],
    }
    draft = outreach.generate_outreach(
        job=job,
        person=target_person,
        asker_profile=asker_profile,
        archetype=target_person["archetype"],
        parsed_jd=parsed,
    )
    print(f"\nSubject: {draft['subject']}")
    print(f"\n{draft['message']}")
    print(f"\nRationale: {json.dumps(draft['rationale'], indent=2)}")

    _print_section("Apollo usage summary")
    print(json.dumps(people_mod.usage_status()["used"], indent=2))


if __name__ == "__main__":
    main()
