const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function fetchApi<T>(path: string, params?: Record<string, string | number | undefined>): Promise<T> {
  const url = new URL(`${API_BASE}${path}`);
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== "") {
        url.searchParams.set(k, String(v));
      }
    });
  }
  const res = await fetch(url.toString());
  if (!res.ok) throw new Error(`API error: ${res.status}`);
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

export interface JobFilters {
  search?: string;
  sector?: string;
  employment_type?: string;
  skill?: string;
  seniority?: string;
  work_model?: string;
  company_type?: string;
  company_id?: number;
  department?: string;
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
    fetchApi<JobRow[]>("/api/jobs", filters as Record<string, string | number | undefined>),
  jobFilters: () => fetchApi<FilterOptions>("/api/jobs/filters"),
  jobFreshness: (companyType?: string) =>
    fetchApi<FreshnessRow[]>("/api/jobs/freshness", { company_type: companyType }),
  jobTrends: () => fetchApi<TrendRow[]>("/api/jobs/trends"),
  changeEvents: (params?: Record<string, string | number | undefined>) =>
    fetchApi<JobEvent[]>("/api/changes/events", params),
  movers: (days?: number) => fetchApi<Mover[]>("/api/changes/movers", { days }),
  sectorDelta: () => fetchApi<SectorDelta[]>("/api/changes/sector-delta"),
  health: () => fetchApi<HealthRow[]>("/api/health"),
  deptSectorCross: () => fetchApi<CrossTabRow[]>("/api/cross/dept-sector"),
  senioritySectorCross: () => fetchApi<CrossTabRow[]>("/api/cross/seniority-sector"),
  remoteSectorCross: (companyType?: string) =>
    fetchApi<CrossTabRow[]>("/api/cross/remote-sector", { company_type: companyType }),
};
