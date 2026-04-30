const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function fetchApi<T>(
  path: string,
  params?: Record<string, string | number | boolean | string[] | number[] | undefined>
): Promise<T> {
  const url = new URL(`${API_BASE}${path}`);
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v === undefined || v === null || v === "") return;
      if (Array.isArray(v)) {
        const values = v.map((entry) => String(entry).trim()).filter(Boolean);
        if (values.length > 0) {
          url.searchParams.set(k, values.join(","));
        }
        return;
      }
      url.searchParams.set(k, String(v));
    });
  }
  const res = await fetch(url.toString(), { credentials: "include" });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

async function postFormApi<T>(path: string, formData: FormData): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { method: "POST", body: formData, credentials: "include" });
  if (!res.ok) {
    let message = `API error: ${res.status}`;
    try {
      const body = await res.json();
      if (body.detail) message = body.detail;
    } catch {
      // Keep default message.
    }
    throw new Error(message);
  }
  return res.json();
}

async function postJsonApi<T>(path: string, body: object | undefined = undefined): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
    credentials: "include",
  });
  if (!res.ok) {
    let message = `API error: ${res.status}`;
    try {
      const b = await res.json();
      if (b.detail) message = b.detail;
    } catch {
      // ignore
    }
    throw new Error(message);
  }
  return res.json();
}

export interface OverviewStats {
  total_companies: number;
  total_active_jobs: number;
  last_run: string | null;
  net_added: number;
  net_removed: number;
}

export interface SectorRow {
  sector: string;
  job_count: number;
}

export interface DepartmentRow {
  category: string;
  job_count: number;
}

export interface CompanyRow {
  id: number;
  name: string;
  sector: string;
  company_type: string;
  funding_round: string | null;
  funding_amount_m: number | null;
  funding_date: string | null;
  website: string | null;
  ats_type: string | null;
  active_jobs: number;
  last_scraped: string | null;
  total_added: number;
  total_removed: number;
}

export interface CompanyVelocity {
  company_id: number;
  added: number;
  removed: number;
  net: number;
}

export interface CompanyDetail extends CompanyRow {
  top_skills: SkillRow[];
  departments: DepartmentRow[];
}

export interface JobEvent {
  event_type: string;
  created_at: string;
  title: string;
  department: string | null;
  location: string | null;
  normalized_department: string | null;
  company: string;
  company_id: number;
  sector: string;
  company_type: string;
}

export interface Mover {
  name: string;
  company_id: number;
  sector: string;
  company_type: string;
  added: number;
  removed: number;
  net: number;
}

export interface CrossTabRow {
  sector: string;
  department?: string;
  seniority?: string;
  work_model?: string;
  job_count: number;
}

export interface SectorDelta {
  sector: string;
  added: number;
  removed: number;
  net: number;
}

export interface SkillRow {
  skill: string;
  count: number;
}

export interface SeniorityRow {
  seniority: string;
  count: number;
}

export interface WorkModelRow {
  work_model: string;
  count: number;
}

export interface RoleFamilyRow {
  role_family: string;
  count: number;
}

export interface FreshnessRow {
  bucket: string;
  count: number;
}

export interface TrendRow {
  company: string;
  sector: string;
  date: string;
  job_count: number;
}

export interface JobRow {
  id: number;
  company_id: number;
  title: string;
  department: string | null;
  location: string | null;
  employment_type: string | null;
  url: string | null;
  first_seen_at: string;
  last_seen_at: string;
  is_active: number;
  company_name: string;
  sector: string;
  company_type: string;
  ats_type: string | null;
  funding_round: string | null;
  normalized_department: string | null;
  seniority: string | null;
  work_model: string | null;
  role_family: string | null;
  location_city: string | null;
  location_region: string | null;
  location_country: string | null;
  remote_scope: string | null;
  posting_status: string | null;
  last_status_change_at: string | null;
}

export interface FilterOptions {
  locations: string[];
  employment_types: string[];
}

export interface HealthRow {
  id: number;
  name: string;
  sector: string;
  ats_type: string | null;
  company_type: string;
  last_run: string | null;
  status: string | null;
  error_msg: string | null;
  jobs_found: number | null;
  active_jobs: number;
}

export interface ResumeProfile {
  headline?: string | null;
  target_roles: string[];
  role_families: string[];
  seniority?: string | null;
  skills: string[];
  domains: string[];
  strengths: string[];
  remote_preference: string;
}

export interface FitJob {
  id: number;
  company_id: number;
  company_name: string;
  title: string;
  sector: string | null;
  company_type: string | null;
  department: string | null;
  role_family: string | null;
  seniority: string | null;
  work_model: string | null;
  location: string | null;
  url: string | null;
  first_seen_at: string | null;
}

export interface JobFitMatch {
  job: FitJob;
  deterministic_score: number;
  matched_skills: string[];
  fit_score: number;
  verdict: string;
  why: string[];
  gaps: string[];
  resume_pointers: string[];
  location_note: string | null;
  location_blocker: boolean;
  cached: boolean;
}

export interface FitMatchesResponse {
  resume_id: number;
  resume_hash: string;
  provider: string;
  model: string;
  prompt_version: string;
  profile: ResumeProfile;
  shortlist_count: number;
  matches: JobFitMatch[];
}

export interface OutreachPerson {
  id?: number;
  apollo_id?: string | null;
  name?: string;
  title?: string | null;
  linkedin_url?: string | null;
  email?: string | null;
  email_status?: string | null;
  bio_summary?: string | null;
  seniority?: string | null;
  archetype?: string | null;
  hm_score?: number | null;
  hm_evidence?: string[] | null;
  _error?: string;
  _enrich_error?: string;
}

export type OutreachStatus = "draft" | "sent" | "replied" | "no_reply" | "bounced";

export interface OutreachDraft {
  id?: number | null;
  job_id?: number | null;
  person_id?: number | null;
  person_name?: string | null;
  person_title?: string | null;
  person_linkedin_url?: string | null;
  person_email?: string | null;
  archetype?: string | null;
  subject?: string;
  message?: string;
  rationale?: {
    person_artifacts_referenced?: string[];
    company_artifacts_referenced?: string[];
    matched_skills?: string[];
  };
  tone?: string;
  provider?: string;
  model?: string;
  prompt_version?: string;
  status?: OutreachStatus;
  sent_at?: string | null;
  sent_via?: string | null;
  replied_at?: string | null;
  reply_text?: string | null;
  reply_category?: string | null;
  follow_up_due_at?: string | null;
  // Listing-page extras (joined from people + job + company)
  job_title?: string;
  job_url?: string | null;
  company_id?: number;
  company_name?: string;
  _error?: string;
}

export interface OutreachListResponse {
  drafts: OutreachDraft[];
  counts: {
    by_status: Partial<Record<OutreachStatus, number>>;
    overdue: number;
  };
}

export type JobStatus =
  | "saved"
  | "applied"
  | "interviewing"
  | "rejected"
  | "offered"
  | "dismissed";

export interface UserJobStatus {
  id?: number;
  job_id: number;
  status: JobStatus | null;
  notes?: string | null;
  action_at?: string;
  outcome?: string | null;
  outcome_at?: string | null;
}

export interface OutreachJobSummary {
  total?: number;
  draft?: number;
  sent?: number;
  replied?: number;
  no_reply?: number;
  bounced?: number;
  positive?: number;
  neutral?: number;
  negative?: number;
  interview?: number;
}

export interface PipelineJob {
  status: JobStatus;
  notes?: string | null;
  action_at: string;
  outcome?: string | null;
  outcome_at?: string | null;
  job_id: number;
  job_title: string;
  job_url?: string | null;
  location?: string | null;
  location_city?: string | null;
  seniority?: string | null;
  work_model?: string | null;
  role_family?: string | null;
  normalized_department?: string | null;
  first_seen_at?: string | null;
  posting_status?: string | null;
  is_active?: number | boolean;
  company_id: number;
  company_name: string;
  sector?: string | null;
  outreach?: OutreachJobSummary;
}

export interface SavedSearch {
  id: number;
  user_id: number;
  surface: string;
  name: string;
  params_json: string;
  created_at: string;
  last_run_at?: string | null;
}

export interface ReplyBreakdown {
  by_category: { positive?: number; neutral?: number; negative?: number; interview?: number };
  totals: {
    draft: number;
    sent: number;
    replied: number;
    no_reply: number;
    bounced: number;
    awaiting_reply: number;
    reply_rate: number;
  };
}

export interface PipelineResponse {
  jobs: PipelineJob[];
  counts: Partial<Record<JobStatus, number>>;
}

export interface TailoredResume {
  tailored_text?: string;
  diff_summary?: {
    sections_changed?: string[];
    keywords_added?: string[];
    bullets_emphasized?: string[];
    bullets_rephrased?: { before: string; after: string }[];
    warnings?: string[];
  };
  provider?: string;
  model?: string;
  prompt_version?: string;
  _error?: string;
}

export interface SimilarJobMatch {
  id: number;
  title: string;
  company_id: number;
  company_name?: string;
  sector?: string | null;
  location?: string | null;
  url?: string | null;
  role_family?: string | null;
  seniority?: string | null;
  work_model?: string | null;
  deterministic_score: number;
  matched_skills?: string[];
}

export interface SimilarJobsResponse {
  parsed_jd: {
    role_title?: string | null;
    level?: string | null;
    function?: string | null;
    sub_function?: string | null;
    must_have_skills?: string[];
    team_or_org?: string | null;
  };
  shortlist_count: number;
  matches: SimilarJobMatch[];
  fetched?: {
    title?: string;
    company?: string;
    location?: string;
    url?: string;
    source?: "greenhouse" | "lever" | "ashby" | "html";
    char_count?: number;
  };
}

export interface OutreachResponse {
  job: { id: number; title: string; company_name: string; url?: string | null };
  parsed_jd: {
    level?: string | null;
    function?: string | null;
    reports_to_phrase?: string | null;
    reports_to_target?: { title?: string; team_or_org?: string | null; level?: string | null; function?: string | null } | null;
    team_or_org?: string | null;
    must_have_skills?: string[];
    /** True when the job had no description in the DB; outreach falls back to title-only context. */
    jd_missing?: boolean;
  };
  people_by_archetype: Record<string, OutreachPerson[]>;
  drafts: OutreachDraft[];
  tailored_resume: TailoredResume | null;
  apollo_usage: {
    caps: { calls_daily: number; calls_monthly: number; credits_daily: number; credits_monthly: number };
    used: { calls_today: number; calls_month: number; credits_today: number; credits_month: number };
    mock_mode: boolean;
  };
}

export interface FitJobResponse {
  resume_id: number;
  resume_hash: string;
  provider: string;
  model: string;
  prompt_version: string;
  profile: ResumeProfile;
  match: JobFitMatch;
}

export interface JobFilters {
  search?: string;
  sector?: string | string[];
  employment_type?: string | string[];
  skill?: string | string[];
  seniority?: string | string[];
  work_model?: string | string[];
  company_type?: string | string[];
  company_id?: number;
  department?: string | string[];
  ats_type?: string | string[];
  funding_round?: string | string[];
}

// API functions
export const api = {
  overview: (companyType?: string) => fetchApi<OverviewStats>("/api/overview", { company_type: companyType }),
  companies: () => fetchApi<CompanyRow[]>("/api/companies"),
  companyVelocity: (days?: number) =>
    fetchApi<CompanyVelocity[]>("/api/companies/velocity", { days }),
  companyDetail: (id: number) => fetchApi<CompanyDetail>(`/api/companies/${id}`),
  sectors: () => fetchApi<SectorRow[]>("/api/sectors"),
  departments: (companyType?: string) =>
    fetchApi<DepartmentRow[]>("/api/departments", { company_type: companyType }),
  seniority: (companyType?: string) =>
    fetchApi<SeniorityRow[]>("/api/seniority", { company_type: companyType }),
  workModels: (companyType?: string) =>
    fetchApi<WorkModelRow[]>("/api/work-models", { company_type: companyType }),
  roleFamilies: (companyType?: string) =>
    fetchApi<RoleFamilyRow[]>("/api/role-families", { company_type: companyType }),
  skills: (companyType?: string, limit?: number) =>
    fetchApi<SkillRow[]>("/api/skills", { company_type: companyType, limit }),
  jobs: (filters?: JobFilters) =>
    fetchApi<JobRow[]>("/api/jobs", filters as Record<string, string | number | string[] | number[] | undefined>),
  jobDetail: (id: number) => fetchApi<JobRow>(`/api/jobs/${id}`),
  jobFilters: () => fetchApi<FilterOptions>("/api/jobs/filters"),
  jobFreshness: (companyType?: string) =>
    fetchApi<FreshnessRow[]>("/api/jobs/freshness", { company_type: companyType }),
  jobTrends: () => fetchApi<TrendRow[]>("/api/jobs/trends"),
  changeEvents: (params?: Record<string, string | number | undefined>) =>
    fetchApi<JobEvent[]>("/api/changes/events", params),
  movers: (days?: number) => fetchApi<Mover[]>("/api/changes/movers", { days }),
  sectorDelta: () => fetchApi<SectorDelta[]>("/api/changes/sector-delta"),
  health: () => fetchApi<HealthRow[]>("/api/health"),
  fitMatches: (file: File, options?: { company_type?: string; limit?: number }) => {
    const form = new FormData();
    form.set("resume", file);
    if (options?.company_type) form.set("company_type", options.company_type);
    if (options?.limit) form.set("limit", String(options.limit));
    return postFormApi<FitMatchesResponse>("/api/fit/matches", form);
  },
  fitJob: (jobId: number, file: File) => {
    const form = new FormData();
    form.set("resume", file);
    return postFormApi<FitJobResponse>(`/api/fit/jobs/${jobId}`, form);
  },
  similarJobsFromJd: (
    input: { jdText?: string; url?: string; limit?: number; companyType?: string },
  ) => {
    const body = JSON.stringify({
      jd_text: input.jdText || null,
      url: input.url || null,
      limit: input.limit ?? 20,
      company_type: input.companyType ?? null,
    });
    return fetch(`${API_BASE}/api/jobs/similar-to-jd`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
      credentials: "include",
    }).then(async (res) => {
      if (!res.ok) {
        let msg = `API error: ${res.status}`;
        try {
          const b = await res.json();
          if (b.detail) msg = b.detail;
        } catch {}
        throw new Error(msg);
      }
      return res.json() as Promise<SimilarJobsResponse>;
    });
  },
  outreachGenerate: (
    jobId: number,
    options?: {
      file?: File | null;
      archetypes?: string[];
      enrichTop?: number;
      includeTailoredResume?: boolean;
    }
  ) => {
    const form = new FormData();
    if (options?.file) form.set("resume", options.file);
    form.set(
      "archetypes",
      (options?.archetypes ?? ["recruiter", "hiring_manager", "recent_joiner"]).join(","),
    );
    form.set("enrich_top", String(options?.enrichTop ?? 1));
    form.set("include_tailored_resume", String(options?.includeTailoredResume ?? true));
    return postFormApi<OutreachResponse>(`/api/outreach/jobs/${jobId}/generate`, form);
  },
  // Outreach lifecycle
  outreachListDrafts: (filters?: {
    status?: OutreachStatus;
    archetype?: string;
    overdue_only?: boolean;
    company_ids?: number[];
    job_id?: number;
  }) =>
    fetchApi<OutreachListResponse>("/api/outreach/drafts", {
      status: filters?.status,
      archetype: filters?.archetype,
      overdue_only: filters?.overdue_only,
      company_ids: filters?.company_ids?.length
        ? filters.company_ids.join(",")
        : undefined,
      job_id: filters?.job_id,
    }),
  outreachCompanies: () =>
    fetchApi<{ companies: { company_id: number; company_name: string; n: number }[] }>(
      "/api/outreach/companies",
    ),
  outreachCounts: () =>
    fetchApi<{ by_status: Partial<Record<OutreachStatus, number>>; overdue: number }>(
      "/api/outreach/counts",
    ),
  outreachCreateDraft: (
    payload: Partial<OutreachDraft> & {
      job_id: number;
      person_id: number;
      message: string;
      status?: "draft" | "sent";
      sent_via?: string;
      user_edits?: string;
      provider?: string;
      model?: string;
      prompt_version?: string;
    },
  ) => postJsonApi<OutreachDraft>("/api/outreach/drafts", payload),
  outreachMarkSent: (draftId: number, body?: { sent_via?: string; user_edits?: string; follow_up_days?: number }) =>
    postJsonApi<OutreachDraft>(`/api/outreach/drafts/${draftId}/sent`, body ?? {}),
  outreachLogReply: (draftId: number, body?: { reply_text?: string; reply_category?: string }) =>
    postJsonApi<OutreachDraft>(`/api/outreach/drafts/${draftId}/reply`, body ?? {}),
  outreachSetStatus: (draftId: number, status: OutreachStatus) =>
    postJsonApi<OutreachDraft>(`/api/outreach/drafts/${draftId}/status`, { status }),
  // User job pipeline (saved / applied / dismissed)
  jobSetStatus: (jobId: number, status: JobStatus, notes?: string) =>
    postJsonApi<UserJobStatus>(`/api/jobs/${jobId}/status`, { status, notes }),
  jobClearStatus: async (jobId: number) => {
    const res = await fetch(`${API_BASE}/api/jobs/${jobId}/status`, { method: "DELETE", credentials: "include" });
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
  },
  jobStatusBatch: (jobIds: number[]) =>
    postJsonApi<Record<string, UserJobStatus>>("/api/jobs/status/batch", { job_ids: jobIds }),
  pipeline: (status?: JobStatus) =>
    fetchApi<PipelineResponse>("/api/pipeline", { status }),
  pipelineCounts: () => fetchApi<Partial<Record<JobStatus, number>>>("/api/pipeline/counts"),
  // Auth
  authMe: () =>
    fetchApi<{ user: { id: number; email: string } | null; signups_allowed: boolean }>(
      "/api/auth/me",
    ),
  authSignup: (email: string, password: string) =>
    postJsonApi<{ id: number; email: string }>("/api/auth/signup", { email, password }),
  authLogin: (email: string, password: string) =>
    postJsonApi<{ id: number; email: string }>("/api/auth/login", { email, password }),
  authLogout: () => postJsonApi<{ ok: true }>("/api/auth/logout"),
  // Saved searches
  savedSearchesList: (surface?: string) =>
    fetchApi<{ searches: SavedSearch[] }>("/api/saved-searches", { surface }),
  savedSearchesCreate: (surface: string, name: string, params: Record<string, unknown>) =>
    postJsonApi<SavedSearch>("/api/saved-searches", { surface, name, params }),
  savedSearchesDelete: async (id: number) => {
    const res = await fetch(`${API_BASE}/api/saved-searches/${id}`, {
      method: "DELETE",
      credentials: "include",
    });
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
  },
  fitFromJobs: (file: File, jobIds: number[], limit = 20) => {
    const form = new FormData();
    form.set("resume", file);
    form.set("job_ids", jobIds.join(","));
    form.set("limit", String(limit));
    return postFormApi<FitMatchesResponse>("/api/fit/from-jobs", form);
  },
  outreachReplyBreakdown: () => fetchApi<ReplyBreakdown>("/api/outreach/reply-breakdown"),
  outreachSummaryBatch: (jobIds: number[]) =>
    postJsonApi<Record<string, OutreachJobSummary>>("/api/outreach/summary/batch", { job_ids: jobIds }),
  deptSectorCross: () => fetchApi<CrossTabRow[]>("/api/cross/dept-sector"),
  senioritySectorCross: () => fetchApi<CrossTabRow[]>("/api/cross/seniority-sector"),
  remoteSectorCross: (companyType?: string) =>
    fetchApi<CrossTabRow[]>("/api/cross/remote-sector", { company_type: companyType }),
};
