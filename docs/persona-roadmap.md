# Persona Roadmap (Job Seeker, Industry Analyst, Recruiter)

Last updated: 2026-04-14

## 1) Current baseline

- Companies in DB: 527
- Active jobs: 32,386
- Tracked in next scrape run (after quality gates): 433
- Core product surfaces already live: Pulse, Changes, Trends, Companies, Coverage, Resume Fit, Skills, Roles, Job Feed, Health

This roadmap assumes growth and persona value ship together: every persona feature should either increase tracked companies/jobs, increase retention, or both.

## 2) Persona goals

### Job seeker
- Find high-fit roles quickly.
- Track “new since last check” jobs without re-running manual filters.
- Get alerts for role + location + skill criteria.

### Industry analyst
- Compare sector/company hiring velocity with confidence.
- Export repeatable slices (sector, stage, role family, location).
- Detect signal shifts (surges, pullbacks, role mix changes).

### Recruiter
- Monitor competitor hiring intent (where, what roles, how fast).
- Build watchlists of peer companies and role families.
- Get weekly deltas without manual dashboard work.

## 3) 90-day roadmap

## Phase 1 (Weeks 1-3): Persona foundations

### Epic A: Saved views + watchlists (all personas)
- Add saved filter presets for Job Feed and Companies.
- Add company watchlists and role-family watchlists.
- Add “new since last viewed” state per saved view.

Build notes:
- Backend: add `saved_views`, `watchlists`, `watchlist_items`, `view_events`.
- Frontend: save/load controls in `/jobs`, `/companies`, `/changes`.

Success criteria:
- 40%+ of active users create at least one saved view/watchlist.
- Increased return usage on `/jobs` and `/changes`.

### Epic B: Persona mode shell
- Add a top-level mode selector: `Job Seeker`, `Analyst`, `Recruiter`.
- Keep existing pages, but reorder nav defaults and summary cards per mode.

Success criteria:
- Faster first action time (time-to-filter/time-to-insight/time-to-watchlist).

## Phase 2 (Weeks 4-7): Persona workflows that pull users back

### Epic C: Job seeker “My Feed”
- New page: `/my-feed` with:
  - Saved searches
  - New jobs since last check
  - Resume Fit overlays for matching roles
- Add notification digest: daily/weekly email-ready payload generation (can start as API endpoint + downloadable digest).

Success criteria:
- Higher weekly repeat opens from saved feeds.
- More resumes analyzed per active user.

### Epic D: Analyst “Cohorts + Exports”
- New page: `/analyst`:
  - Cohort builder (sector + funding stage + company_type + ATS type)
  - Hiring index and role mix change by cohort
  - One-click CSV export with same cohort config

Success criteria:
- Analysts export data regularly instead of manually filtering each session.

### Epic E: Recruiter “Competitive Radar”
- New page: `/radar`:
  - Select competitors (watchlist)
  - Role-family and location hiring deltas by week
  - “Net hiring momentum” panel

Success criteria:
- Recruiters maintain multiple watchlists and review weekly deltas.

## Phase 3 (Weeks 8-12): Growth loops from persona usage

### Epic F: User-submitted coverage gaps
- Add “Track this company” + “Missing job posting?” actions on core pages.
- Route submissions to ingestion queue with confidence labels.

Success criteria:
- 10%+ of new tracked companies originate from user submissions.

### Epic G: Automated recommendations from behavior
- Recommend companies to track based on:
  - Popular saved views
  - Frequently watched competitors
  - Repeated missing-company searches

Success criteria:
- Higher net new tracked companies/jobs with stable quality-gate pass rate.

## 4) Prioritized backlog (ticket-ready)

P0
- `saved_views` backend schema + CRUD APIs
- Watchlist schema + CRUD APIs
- Add “new since last viewed” query support for `/api/jobs`
- Mode selector + mode-aware landing defaults

P1
- `/my-feed` page
- `/analyst` page (cohorts + exports)
- `/radar` page (competitive deltas)
- Digest payload API (`/api/digests/...`)

P2
- User submission intake queue
- Recommendation service for new companies
- Persona-specific onboarding prompts

## 5) KPI stack

Primary KPIs:
- Net new tracked companies/week
- Net active jobs/week
- Quality pass rate for new companies (first scrape >= 5 jobs and not auto-pruned)

Persona KPIs:
- Job seeker: saved feeds created/user, repeat feed opens/week
- Analyst: cohort exports/user, cohort re-use rate
- Recruiter: active watchlists/user, weekly radar opens

Reliability KPIs:
- Latest scrape failure count on tracked set
- Zero-job ratio on tracked set

## 6) Sequencing recommendation for build

1. Ship shared primitives first (`saved_views`, watchlists, mode selector).
2. Build `/my-feed` first (highest user pull + fastest value).
3. Build `/radar` next (recruiter monetizable workflow).
4. Build `/analyst` exports/cohorts after shared query primitives are stable.
5. Add submission/recommendation loops last to compound acquisition.

## 7) Immediate next sprint (start now)

- Implement DB migrations + APIs for saved views and watchlists.
- Add mode selector and persist mode choice.
- Add “new since last viewed” support to jobs query.
- Ship MVP `/my-feed` with saved searches + new job counts.
