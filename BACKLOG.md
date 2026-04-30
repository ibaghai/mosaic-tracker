# Backlog

Items deferred from the active sprint. Each is small (S) and targeted; pick up when the larger pipeline / outreach-lifecycle work lands.

## C — Better empty-state UX in `ReachOutPanel`
When Apollo returns people but none match the archetype filters (recruiter / hiring_manager / recent_joiner), the UI shows a generic *"No drafts generated"* — confusing because it conflates "no people" with "people but wrong titles".

**Change**: surface the per-archetype reason. Examples:
- "Found 3 people at LatchBio in Apollo, but none have recruiter/talent titles."
- "Apollo has no employees indexed at this domain."
- "Apollo daily credit cap reached (1018/1000) — try again tomorrow."

**Files**: `dashboard/src/components/outreach/ReachOutPanel.tsx`, `api/app.py:_candidates_for_archetype` (return reason metadata).

## D — Founder-as-hiring-manager fallback for tiny startups
For companies with <10 people indexed in Apollo, the manager-level title search returns nothing because the founders ARE the managers. Should fall back to founder/CEO when manager-level titles return zero.

**Change**: in `_candidates_for_archetype` (hiring_manager branch), if the manager search returns 0 and Apollo's company size is small, retry with founder/co-founder/CEO titles.

**Files**: `api/app.py`, possibly `analysis/people.py` (need company-size signal).

## E — Auto-pin `apollo_organization_id` after first successful name-matched search
The schema column exists and the search uses it when set, but no code ever populates it. Should pin the org_id from the first Apollo response where the org name fuzzy-matches the tracker's company name.

**Change**: in `_real_people_search` (analysis/people.py), after results pass the name-match guard, if all returned people share the same `organization.id` and the company has no `apollo_organization_id` yet, write it back via a small `queries.set_company_apollo_org_id` helper.

**Files**: `analysis/people.py`, `db/queries.py` (new helper).

## F — UI warning when tracker company name disagrees with JD body
The JD parser now extracts `company_name_in_jd`. When it disagrees with the tracker name (e.g. "LatchBio" vs "Latch"), the outreach panel should surface a small warning so the user can fix data hygiene.

**Change**: render a small banner inside `ReachOutPanel` when `parsed_jd.company_name_in_jd` and `job.company_name` don't fuzzy-match. Link to a future "edit company" surface.

**Files**: `dashboard/src/components/outreach/ReachOutPanel.tsx`, `api/app.py` (expose `company_name_in_jd` in the response).

## G — Cache the JD parse per job
Today, every "Reach out" click re-parses the JD via Gemini. Same JD = same parse output. We should cache the parsed JD on the job_postings row (or in a small `parsed_jds` table keyed by job_id + prompt_version).

**Change**: store on first parse, return from cache on subsequent calls. Invalidate when `prompt_version` bumps.

**Files**: `api/app.py:outreach_generate`, possibly `db/models.py` (column or table) and `db/queries.py` (cache helpers).

---

## Other items noted in the audit but not yet broken out

- User accounts / multi-tenant (currently single-operator)
- Resume version library (multiple resumes per user)
- Editable parsed-resume profile (correct LLM misparses)
- Batch outreach (send to N dream jobs at once)
- Sidebar entries for `/radar`, `/analyst`, `/compare`
- URL-persisted filters on `/jobs` and `/companies`
- `/jobs` pagination beyond 500 rows
- Outreach template library / saved voices
- CRM-style person notes + tags
- must-have vs nice-to-have skill weighting in fit scoring
