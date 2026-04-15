const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
let apiReachable: boolean | null = null;
let apiProbeInFlight: Promise<boolean> | null = null;
let lastProbeAt = 0;
const API_PROBE_BACKOFF_MS = 15000;
const API_OFFLINE_UNTIL_KEY = "mosaic_api_offline_until";

function getOfflineUntil(): number {
  if (typeof window === "undefined") return 0;
  const raw = window.sessionStorage.getItem(API_OFFLINE_UNTIL_KEY);
  const value = raw ? Number(raw) : 0;
  return Number.isFinite(value) ? value : 0;
}

function setOfflineUntil(until: number): void {
  if (typeof window === "undefined") return;
  if (until <= 0) {
    window.sessionStorage.removeItem(API_OFFLINE_UNTIL_KEY);
    return;
  }
  window.sessionStorage.setItem(API_OFFLINE_UNTIL_KEY, String(until));
}

async function ensureApiReachable(): Promise<boolean> {
  const now = Date.now();
  const offlineUntil = getOfflineUntil();
  if (offlineUntil > now) {
    apiReachable = false;
    return false;
  }
  if (apiReachable === false && now - lastProbeAt < API_PROBE_BACKOFF_MS) {
    return false;
  }
  if (apiProbeInFlight) return apiProbeInFlight;
  apiProbeInFlight = fetch(`${API_BASE}/api/overview`)
    .then((res) => {
      apiReachable = res.ok;
      if (res.ok) setOfflineUntil(0);
      return res.ok;
    })
    .catch(() => {
      apiReachable = false;
      setOfflineUntil(Date.now() + API_PROBE_BACKOFF_MS);
      return false;
    })
    .finally(() => {
      lastProbeAt = Date.now();
      apiProbeInFlight = null;
    });
  return apiProbeInFlight;
}

async function fetchApi<T>(
  path: string,
  params?: Record<string, string | number | string[] | number[] | undefined>,
  fallback?: T
): Promise<T> {
  const reachable = await ensureApiReachable();
  if (!reachable) {
    if (fallback !== undefined) return fallback;
    throw new Error("API unreachable");
  }

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
  try {
    const res = await fetch(url.toString());
    apiReachable = true;
    if (!res.ok) {
      if (fallback !== undefined) return fallback;
      throw new Error(`API error: ${res.status}`);
    }
    return res.json();
  } catch (error) {
    apiReachable = false;
    lastProbeAt = Date.now();
    setOfflineUntil(Date.now() + API_PROBE_BACKOFF_MS);
    if (fallback !== undefined) return fallback;
    throw error;
  }
}

async function postFormApi<T>(path: string, formData: FormData): Promise<T> {
  const reachable = await ensureApiReachable();
  if (!reachable) {
    throw new Error("API unreachable");
  }
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, { method: "POST", body: formData });
    apiReachable = true;
    setOfflineUntil(0);
  } catch {
    apiReachable = false;
    lastProbeAt = Date.now();
    setOfflineUntil(Date.now() + API_PROBE_BACKOFF_MS);
    throw new Error("API unreachable");
  }
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

async function postApi<T>(path: string, body: Record<string, unknown>): Promise<T> {
  const reachable = await ensureApiReachable();
  if (!reachable) {
    throw new Error("API unreachable");
  }
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    apiReachable = true;
    setOfflineUntil(0);
  } catch {
    apiReachable = false;
    lastProbeAt = Date.now();
    setOfflineUntil(Date.now() + API_PROBE_BACKOFF_MS);
    throw new Error("API unreachable");
  }
  if (!res.ok) {
    let message = `API error: ${res.status}`;
    try {
      const payload = await res.json();
      if (payload.detail) message = payload.detail;
    } catch {
      // Keep default message.
    }
    throw new Error(message);
  }
  return res.json();
}

async function deleteApi<T>(path: string, params?: Record<string, string | number | undefined>): Promise<T> {
  const reachable = await ensureApiReachable();
  if (!reachable) {
    throw new Error("API unreachable");
  }
  const url = new URL(`${API_BASE}${path}`);
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== "") {
        url.searchParams.set(k, String(v));
      }
    });
  }
  let res: Response;
  try {
    res = await fetch(url.toString(), { method: "DELETE" });
    apiReachable = true;
    setOfflineUntil(0);
  } catch {
    apiReachable = false;
    lastProbeAt = Date.now();
    setOfflineUntil(Date.now() + API_PROBE_BACKOFF_MS);
    throw new Error("API unreachable");
  }
  if (!res.ok) {
    let message = `API error: ${res.status}`;
    try {
      const payload = await res.json();
      if (payload.detail) message = payload.detail;
    } catch {
      // Keep default message.
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

export interface SavedView {
  id: number;
  name: string;
  view_type: "jobs" | "companies";
  persona: string | null;
  filters: Record<string, unknown>;
  total_count: number;
  new_count: number;
  last_viewed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface Watchlist {
  id: number;
  name: string;
  persona: string | null;
  item_count: number;
  company_count: number;
  role_family_count: number;
  created_at: string;
  updated_at: string;
}

export interface WatchlistItem {
  watchlist_id: number;
  item_type: "company" | "role_family";
  item_value: string;
  company_id: number | null;
  company_name: string | null;
  added_at: string;
}

export interface AnalystWeeklyRow {
  week_start: string;
  added: number;
  removed: number;
  net: number;
}

export interface AnalystRoleMixRow {
  role_family: string;
  current_count: number;
  previous_count: number;
  delta: number;
}

export interface AnalystCompanyRow {
  id: number;
  name: string;
  sector: string | null;
  company_type: string;
  funding_round: string | null;
  ats_type: string | null;
  active_jobs: number;
  added_28d: number;
  removed_28d: number;
  net_28d: number;
}

export interface AnalystCohortResponse {
  cohort_company_count: number;
  cohort_active_jobs: number;
  weekly_index: AnalystWeeklyRow[];
  role_mix_change: AnalystRoleMixRow[];
  companies: AnalystCompanyRow[];
}

// API functions
export const api = {
  overview: (companyType?: string) => fetchApi<OverviewStats>(
    "/api/overview",
    { company_type: companyType },
    { total_companies: 0, total_active_jobs: 0, last_run: null, net_added: 0, net_removed: 0 }
  ),
  companies: () => fetchApi<CompanyRow[]>("/api/companies", undefined, []),
  companyVelocity: (days?: number) =>
    fetchApi<CompanyVelocity[]>("/api/companies/velocity", { days }, []),
  companyDetail: (id: number) => fetchApi<CompanyDetail>(`/api/companies/${id}`),
  sectors: () => fetchApi<SectorRow[]>("/api/sectors", undefined, []),
  departments: (companyType?: string) =>
    fetchApi<DepartmentRow[]>("/api/departments", { company_type: companyType }, []),
  seniority: (companyType?: string) =>
    fetchApi<SeniorityRow[]>("/api/seniority", { company_type: companyType }, []),
  workModels: (companyType?: string) =>
    fetchApi<WorkModelRow[]>("/api/work-models", { company_type: companyType }, []),
  roleFamilies: (companyType?: string) =>
    fetchApi<RoleFamilyRow[]>("/api/role-families", { company_type: companyType }, []),
  skills: (companyType?: string, limit?: number) =>
    fetchApi<SkillRow[]>("/api/skills", { company_type: companyType, limit }, []),
  jobs: (filters?: JobFilters) =>
    fetchApi<JobRow[]>("/api/jobs", filters as Record<string, string | number | string[] | number[] | undefined>, []),
  jobDetail: (id: number) => fetchApi<JobRow>(`/api/jobs/${id}`),
  jobFilters: () => fetchApi<FilterOptions>("/api/jobs/filters", undefined, { locations: [], employment_types: [] }),
  jobFreshness: (companyType?: string) =>
    fetchApi<FreshnessRow[]>("/api/jobs/freshness", { company_type: companyType }, []),
  jobTrends: () => fetchApi<TrendRow[]>("/api/jobs/trends", undefined, []),
  changeEvents: (params?: Record<string, string | number | undefined>) =>
    fetchApi<JobEvent[]>("/api/changes/events", params, []),
  movers: (days?: number) => fetchApi<Mover[]>("/api/changes/movers", { days }, []),
  sectorDelta: () => fetchApi<SectorDelta[]>("/api/changes/sector-delta", undefined, []),
  health: () => fetchApi<HealthRow[]>("/api/health", undefined, []),
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
  savedViews: (viewType?: "jobs" | "companies") =>
    fetchApi<SavedView[]>("/api/saved-views", { view_type: viewType }, []),
  createSavedView: (payload: {
    name: string;
    view_type: "jobs" | "companies";
    filters: Record<string, unknown>;
    persona?: string;
  }) => postApi<SavedView>("/api/saved-views", payload),
  markSavedViewViewed: (id: number) => postApi<SavedView>(`/api/saved-views/${id}/viewed`, {}),
  deleteSavedView: (id: number) => deleteApi<{ ok: boolean }>(`/api/saved-views/${id}`),
  watchlists: (persona?: string) =>
    fetchApi<Watchlist[]>("/api/watchlists", { persona }, []),
  createWatchlist: (payload: { name: string; persona?: string }) =>
    postApi<Watchlist>("/api/watchlists", payload),
  deleteWatchlist: (id: number) => deleteApi<{ ok: boolean }>(`/api/watchlists/${id}`),
  watchlistItems: (watchlistId: number) =>
    fetchApi<WatchlistItem[]>(`/api/watchlists/${watchlistId}/items`, undefined, []),
  addWatchlistItem: (
    watchlistId: number,
    payload: { item_type: "company" | "role_family"; item_value: string; company_id?: number }
  ) => postApi<WatchlistItem>(`/api/watchlists/${watchlistId}/items`, payload),
  removeWatchlistItem: (watchlistId: number, itemType: "company" | "role_family", itemValue: string) =>
    deleteApi<{ ok: boolean }>(`/api/watchlists/${watchlistId}/items`, { item_type: itemType, item_value: itemValue }),
  analystCohort: (params?: {
    sector?: string | string[];
    funding_round?: string | string[];
    company_type?: string | string[];
    ats_type?: string | string[];
    weeks?: number;
  }) => fetchApi<AnalystCohortResponse>(
    "/api/analyst/cohort",
    params as Record<string, string | number | string[] | number[] | undefined>,
    { cohort_company_count: 0, cohort_active_jobs: 0, weekly_index: [], role_mix_change: [], companies: [] }
  ),
  deptSectorCross: () => fetchApi<CrossTabRow[]>("/api/cross/dept-sector", undefined, []),
  senioritySectorCross: () => fetchApi<CrossTabRow[]>("/api/cross/seniority-sector", undefined, []),
  remoteSectorCross: (companyType?: string) =>
    fetchApi<CrossTabRow[]>("/api/cross/remote-sector", { company_type: companyType }, []),
};
