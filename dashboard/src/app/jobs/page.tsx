"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { api, CompanyRow, JobRow, SkillRow, DepartmentRow, JobFilters, FreshnessRow } from "@/lib/api";
import { formatRoleFamily, formatSeniority, formatWorkModel, FUNDING_ORDER, SENIORITY_LABELS } from "@/lib/format";
import { downloadCSV } from "@/lib/export";
import { MultiValuePicker } from "@/components/MultiValuePicker";
import { ReachOutPanel } from "@/components/outreach/ReachOutPanel";
import { JobStatusPill } from "@/components/JobStatusPill";
import { JobStatus, UserJobStatus } from "@/lib/api";
import { SaveSearchControls } from "@/components/SaveSearchControls";
import { ScoreFilteredJobsPanel } from "@/components/fit/ScoreFilteredJobsPanel";

const WORK_MODELS = ["remote", "hybrid", "onsite"];
const COMPANY_TYPE_OPTIONS = [
  { value: "startup", label: "Startups" },
  { value: "bigco", label: "Big companies" },
];

export default function JobFeedPage() {
  const [jobs, setJobs] = useState<JobRow[]>([]);
  const [skills, setSkills] = useState<SkillRow[]>([]);
  const [departments, setDepartments] = useState<DepartmentRow[]>([]);
  const [freshness, setFreshness] = useState<FreshnessRow[]>([]);
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
  const [reachOutOpen, setReachOutOpen] = useState<Set<number>>(new Set());
  const [jobStatuses, setJobStatuses] = useState<Record<number, JobStatus | null>>({});

  const toggleReachOut = (jobId: number) => {
    setReachOutOpen((prev) => {
      const next = new Set(prev);
      if (next.has(jobId)) next.delete(jobId);
      else next.add(jobId);
      return next;
    });
  };

  useEffect(() => {
    void Promise.all([
      api.skills(undefined, 95),
      api.departments(),
      api.jobFreshness(),
      api.companies(),
      api.jobFilters(),
    ]).then(([skillRows, deptRows, freshRows, companyRows, jobFilterOptions]) => {
      setSkills(skillRows);
      setDepartments(deptRows);
      setFreshness(freshRows);

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

  // Snapshot for /api/saved-searches: just the raw filter inputs as we keep
  // them in React state (so loading round-trips cleanly back into setState).
  type JobsSearchSnapshot = {
    search: string;
    sector: string[];
    empType: string[];
    skill: string[];
    seniority: string[];
    workModel: string[];
    companyType: string[];
    department: string[];
    atsType: string[];
    fundingRound: string[];
  };
  const snapshot: JobsSearchSnapshot = useMemo(() => ({
    search, sector, empType, skill, seniority, workModel,
    companyType, department, atsType, fundingRound,
  }), [search, sector, empType, skill, seniority, workModel, companyType, department, atsType, fundingRound]);

  const applySnapshot = (s: JobsSearchSnapshot) => {
    setSearch(s.search ?? "");
    setSector(s.sector ?? []);
    setEmpType(s.empType ?? []);
    setSkill(s.skill ?? []);
    setSeniority(s.seniority ?? []);
    setWorkModel(s.workModel ?? []);
    setCompanyType(s.companyType ?? []);
    setDepartment(s.department ?? []);
    setAtsType(s.atsType ?? []);
    setFundingRound(s.fundingRound ?? []);
  };

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
        // Batch-fetch user statuses for the visible rows so we can render pills.
        const ids = data.slice(0, 500).map((j) => j.id);
        if (ids.length === 0) return null;
        return api.jobStatusBatch(ids);
      })
      .then((statusMap) => {
        if (!statusMap || cancelled) return;
        const next: Record<number, JobStatus | null> = {};
        for (const [k, v] of Object.entries(statusMap as Record<string, UserJobStatus>)) {
          next[Number(k)] = (v?.status ?? null) as JobStatus | null;
        }
        setJobStatuses(next);
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

      <div className="bg-card border border-card-border rounded-xl p-3">
        <SaveSearchControls
          surface="jobs"
          currentParams={snapshot}
          onLoad={applySnapshot}
        />
      </div>

      <ScoreFilteredJobsPanel jobs={jobs} />

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
              ) : jobs.slice(0, 500).flatMap((j) => [
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
                    <div className="flex flex-col gap-1">
                      <Link href={`/fit?jobId=${j.id}`} className="text-accent-light hover:underline text-xs">
                        Score
                      </Link>
                      <button
                        type="button"
                        onClick={() => toggleReachOut(j.id)}
                        className="text-accent-light hover:underline text-xs text-left"
                      >
                        {reachOutOpen.has(j.id) ? "▾ Reach out" : "▸ Reach out"}
                      </button>
                      <JobStatusPill
                        jobId={j.id}
                        initialStatus={jobStatuses[j.id] ?? null}
                        onChange={(next) =>
                          setJobStatuses((prev) => ({ ...prev, [j.id]: next }))
                        }
                      />
                    </div>
                  </td>
                  <td className="px-4 py-2.5">
                    {j.url ? (
                      <a href={j.url} target="_blank" rel="noopener noreferrer" className="text-accent-light hover:underline text-xs">
                        Apply →
                      </a>
                    ) : "—"}
                  </td>
                </tr>,
                reachOutOpen.has(j.id) && (
                  <tr key={`${j.id}-reach`} className="border-b border-card-border/50 bg-background/50">
                    <td colSpan={10} className="px-4 py-3">
                      <ReachOutPanel jobId={j.id} resumeFile={null} embedded />
                    </td>
                  </tr>
                ),
              ])}
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
