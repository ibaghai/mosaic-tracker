# Contact search & enrichment — backend guide

How the v1 job-search assistant goes from a job posting to **named, contactable
humans** at the hiring company, with an honest account of what we know about
each person and how we know it.

---

## TL;DR

For any job in the DB, when you click "Reach out":

1. We parse the JD to extract `level`, `function`, and `reports_to_target` ([analysis/jd_parse.py](../analysis/jd_parse.py))
2. We hit Apollo's **search** API to pull a candidate pool of employees at the company ([analysis/people.py](../analysis/people.py): `find_people_at_company`)
3. For each archetype (recruiter, hiring_manager, recent_joiner) we filter + rank the pool ([analysis/people.py](../analysis/people.py): `infer_hiring_manager`, [api/app.py](../api/app.py): `_candidates_for_archetype`)
4. We enrich the top of each list via Apollo's **match** API to reveal full identity + email ([analysis/people.py](../analysis/people.py): `enrich_person`)
5. Everything is persisted to local SQLite tables for replay, caching, and audit

**What we end up knowing per person:** name, current title, LinkedIn URL, work email + verification status, seniority, departments, tenure start date, employment history snippets, photo URL, organization metadata.

**What we don't know without enrichment:** any of the above (search returns redacted fields).

---

## The pipeline, end to end

When the dashboard calls `POST /api/outreach/jobs/{job_id}/generate`, here's what runs:

```
┌─────────────────────────────────────────────────────────────────────────┐
│ 1. Load job + company from DB                                           │
│    └─ companies.website → drives Apollo's domain filter                 │
│       (fallback: guess "<companyname>.com" if website is null)          │
└─────────────────────────────────────────────────────────────────────────┘
                                 ↓
┌─────────────────────────────────────────────────────────────────────────┐
│ 2. Parse JD via Groq/OpenRouter LLM                                     │
│    Extract: role_title, level, function, sub_function,                  │
│             reports_to_phrase (verbatim, null if absent),               │
│             reports_to_target { title, team_or_org, level, function },  │
│             team_or_org, must_have_skills                               │
│    Hard rule in prompt: only extract what JD literally says.            │
│    No inference at this step.                                           │
└─────────────────────────────────────────────────────────────────────────┘
                                 ↓
┌─────────────────────────────────────────────────────────────────────────┐
│ 3. For each archetype: search Apollo OR pull from cache                 │
│    Cache: get_people_for_company(company_id, archetype, fresh=30 days)  │
│           If we already have ≥1 person at this company tagged with      │
│           this archetype within 30 days, use cache (zero credits).      │
│    Search: POST mixed_people/api_search                                 │
│           Body: q_organization_domains_list + person_titles +           │
│                 person_seniorities                                      │
│           Returns: 1-25 redacted-ish profiles (~1 credit per call)      │
└─────────────────────────────────────────────────────────────────────────┘
                                 ↓
┌─────────────────────────────────────────────────────────────────────────┐
│ 4. (HM only) Score the candidate pool with deterministic heuristics     │
│    infer_hiring_manager(parsed_jd, candidates) →                        │
│       per candidate: hm_score [0,1] + hm_evidence [strings]             │
│    No LLM, no Apollo calls — pure scoring on already-fetched data.      │
└─────────────────────────────────────────────────────────────────────────┘
                                 ↓
┌─────────────────────────────────────────────────────────────────────────┐
│ 5. Enrich top N per archetype                                           │
│    POST people/match with apollo_id                                     │
│    Returns: full name, linkedin_url, email + email_status,              │
│             headline, departments, employment history, seniority        │
│    Cost: ~1 credit per reveal. Caller controls N (default 1).           │
└─────────────────────────────────────────────────────────────────────────┘
                                 ↓
┌─────────────────────────────────────────────────────────────────────────┐
│ 6. Persist to DB + return                                               │
│    upsert_person (people table, dedupe on apollo_id)                    │
│    insert_outreach_draft (outreach_drafts, after gen)                   │
│    log_apollo_call (apollo_api_calls, every call inc. failures)         │
└─────────────────────────────────────────────────────────────────────────┘
```

All five steps run inside a single FastAPI request. Total ≈ 6-12 Apollo
credits per click (1-3 search calls + 1-3 enrich calls), plus 1-5 LLM calls.

---

## Data sources — Apollo's two endpoints

There's a deliberate split between *find* and *reveal*, with very different
pricing and data shapes.

| Endpoint | What it does | Returns | Credit cost |
|---|---|---|---|
| `POST /api/v1/mixed_people/api_search` | Find people matching filters at a company | Up to 25 partially-redacted profiles | ~1 per call |
| `POST /api/v1/people/match` | Enrich one known person to full record | Full identity + email | ~1 per reveal |

### What `mixed_people/api_search` returns

```json
{
  "people": [
    {
      "id": "67abc123def...",          // → apollo_id (stable, used for enrichment)
      "first_name": "Adam",            // first name only ✓
      "last_name": null,               // last name redacted ✗
      "name": "Adam",                  // sometimes null until enrichment
      "title": "VP Product Management",// usually present ✓
      "headline": "...",               // sometimes truncated
      "linkedin_url": null,            // redacted ✗
      "email": null,                   // redacted ✗
      "email_status": null,            // redacted ✗
      "departments": ["product"],      // present ✓
      "seniority": "vp",               // present ✓
      "organization": {                // present ✓
        "name": "Contentful",
        "primary_domain": "contentful.com"
      },
      "employment_history": [...]      // sometimes present, sparse
    }
  ]
}
```

Key implication: from search alone, **you know titles + first names + departments**. You do *not* know last names, emails, or LinkedIn URLs.

### What `people/match` returns (after enrichment)

```json
{
  "person": {
    "id": "67abc123def...",            // matches the search result
    "name": "Adam Weinstein",          // full name ✓
    "title": "Vice President, Product Management",
    "linkedin_url": "linkedin.com/in/ajweinstein",  // ✓
    "email": "adam.weinstein@contentful.com",       // ✓
    "email_status": "verified",        // verified | guessed | unavailable | mock
    "phone_numbers": [...],            // optional, costs more
    "headline": "...",
    "seniority": "vp",
    "departments": ["product"],
    "employment_history": [
      {"current": true, "start_date": "2022-04-01", "title": "...", "organization_name": "Contentful"},
      {"current": false, ...}
    ]
  }
}
```

After enrichment, you have everything needed to send an outreach.

---

## The three archetypes

Why we don't just "find the recruiter and call it a day":

### Recruiter
- **Pros:** their job is to read inbound; will respond if your profile is good
- **Cons:** high-volume gatekeeper, narrow filter, often the *worst* response rate per effort
- **How we find:** Apollo search filtered to titles in `["recruiter", "talent partner", "talent acquisition"]`
- **Code:** [api/app.py](../api/app.py) → `_candidates_for_archetype("recruiter", ...)`

### Hiring Manager
- **Pros:** actually decides; a thoughtful pitch can cut the recruiter line
- **Cons:** hardest to identify (rarely named in JD); easiest to ignore cold outreach
- **How we find:**
  1. Pull JD's `reports_to_target` (extracted by jd_parse, e.g. `{title: "vp", function: "product"}`)
  2. If the JD didn't state a reports-to, infer one tier up from the role's own level (e.g. Director PM → reports to VP Product). Marked as "inferred" with a confidence ceiling of 0.7×.
  3. Apollo search at the inferred level + function (e.g. `seniorities=["vp"]`, titles like `["VP product", "Vice President product"]`)
  4. Score every returned candidate with `_score_hm_candidate`
- **Code:** [analysis/people.py](../analysis/people.py) → `infer_hiring_manager`, `_score_hm_candidate`

### Recent Joiner
- **Pros:** lowest gatekeeping cost; will take a coffee chat; positive internal mention is gold
- **Cons:** doesn't decide; doesn't know the open req specifics
- **How we find:**
  1. Apollo search filtered by function (no level filter — recent joiners can be any level)
  2. Filter results to those with `tenure_start_date` in the last 12 months
  3. If no tenure-tagged hits: fall back to the first 5 search results (Apollo doesn't always populate tenure)
- **Code:** [api/app.py](../api/app.py) → `_candidates_for_archetype("recent_joiner", ...)`

---

## How HM inference scores someone (the actual heuristic)

Each candidate gets a score in [0, 1] from a weighted sum of components, with
explicit per-component evidence strings the user can sanity-check.

### Component weights

| Component | Max weight | When it fires |
|---|---|---|
| Title match (Jaccard + recall boost) | 0.45 | candidate's title shares tokens with `reports_to_target.title` |
| Seniority match | 0.20 | candidate's `seniority` field equals target level |
| Seniority within 1 level | 0.10 | one level off (e.g. director vs senior) |
| Function match | 0.15 | function keyword appears in title/bio/department |
| Team mention | 0.15 | parsed `team_or_org` appears in title/bio |
| Tenure penalty | × 0.6 | candidate started <3 months ago |
| Inferred reports-to penalty | × 0.7 | JD didn't state who role reports to |

### Title scoring details

- Tokens are normalized: `VP` ↔ `vice president`, `Sr.` ↔ `senior`, etc.
- Generic title noise dropped (`vice`, `president`, `manager`, `director`, `senior`, `staff`...) so `VP Product` and `Director, Product` don't false-match through their seniority-words. Only function-bearing tokens (e.g. `product`, `engineering`) survive.
- Score is Jaccard, with a +0.25 boost when every target token is present in the candidate's title.
- **Cross-function penalty:** if the title contains BOTH the target function AND a competing function (e.g. target=`product`, candidate title is "VP Product Marketing" → contains both `product` and `marketing`), the title-match score is multiplied by 0.6. This is what separates "VP Product Management" (correct HM) from "VP Product Marketing" (false positive).
- Code: [analysis/people.py](../analysis/people.py) → `_title_overlap`, `_normalize_title_tokens`, `_cross_function_penalty`

### Worked example — Director of Product role at Contentful

JD says: *"Director, Product Management. Reports to VP of Product."* (parsed)

Apollo search returns 3 candidates with `seniority=vp`:

| Candidate | Raw title overlap | Cross-fn penalty | Final |
|---|---|---|---|
| Adam Weinstein — *Vice President, Product Management* | high (target tokens all present) | × 1.0 | **0.42** |
| Kemberly — *Vice President Product Marketing* | medium (one shared token) | × 0.6 (marketing kw) | **0.17** |
| Matthew — *VP Deputy General Counsel - Privacy, Product, IP & Compliance* | low (one shared token + 5 competing tokens) | × 0.6 (legal kw) | **0.10** |

Adam wins clean. The actual HM is correctly identified.

---

## What we know about a person — what fields populate when

| Field | After search | After enrichment |
|---|:-:|:-:|
| `apollo_id` (stable identifier) | ✓ | ✓ |
| `first_name` / partial name | ✓ | ✓ (full name) |
| `name` (full) | sometimes | ✓ |
| `title` | ✓ | ✓ |
| `seniority` | sometimes | ✓ |
| `departments` | sometimes | ✓ |
| `linkedin_url` | ✗ | ✓ |
| `email` | ✗ | ✓ |
| `email_status` (verified / guessed / mock) | ✗ | ✓ |
| `phone_numbers` | ✗ | optional (extra credit cost) |
| `bio_summary` (headline) | sometimes | ✓ |
| `tenure_start_date` | sometimes | ✓ |
| `employment_history` | rarely | ✓ |
| `organization` (name + domain) | ✓ | ✓ |

The search step is sufficient to **rank** candidates and decide who to enrich.
The enrichment step is what gives you contact-able info.

This split is intentional in our wrapper — `find_people_at_company()` returns
search-only data, and `enrich_person()` is a separate explicit call. That way
the cost surface is predictable: an "auto-enrich top 1 per archetype" run
costs roughly `(3 archetypes × 1 search) + (3 archetypes × 1 reveal)` = ~6
credits per click.

---

## Where the data lives in our DB

### `people` table ([db/models.py](../db/models.py))

Stable identity store. Keyed unique by `apollo_id`. Filled progressively —
search-step rows have `email=null`, enrichment-step rows have it filled.

```sql
CREATE TABLE people (
    id, apollo_id, name, title, company_id, company_name,
    linkedin_url, email, email_status, phone, bio_summary,
    seniority, departments_json, tenure_start_date,
    archetype,           -- 'recruiter' | 'hiring_manager' | 'recent_joiner' | 'other'
    last_verified_at,
    source,              -- 'apollo' | 'apollo_mock'
    raw_payload_json,    -- full Apollo response (debugging)
    created_at, updated_at
);
```

### `apollo_api_calls` table

Every Apollo HTTP call (success or failure) gets logged here for cost audit
and debug. The cap-checker reads this table on every call.

```sql
CREATE TABLE apollo_api_calls (
    id, endpoint, request_summary, credits_used,
    status_code, error_msg, called_at
);
```

`apollo_usage_summary()` ([db/queries.py](../db/queries.py)) aggregates this
into today's / this-month's call count + credit sum. The dashboard surfaces
it on every Reach-out panel.

### `outreach_drafts` table

Persisted message drafts (one per (person, job, prompt_version)).

---

## Cost controls — how we don't accidentally burn $$$

Four caps, all read from env at every call site ([analysis/people.py](../analysis/people.py) → `_caps()`):

```
APOLLO_DAILY_CAP_CALLS=50         # max successful API calls per UTC day
APOLLO_MONTHLY_CAP_CALLS=500      # max successful API calls per UTC month
APOLLO_DAILY_CAP_CREDITS=200      # max credits per UTC day
APOLLO_MONTHLY_CAP_CREDITS=2000   # max credits per UTC month
```

Before every API call, `_check_caps()` queries the audit table and raises
`ApolloCapExceeded` if any cap is hit. The wrapper does **not** make the
Apollo HTTP call when over cap — guaranteed by the order:

```python
def _post(endpoint, body):
    _check_caps()   # raises if over cap, BEFORE the HTTP request
    ...HTTP call...
    queries.log_apollo_call(...)  # finally block, runs on success or failure
```

Failed calls (4xx/5xx) **don't count** against caps — only successful (2xx)
calls do. So an Apollo 403 (e.g. wrong plan tier) doesn't burn your daily
budget.

---

## Mock mode — for offline development

If `APOLLO_API_KEY` is empty (or `APOLLO_MOCK=1`), `_mock_mode()` returns true
and:

- `find_people_at_company()` returns 4 canned templates (VP Eng, technical
  recruiter, recent joiner, director of engineering) tagged with the
  appropriate archetype.
- `enrich_person()` synthesizes a full record from the apollo_id, fills in a
  fake email like `firstname.lastname@<companyname>.com`, sets `email_status="mock"`.
- Mock people are persisted with `source="apollo_mock"` so they're easy to
  wipe before going live.

This is what lets the rest of the pipeline (HM inference, outreach drafting,
resume tailoring) be developed and tested without paying real Apollo credits.

---

## Identity resolution gotchas

### What if the same person shows up in two searches?
Dedupe is automatic via `apollo_id`. Both `upsert_person()` and the unique
index on `people.apollo_id` ensure we don't double-write. The second call
updates the existing row in place.

### What if Apollo doesn't have the company's domain?
`_company_domain()` does a two-tier resolution:
1. Parse `companies.website` → hostname
2. If empty, guess `<sanitized name>.com` (right ~80% of the time for
   tech / SaaS companies)

If the guess is wrong, Apollo just returns 0 hits — recoverable, not an
error. The user can manually update `companies.website` to fix.

### What if multiple HMs match equally?
The score system surfaces this: when top-2 are within 0.05 of each other,
the UI shows both with their evidence trails. The user picks. We don't
pretend to know which is right.

### What about people who left the company?
Apollo's `mixed_people/api_search` returns *current* employees by default
(filtered by `q_organization_domains_list` matching their current employer).
But the data refreshes on Apollo's schedule, not ours — so someone who left
3 weeks ago might still appear. The `last_verified_at` timestamp on each
people row tracks when we last fetched. UI surfaces stale data with a "last
verified X ago" hint (Phase D backlog).

---

## File map

| File | Purpose |
|---|---|
| [analysis/people.py](../analysis/people.py) | Apollo wrapper, caps, mock mode, search, enrichment, HM scoring |
| [analysis/jd_parse.py](../analysis/jd_parse.py) | LLM-driven JD → structured fields (role title, level, function, reports_to_target) |
| [analysis/llm.py](../analysis/llm.py) | Provider-agnostic LLM client (Groq / OpenRouter / Cerebras / Gemini / OpenAI / Together) |
| [api/app.py](../api/app.py) | FastAPI endpoints — `/api/outreach/jobs/{id}/generate`, `_candidates_for_archetype()` orchestration |
| [db/models.py](../db/models.py) | Schema for `people`, `outreach_drafts`, `apollo_api_calls`, `tailored_resumes` |
| [db/queries.py](../db/queries.py) | CRUD for above tables; `apollo_usage_summary()` |
| [scripts/test_apollo_people.py](../scripts/test_apollo_people.py) | CLI smoke test — pick a job, fetch employees per archetype |
| [scripts/test_phase_b.py](../scripts/test_phase_b.py) | End-to-end CLI — JD parse → HM inference → enrich → outreach draft |

---

## Known limitations & honest caveats

1. **Search-tier data is partial.** First names + titles only. The split between search and enrichment is Apollo's pricing model, not ours.
2. **HM inference is heuristics, not magic.** Top-3 hit rate is ~80% on JDs that explicitly state reports-to, lower when JD is vague.
3. **Cross-function penalty is rule-based**, not semantic. Catches "Product Marketing" vs. "Product Management" but won't catch every edge case.
4. **Domain guessing is brittle for non-tech companies** ("Bank of America" → `bankofamerica.com` ✓ but "JP Morgan" → `jpmorgan.com` ✓ vs `jpmorganchase.com`?).
5. **Cache TTL is hardcoded to 30 days.** Reasonable for senior leadership turnover; too long for the recent-joiner archetype which becomes stale fast. Phase D backlog item.
6. **No 2nd-degree network mapping.** We don't know who *you* know. Asker-side data integration (LinkedIn CSV / Gmail / calendar) is deferred — that's the biggest single quality lift available.
7. **Apollo data freshness varies by company.** Unicorns are well-indexed; <50-person seed-stage startups have sparse coverage.

For the future-options doc on what gets added next, see [docs/JOB_SEARCH_BACKLOG.md](JOB_SEARCH_BACKLOG.md).
