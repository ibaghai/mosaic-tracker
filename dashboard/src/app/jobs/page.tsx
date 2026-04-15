"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  api,
  CompanyRow,
  JobRow,
  SkillRow,
  DepartmentRow,
  JobFilters,
  FreshnessRow,
  SavedView,
  Watchlist,
  RoleFamilyRow,
} from "@/lib/api";
import { formatRoleFamily, formatSeniority, formatWorkModel, FUNDING_ORDER, SENIORITY_LABELS } from "@/lib/format";
import { downloadCSV } from "@/lib/export";
import { MultiValuePicker } from "@/components/MultiValuePicker";

const WORK_MODELS = ["remote", "hybrid", "onsite"];
const COMPANY_TYPE_OPTIONS = [
  { value: "startup", label: "Startups" },
  { value: "bigco", label: "Big companies" },
];

function toMultiValues(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value.map((entry) => String(entry).trim()).filter(Boolean);
  }
  if (typeof value === "string") {
    return value.split(",").map((entry) => entry.trim()).filter(Boolean);
  }
  return [];
}

export default function JobFeedPage() {
  const [jobs, setJobs] = useState<JobRow[]>([]);
  const [skills, setSkills] = useState<SkillRow[]>([]);
  const [departments, setDepartments] = useState<DepartmentRow[]>([]);
  const [freshness, setFreshness] = useState<FreshnessRow[]>([]);
  const [roleFamilies, setRoleFamilies] = useState<RoleFamilyRow[]>([]);
  const [savedViews, setSavedViews] = useState<SavedView[]>([]);
  const [watchlists, setWatchlists] = useState<Watchlist[]>([]);
  const [loading, setLoading] = useState(false);
  const [sectorOptions, setSectorOptions] = useState<string[]>([]);
  const [empTypeOptions, setEmpTypeOptions] = useState<string[]>([]);
  const [atsTypeOptions, setAtsTypeOptions] = useState<string[]>([]);
  const [fundingRoundOptions, setFundingRoundOptions] = useState<string[]>([]);

  // Filters
  const [search, setSearch] = useState("");
  const [sector, setSector] = useState<string[]>([]);
  const [empType, setEmpType] = useState<string[]>([]);
  const [skill, setSkill] = useState<string[]>([]);
  const [seniority, setSeniority] = useState<string[]>([]);
  const [workModel, setWorkModel] = useState<string[]>([]);
  const [companyType, setCompanyType] = useState<string[]>([]);
  const [department, setDepartment] = useState<string[]>([]);
  const [atsType, setAtsType] = useState<string[]>([]);
  const [fundingRound, setFundingRound] = useState<string[]>([]);
  const [viewName, setViewName] = useState("");
  const [selectedWatchlistId, setSelectedWatchlistId] = useState<number | "">("");
  const [watchRoleFamily, setWatchRoleFamily] = useState("");
  const [actionError, setActionError] = useState("");

  useEffect(() => {
    void Promise.all([
      api.skills(undefined, 95),
      api.departments(),
      api.jobFreshness(),
      api.savedViews("jobs"),
      api.watchlists(),
      api.roleFamilies(),
      api.companies(),
      api.jobFilters(),
    ]).then(([skillRows, deptRows, freshRows, views, lists, roles, companyRows, jobFilterOptions]) => {
      setSkills(skillRows);
      setDepartments(deptRows);
      setFreshness(freshRows);
      setSavedViews(views);
      setWatchlists(lists);
      setRoleFamilies(roles);
      const companySectors = [...new Set(companyRows.map((company: CompanyRow) => company.sector).filter(Boolean))].sort();
      const companyAtsTypes = [...new Set(companyRows.map((company: CompanyRow) => company.ats_type).filter((value): value is string => Boolean(value)))].sort();
      const fundingSet = new Set(
        companyRows
          .map((company: CompanyRow) => company.funding_round)
          .filter((value): value is string => Boolean(value))
      );
      const orderedFunding = [
        ...FUNDING_ORDER.filter((round) => fundingSet.has(round)),
        ...[...fundingSet].filter((round) => !FUNDING_ORDER.includes(round)).sort(),
      ];
      const employmentTypes = [...new Set(jobFilterOptions.employment_types.map((value) => value.trim()).filter(Boolean))].sort();
      setSectorOptions(companySectors);
      setAtsTypeOptions(companyAtsTypes);
      setFundingRoundOptions(orderedFunding);
      setEmpTypeOptions(employmentTypes);
      if (lists.length > 0) setSelectedWatchlistId(lists[0].id);
      if (roles.length > 0) setWatchRoleFamily(String(roles[0].role_family || ""));
    });
  }, []);

  const filters = useMemo((): JobFilters => ({
    search: search || undefined,
    sector: sector.length ? sector : undefined,
    employment_type: empType.length ? empType : undefined,
    skill: skill.length ? skill : undefined,
    seniority: seniority.length ? seniority : undefined,
    work_model: workModel.length ? workModel : undefined,
    company_type: companyType.length ? companyType : undefined,
    department: department.length ? department : undefined,
    ats_type: atsType.length ? atsType : undefined,
    funding_round: fundingRound.length ? fundingRound : undefined,
  }), [search, sector, empType, skill, seniority, workModel, companyType, department, atsType, fundingRound]);

  useEffect(() => {
    let cancelled = false;
    void Promise.resolve()
      .then(() => {
        if (!cancelled) setLoading(true);
        return api.jobs(filters);
      })
      .then((data) => {
        if (!cancelled) {
          setJobs(data);
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [filters]);

  const activeFilters = Number(Boolean(search))
    + sector.length
    + empType.length
    + skill.length
    + seniority.length
    + workModel.length
    + companyType.length
    + department.length
    + atsType.length
    + fundingRound.length;

  const freshnessLookup = useMemo(
    () => freshness.reduce<Record<string, number>>((acc, row) => {
      acc[row.bucket] = row.count;
      return acc;
    }, {}),
    [freshness]
  );

  const handleExport = () => {
    const rows = jobs.slice(0, 500).map((j) => ({
      Title: j.title,
      Company: j.company_name,
      Sector: j.sector,
      Department: j.normalized_department || j.department || "",
      Seniority: formatSeniority(j.seniority),
      "Work Model": formatWorkModel(j.work_model),
      Location: j.location || "",
      "Employment Type": j.employment_type || "",
      Posted: new Date(j.first_seen_at).toLocaleDateString(),
      URL: j.url || "",
    }));
    downloadCSV(rows as Record<string, unknown>[], "mosaic-jobs.csv");
  };

  const refreshSavedViews = () => {
    void api.savedViews("jobs").then(setSavedViews);
  };

  const handleSaveView = async () => {
    if (!viewName.trim()) return;
    try {
      setActionError("");
      await api.createSavedView({
        name: viewName.trim(),
        view_type: "jobs",
        persona: "job_seeker",
        filters: {
          search,
          sector,
          employment_type: empType,
          skill,
          seniority,
          work_model: workModel,
          company_type: companyType,
          department,
          ats_type: atsType,
          funding_round: fundingRound,
        },
      });
      setViewName("");
      refreshSavedViews();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Could not save view");
    }
  };

  const applySavedView = async (view: SavedView) => {
    const f = view.filters || {};
    setSearch(String(f.search || ""));
    setSector(toMultiValues(f.sector));
    setEmpType(toMultiValues(f.employment_type));
    setSkill(toMultiValues(f.skill));
    setSeniority(toMultiValues(f.seniority));
    setWorkModel(toMultiValues(f.work_model));
    setCompanyType(toMultiValues(f.company_type));
    setDepartment(toMultiValues(f.department));
    setAtsType(toMultiValues(f.ats_type));
    setFundingRound(toMultiValues(f.funding_round));
    try {
      setActionError("");
      await api.markSavedViewViewed(view.id);
      refreshSavedViews();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Could not apply view");
    }
  };

  const addRoleFamilyToWatchlist = async () => {
    if (!selectedWatchlistId || !watchRoleFamily) return;
    try {
      setActionError("");
      await api.addWatchlistItem(Number(selectedWatchlistId), {
        item_type: "role_family",
        item_value: watchRoleFamily,
      });
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Could not update watchlist");
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-2xl font-bold">Job Feed</h2>
          <p className="text-muted text-sm mt-1">
            {loading ? "Loading..." : `${jobs.length.toLocaleString()} active jobs`}
            {activeFilters > 0 && (
              <span className="ml-2 text-accent-light">· {activeFilters} filter{activeFilters > 1 ? "s" : ""} active</span>
            )}
          </p>
        </div>
        <button
          onClick={handleExport}
          className="px-3 py-2 text-xs bg-card border border-card-border rounded-lg text-muted hover:text-foreground transition-colors"
        >
          Export CSV
        </button>
      </div>

      <div className="bg-card border border-card-border rounded-xl p-4 space-y-3">
        <div className="flex flex-wrap gap-3 items-center">
          <input
            type="text"
            placeholder="Name this view..."
            value={viewName}
            onChange={(e) => setViewName(e.target.value)}
            className="bg-background border border-card-border rounded-lg px-3 py-2 text-sm text-foreground w-full sm:w-56"
          />
          <button
            onClick={handleSaveView}
            className="px-3 py-2 text-xs bg-accent text-white rounded-lg hover:bg-accent/90 transition-colors"
          >
            Save current view
          </button>
        </div>
        {savedViews.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {savedViews.map((view) => (
              <div key={view.id} className="inline-flex items-center gap-1 bg-background border border-card-border rounded-lg px-2 py-1">
                <button
                  onClick={() => applySavedView(view)}
                  className="text-xs text-muted hover:text-foreground"
                >
                  {view.name}
                  <span className="ml-1 opacity-70">({view.total_count})</span>
                  {view.new_count > 0 && (
                    <span className="ml-1 text-green">+{view.new_count} new</span>
                  )}
                </button>
                <button
                  onClick={() => {
                    void api.deleteSavedView(view.id)
                      .then(refreshSavedViews)
                      .catch((err) => setActionError(err instanceof Error ? err.message : "Could not delete view"));
                  }}
                  className="text-xs text-muted hover:text-red px-1"
                  title="Delete view"
                >
                  x
                </button>
              </div>
            ))}
          </div>
        )}
        {actionError && <p className="text-xs text-red">{actionError}</p>}
      </div>

      {/* Filter bar */}
      <div className="bg-card border border-card-border rounded-xl p-4 space-y-3">
        <div className="flex flex-wrap gap-3">
          <input
            type="text"
            placeholder="Search by job title..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="bg-background border border-card-border rounded-lg px-3 py-2 text-sm text-foreground w-full sm:w-64"
          />
          <MultiValuePicker
            placeholder="Add sector"
            options={sectorOptions.map((item) => ({ value: item, label: item }))}
            values={sector}
            onChange={setSector}
          />
          <MultiValuePicker
            placeholder="Add company type"
            options={COMPANY_TYPE_OPTIONS}
            values={companyType}
            onChange={setCompanyType}
          />
          <MultiValuePicker
            placeholder="Add ATS"
            options={atsTypeOptions.map((item) => ({ value: item, label: item }))}
            values={atsType}
            onChange={setAtsType}
          />
          <MultiValuePicker
            placeholder="Add funding stage"
            options={fundingRoundOptions.map((item) => ({ value: item, label: item }))}
            values={fundingRound}
            onChange={setFundingRound}
          />
        </div>
        <div className="flex flex-wrap gap-3">
          <MultiValuePicker
            placeholder="Add department"
            options={departments.map((item) => ({
              value: item.category,
              label: `${item.category} (${item.job_count.toLocaleString()})`,
            }))}
            values={department}
            onChange={setDepartment}
          />
          <MultiValuePicker
            placeholder="Add skill"
            options={skills.map((item) => ({ value: item.skill, label: `${item.skill} (${item.count})` }))}
            values={skill}
            onChange={setSkill}
          />
          <MultiValuePicker
            placeholder="Add seniority"
            options={Object.entries(SENIORITY_LABELS).map(([value, label]) => ({ value, label }))}
            values={seniority}
            onChange={setSeniority}
          />
          <MultiValuePicker
            placeholder="Add work model"
            options={WORK_MODELS.map((item) => ({ value: item, label: formatWorkModel(item) }))}
            values={workModel}
            onChange={setWorkModel}
          />
          <MultiValuePicker
            placeholder="Add employment type"
            options={empTypeOptions.map((item) => ({ value: item, label: item }))}
            values={empType}
            onChange={setEmpType}
          />
          {activeFilters > 0 && (
            <button
              onClick={() => {
                setSearch("");
                setSector([]);
                setEmpType([]);
                setSkill([]);
                setSeniority([]);
                setWorkModel([]);
                setCompanyType([]);
                setDepartment([]);
                setAtsType([]);
                setFundingRound([]);
              }}
              className="px-3 py-2 text-xs text-red border border-red/30 rounded-lg hover:bg-red/10 transition-colors"
            >
              Clear all
            </button>
          )}
        </div>
        <div className="flex flex-wrap gap-2">
          {["0-3 days", "4-7 days", "8-14 days"].map((bucket) => (
            <span key={bucket} className="px-2.5 py-1 rounded-full text-xs border border-card-border text-muted bg-background">
              {bucket}: {(freshnessLookup[bucket] || 0).toLocaleString()}
            </span>
          ))}
        </div>
        <div className="flex flex-wrap gap-3 items-center">
          <select
            value={selectedWatchlistId}
            onChange={(e) => setSelectedWatchlistId(e.target.value ? Number(e.target.value) : "")}
            className="bg-background border border-card-border rounded-lg px-3 py-2 text-sm text-foreground"
          >
            <option value="">Select watchlist</option>
            {watchlists.map((w) => (
              <option key={w.id} value={w.id}>{w.name}</option>
            ))}
          </select>
          <select
            value={watchRoleFamily}
            onChange={(e) => setWatchRoleFamily(e.target.value)}
            className="bg-background border border-card-border rounded-lg px-3 py-2 text-sm text-foreground"
          >
            <option value="">Role family</option>
            {roleFamilies.map((r) => (
              <option key={r.role_family} value={r.role_family}>{formatRoleFamily(r.role_family)}</option>
            ))}
          </select>
          <button
            onClick={() => { void addRoleFamilyToWatchlist(); }}
            disabled={!selectedWatchlistId || !watchRoleFamily}
            className="px-3 py-2 text-xs bg-card border border-card-border rounded-lg text-muted hover:text-foreground disabled:opacity-40 transition-colors"
          >
            Add role family to watchlist
          </button>
        </div>
      </div>

      <div className="bg-card border border-card-border rounded-xl overflow-hidden">
        <div className="max-h-[60vh] overflow-y-auto overflow-x-auto">
          <table className="w-full text-sm min-w-[800px]">
            <thead className="sticky top-0 bg-card z-10">
              <tr className="text-muted text-left border-b border-card-border">
                <th className="px-4 py-3 font-medium">Job Title</th>
                <th className="px-4 py-3 font-medium">Company</th>
                <th className="px-4 py-3 font-medium">Department</th>
                <th className="px-4 py-3 font-medium">Role</th>
                <th className="px-4 py-3 font-medium">Seniority</th>
                <th className="px-4 py-3 font-medium">Work Model</th>
                <th className="px-4 py-3 font-medium">Location</th>
                <th className="px-4 py-3 font-medium">Posted</th>
                <th className="px-4 py-3 font-medium">Fit</th>
                <th className="px-4 py-3 font-medium">Apply</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={10} className="px-4 py-8 text-center text-muted">Loading...</td>
                </tr>
              ) : jobs.slice(0, 500).map((j) => (
                <tr key={j.id} className="border-b border-card-border/50 hover:bg-white/5">
                  <td className="px-4 py-2.5 font-medium max-w-xs truncate">{j.title}</td>
                  <td className="px-4 py-2.5 text-muted">
                    <Link href={`/companies/${j.company_id}`} className="hover:text-accent-light">
                      {j.company_name}
                    </Link>
                  </td>
                  <td className="px-4 py-2.5 text-muted text-xs">{j.normalized_department || j.department || "—"}</td>
                  <td className="px-4 py-2.5 text-muted text-xs">{formatRoleFamily(j.role_family)}</td>
                  <td className="px-4 py-2.5 text-muted text-xs">{formatSeniority(j.seniority)}</td>
                  <td className="px-4 py-2.5 text-muted text-xs">{formatWorkModel(j.work_model)}</td>
                  <td className="px-4 py-2.5 text-muted text-xs max-w-[140px] truncate">{j.location_city || j.location || "—"}</td>
                  <td className="px-4 py-2.5 text-muted text-xs">
                    {new Date(j.first_seen_at).toLocaleDateString()}
                    <span className="block text-[10px] text-accent-light">{j.posting_status || "active"}</span>
                  </td>
                  <td className="px-4 py-2.5">
                    <Link href={`/fit?jobId=${j.id}`} className="text-accent-light hover:underline text-xs">
                      Compare
                    </Link>
                  </td>
                  <td className="px-4 py-2.5">
                    {j.url ? (
                      <a href={j.url} target="_blank" rel="noopener noreferrer" className="text-accent-light hover:underline text-xs">
                        Apply →
                      </a>
                    ) : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!loading && jobs.length > 500 && (
            <p className="px-4 py-3 text-xs text-muted">
              Showing 500 of {jobs.length.toLocaleString()} results — add filters to narrow down.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
