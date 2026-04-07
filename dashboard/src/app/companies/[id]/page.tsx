"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend,
} from "recharts";
import { api, CompanyDetail, JobRow, JobEvent } from "@/lib/api";
import { formatSeniority, formatWorkModel, formatDate, formatMoney, SENIORITY_LABELS } from "@/lib/format";

const DEPT_COLORS = [
  "#6366f1", "#8b5cf6", "#ec4899", "#f59e0b", "#10b981",
  "#3b82f6", "#ef4444", "#14b8a6", "#f97316", "#a855f7",
];

const ATS_LABELS: Record<string, string> = {
  greenhouse: "Greenhouse",
  ashby: "Ashby",
  lever: "Lever",
  workday: "Workday",
  icims: "iCIMS",
  smartrecruiters: "SmartRecruiters",
  jobvite: "Jobvite",
};

export default function CompanyDetailPage() {
  const params = useParams();
  const id = Number(params.id);

  const [detail, setDetail] = useState<CompanyDetail | null>(null);
  const [jobs, setJobs] = useState<JobRow[]>([]);
  const [events, setEvents] = useState<JobEvent[]>([]);
  const [velocity, setVelocity] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [jobSearch, setJobSearch] = useState("");

  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    void Promise.resolve()
      .then(() => {
        if (!cancelled) setLoading(true);
        return Promise.all([
          api.companyDetail(id),
          api.jobs({ company_id: id }),
          api.companyVelocity(7),
        ]);
      })
      .then(([det, jobList, vel]) => {
        if (cancelled) return null;
        setDetail(det);
        setJobs(jobList);
        const v = vel.find((r) => r.company_id === id);
        setVelocity(v ? v.net : 0);
        return api.changeEvents({ company_name: det.name, limit: 20 });
      })
      .then((evts) => {
        if (!cancelled && evts) {
          setEvents(evts);
          setLoading(false);
        }
      })
      .catch(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [id]);

  const filteredJobs = jobSearch
    ? jobs.filter((j) => j.title.toLowerCase().includes(jobSearch.toLowerCase()))
    : jobs;

  // Build seniority chart data from active jobs
  const seniorityCounts = jobs.reduce<Record<string, number>>((acc, j) => {
    const s = j.seniority || "unknown";
    acc[s] = (acc[s] || 0) + 1;
    return acc;
  }, {});

  const seniorityData = Object.entries(SENIORITY_LABELS)
    .map(([key]) => ({ seniority: key, count: seniorityCounts[key] || 0 }))
    .filter((d) => d.count > 0)
    .sort((a, b) => b.count - a.count);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64 text-muted text-sm">
        Loading company data...
      </div>
    );
  }

  if (!detail) {
    return (
      <div className="space-y-4">
        <Link href="/companies" className="text-sm text-muted hover:text-foreground">← Back to Companies</Link>
        <p className="text-muted">Company not found.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Back nav */}
      <Link href="/companies" className="text-sm text-muted hover:text-foreground inline-flex items-center gap-1">
        ← Back to Companies
      </Link>

      {/* Header */}
      <div className="bg-card border border-card-border rounded-xl p-6">
        <div className="flex items-start justify-between flex-wrap gap-4">
          <div>
            <div className="flex items-center gap-3 flex-wrap">
              <h2 className="text-2xl font-bold">{detail.name}</h2>
              {detail.company_type === "bigco" && (
                <span className="text-xs bg-card-border text-muted px-2 py-0.5 rounded">Big Tech</span>
              )}
              {detail.ats_type && (
                <span className="text-xs bg-accent/10 text-accent-light px-2 py-0.5 rounded border border-accent/20">
                  {ATS_LABELS[detail.ats_type] ?? detail.ats_type}
                </span>
              )}
            </div>
            <p className="text-muted text-sm mt-1">{detail.sector}</p>
          </div>
          <div className="flex flex-col items-end gap-1">
            {detail.website && (
              <a
                href={detail.website.startsWith("http") ? detail.website : `https://${detail.website}`}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm text-accent-light hover:underline"
              >
                {detail.website.replace(/^https?:\/\//, "")} →
              </a>
            )}
            {detail.funding_round && (
              <span className="text-xs text-muted">
                {detail.funding_round}{detail.funding_amount_m ? ` · ${formatMoney(detail.funding_amount_m)}` : ""}
                {detail.funding_date ? ` · ${new Date(detail.funding_date).getFullYear()}` : ""}
              </span>
            )}
          </div>
        </div>
      </div>

      {/* KPI row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="bg-card border border-card-border rounded-xl p-4">
          <p className="text-xs text-muted mb-1">Active Jobs</p>
          <p className="text-2xl font-bold font-mono">{detail.active_jobs.toLocaleString()}</p>
        </div>
        <div className="bg-card border border-card-border rounded-xl p-4">
          <p className="text-xs text-muted mb-1">7-Day Change</p>
          <p className={`text-2xl font-bold font-mono ${velocity === null ? "text-muted" : velocity > 0 ? "text-green" : velocity < 0 ? "text-red" : "text-muted"}`}>
            {velocity === null ? "—" : velocity > 0 ? `+${velocity}` : velocity}
          </p>
        </div>
        <div className="bg-card border border-card-border rounded-xl p-4">
          <p className="text-xs text-muted mb-1">Total Added</p>
          <p className="text-2xl font-bold font-mono text-green">{detail.total_added.toLocaleString()}</p>
        </div>
        <div className="bg-card border border-card-border rounded-xl p-4">
          <p className="text-xs text-muted mb-1">Total Removed</p>
          <p className="text-2xl font-bold font-mono text-red">{detail.total_removed.toLocaleString()}</p>
        </div>
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Department Breakdown */}
        {detail.departments.length > 0 && (
          <div className="bg-card border border-card-border rounded-xl p-5">
            <h3 className="text-sm font-semibold mb-4">Department Breakdown</h3>
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie
                  data={detail.departments}
                  dataKey="job_count"
                  nameKey="category"
                  cx="40%"
                  cy="50%"
                  outerRadius={80}
                  label={false}
                >
                  {detail.departments.map((_, i) => (
                    <Cell key={i} fill={DEPT_COLORS[i % DEPT_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{ background: "var(--color-card)", border: "1px solid var(--color-card-border)", borderRadius: "8px" }}
                  formatter={(val, name) => [val, name]}
                />
                <Legend
                  layout="vertical"
                  align="right"
                  verticalAlign="middle"
                  iconSize={8}
                  formatter={(val) => <span className="text-xs text-muted">{val}</span>}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Seniority Distribution */}
        {seniorityData.length > 0 && (
          <div className="bg-card border border-card-border rounded-xl p-5">
            <h3 className="text-sm font-semibold mb-4">Seniority Distribution</h3>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={seniorityData} layout="vertical" margin={{ left: 8, right: 16, top: 0, bottom: 0 }}>
                <XAxis type="number" tick={{ fontSize: 11 }} stroke="var(--color-muted)" />
                <YAxis
                  type="category"
                  dataKey="seniority"
                  tick={{ fontSize: 11 }}
                  stroke="var(--color-muted)"
                  width={72}
                  tickFormatter={formatSeniority}
                />
                <Tooltip
                  contentStyle={{ background: "var(--color-card)", border: "1px solid var(--color-card-border)", borderRadius: "8px" }}
                  formatter={(val) => [val, "Jobs"]}
                  labelFormatter={(label) => formatSeniority(String(label))}
                />
                <Bar dataKey="count" fill="#6366f1" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {/* Top Skills */}
      {detail.top_skills.length > 0 && (
        <div className="bg-card border border-card-border rounded-xl p-5">
          <h3 className="text-sm font-semibold mb-4">Top Skills in Job Listings</h3>
          <div className="flex flex-wrap gap-2">
            {detail.top_skills.map((s) => (
              <span key={s.skill} className="flex items-center gap-1.5 px-3 py-1.5 bg-background border border-card-border rounded-full text-xs">
                <span className="font-medium text-foreground">{s.skill}</span>
                <span className="text-muted">{s.count}</span>
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Recent Activity */}
      {events.length > 0 && (
        <div className="bg-card border border-card-border rounded-xl p-5">
          <h3 className="text-sm font-semibold mb-4">Recent Activity</h3>
          <div className="space-y-1 max-h-64 overflow-y-auto">
            {events.map((e, i) => (
              <div key={i} className="flex items-start gap-3 py-2 border-b border-card-border/40 last:border-0">
                <span className={`text-xs px-2 py-0.5 rounded font-medium mt-0.5 shrink-0 ${
                  e.event_type === "added" ? "bg-green/10 text-green" : "bg-red/10 text-red"
                }`}>
                  {e.event_type === "added" ? "Opened" : "Closed"}
                </span>
                <div className="min-w-0">
                  <p className="text-sm font-medium truncate">{e.title}</p>
                  <p className="text-xs text-muted">
                    {e.normalized_department || e.department || "—"}
                    {e.location ? ` · ${e.location}` : ""}
                    <span className="ml-2">{formatDate(e.created_at)}</span>
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Active Job Listings */}
      <div className="bg-card border border-card-border rounded-xl overflow-hidden">
        <div className="px-5 py-4 flex items-center justify-between border-b border-card-border">
          <h3 className="text-sm font-semibold">
            Active Job Listings
            <span className="ml-2 text-muted font-normal">({jobs.length.toLocaleString()})</span>
          </h3>
          <input
            type="text"
            placeholder="Filter by title..."
            value={jobSearch}
            onChange={(e) => setJobSearch(e.target.value)}
            className="bg-background border border-card-border rounded-lg px-3 py-1.5 text-xs text-foreground w-48"
          />
        </div>
        <div className="max-h-[50vh] overflow-y-auto">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-card z-10">
              <tr className="text-muted text-left border-b border-card-border">
                <th className="px-4 py-3 font-medium">Title</th>
                <th className="px-4 py-3 font-medium">Department</th>
                <th className="px-4 py-3 font-medium">Seniority</th>
                <th className="px-4 py-3 font-medium">Work Model</th>
                <th className="px-4 py-3 font-medium">Location</th>
                <th className="px-4 py-3 font-medium">Posted</th>
                <th className="px-4 py-3 font-medium">Apply</th>
              </tr>
            </thead>
            <tbody>
              {filteredJobs.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-muted text-xs">No jobs found</td>
                </tr>
              ) : filteredJobs.map((j) => (
                <tr key={j.id} className="border-b border-card-border/50 hover:bg-white/5">
                  <td className="px-4 py-2.5 font-medium max-w-xs truncate">{j.title}</td>
                  <td className="px-4 py-2.5 text-muted text-xs">{j.normalized_department || j.department || "—"}</td>
                  <td className="px-4 py-2.5 text-muted text-xs">{formatSeniority(j.seniority)}</td>
                  <td className="px-4 py-2.5 text-muted text-xs">{formatWorkModel(j.work_model)}</td>
                  <td className="px-4 py-2.5 text-muted text-xs max-w-[140px] truncate">{j.location || "—"}</td>
                  <td className="px-4 py-2.5 text-muted text-xs">{new Date(j.first_seen_at).toLocaleDateString()}</td>
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
        </div>
      </div>

      {/* Footer metadata */}
      <p className="text-xs text-muted">
        Updated: {formatDate(detail.last_scraped)}
      </p>
    </div>
  );
}
