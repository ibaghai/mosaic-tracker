"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { api, JobRow, SkillRow, DepartmentRow, JobFilters, FreshnessRow } from "@/lib/api";
import { formatRoleFamily, formatSeniority, formatWorkModel, SENIORITY_LABELS } from "@/lib/format";
import { downloadCSV } from "@/lib/export";

const WORK_MODELS = ["remote", "hybrid", "onsite"];

export default function JobFeedPage() {
  const [jobs, setJobs] = useState<JobRow[]>([]);
  const [skills, setSkills] = useState<SkillRow[]>([]);
  const [departments, setDepartments] = useState<DepartmentRow[]>([]);
  const [freshness, setFreshness] = useState<FreshnessRow[]>([]);
  const [loading, setLoading] = useState(false);

  // Filters
  const [search, setSearch] = useState("");
  const [sector, setSector] = useState("");
  const [empType, setEmpType] = useState("");
  const [skill, setSkill] = useState("");
  const [seniority, setSeniority] = useState("");
  const [workModel, setWorkModel] = useState("");
  const [companyType, setCompanyType] = useState("");
  const [department, setDepartment] = useState("");

  useEffect(() => {
    void api.skills(undefined, 95).then(setSkills);
    void api.departments().then(setDepartments);
    void api.jobFreshness().then(setFreshness);
  }, []);

  const filters = useMemo((): JobFilters => ({
    search: search || undefined,
    sector: sector || undefined,
    employment_type: empType || undefined,
    skill: skill || undefined,
    seniority: seniority || undefined,
    work_model: workModel || undefined,
    company_type: companyType || undefined,
    department: department || undefined,
  }), [search, sector, empType, skill, seniority, workModel, companyType, department]);

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

  const sectors = useMemo(
    () => [...new Set(jobs.map((j) => j.sector).filter(Boolean))].sort(),
    [jobs]
  );

  const empTypes = useMemo(
    () => [...new Set(jobs.map((j) => j.employment_type).filter((t): t is string => Boolean(t)))].sort(),
    [jobs]
  );

  const activeFilters = [search, sector, empType, skill, seniority, workModel, companyType, department].filter(Boolean).length;

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
          <select
            value={sector}
            onChange={(e) => setSector(e.target.value)}
            className="bg-background border border-card-border rounded-lg px-3 py-2 text-sm text-foreground"
          >
            <option value="">All Sectors</option>
            {sectors.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
          <select
            value={companyType}
            onChange={(e) => setCompanyType(e.target.value)}
            className="bg-background border border-card-border rounded-lg px-3 py-2 text-sm text-foreground"
          >
            <option value="">Both</option>
            <option value="startup">Startups</option>
            <option value="bigco">Big companies</option>
          </select>
        </div>
        <div className="flex flex-wrap gap-3">
          <select
            value={department}
            onChange={(e) => setDepartment(e.target.value)}
            className="bg-background border border-card-border rounded-lg px-3 py-2 text-sm text-foreground"
          >
            <option value="">All Departments</option>
            {departments.map((d) => <option key={d.category} value={d.category}>{d.category} ({d.job_count.toLocaleString()})</option>)}
          </select>
          <select
            value={skill}
            onChange={(e) => setSkill(e.target.value)}
            className="bg-background border border-card-border rounded-lg px-3 py-2 text-sm text-foreground"
          >
            <option value="">Any Skill</option>
            {skills.map((s) => <option key={s.skill} value={s.skill}>{s.skill} ({s.count})</option>)}
          </select>
          <select
            value={seniority}
            onChange={(e) => setSeniority(e.target.value)}
            className="bg-background border border-card-border rounded-lg px-3 py-2 text-sm text-foreground"
          >
            <option value="">Any Seniority</option>
            {Object.entries(SENIORITY_LABELS).map(([val, label]) => (
              <option key={val} value={val}>{label}</option>
            ))}
          </select>
          <select
            value={workModel}
            onChange={(e) => setWorkModel(e.target.value)}
            className="bg-background border border-card-border rounded-lg px-3 py-2 text-sm text-foreground"
          >
            <option value="">Any Work Model</option>
            {WORK_MODELS.map((m) => (
              <option key={m} value={m}>{formatWorkModel(m)}</option>
            ))}
          </select>
          <select
            value={empType}
            onChange={(e) => setEmpType(e.target.value)}
            className="bg-background border border-card-border rounded-lg px-3 py-2 text-sm text-foreground"
          >
            <option value="">All Employment Types</option>
            {empTypes.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
          {activeFilters > 0 && (
            <button
              onClick={() => { setSearch(""); setSector(""); setEmpType(""); setSkill(""); setSeniority(""); setWorkModel(""); setCompanyType(""); setDepartment(""); }}
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
