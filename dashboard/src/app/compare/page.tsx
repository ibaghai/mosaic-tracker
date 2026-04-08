"use client";

import { useEffect, useState, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend,
} from "recharts";
import { api, CompanyDetail } from "@/lib/api";
import { formatSeniority, fundingBadgeColor, SENIORITY_LABELS } from "@/lib/format";

const DEPT_COLORS = [
  "#6366f1", "#22c55e", "#f59e0b", "#ec4899", "#06b6d4",
  "#8b5cf6", "#f97316", "#14b8a6", "#a78bfa", "#fb923c",
];

const SENIORITY_ORDER = Object.keys(SENIORITY_LABELS);

const COMPANY_ACCENT = ["#6366f1", "#22c55e", "#f59e0b"];

const TOOLTIP_STYLE = {
  contentStyle: { background: "#1a1d27", border: "1px solid #2a2d3a", borderRadius: 8 },
  labelStyle: { color: "#e5e7eb" },
  itemStyle: { color: "#e5e7eb" },
};

export default function ComparePage() {
  return (
    <Suspense fallback={<div className="text-muted text-sm">Loading...</div>}>
      <CompareInner />
    </Suspense>
  );
}

function CompareInner() {
  const params = useSearchParams();
  const ids = (params.get("ids") || "").split(",").map(Number).filter(Boolean).slice(0, 3);

  const [companies, setCompanies] = useState<CompanyDetail[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!ids.length) { setLoading(false); return; }
    Promise.all(ids.map((id) => api.companyDetail(id))).then((results) => {
      setCompanies(results);
      setLoading(false);
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.get("ids")]);

  if (loading) {
    return <div className="text-muted text-sm">Loading comparison...</div>;
  }

  if (!ids.length || !companies.length) {
    return (
      <div className="space-y-4">
        <Link href="/companies" className="text-sm text-muted hover:text-foreground">← Back to Companies</Link>
        <p className="text-muted">Select up to 3 companies from the Companies page to compare them.</p>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <div className="flex items-center gap-4">
        <Link href="/companies" className="text-sm text-muted hover:text-foreground">← Back</Link>
        <h2 className="text-2xl font-bold">Compare</h2>
        <span className="text-muted text-sm">{companies.length} companies</span>
      </div>

      {/* Header cards */}
      <div className="flex gap-4 overflow-x-auto pb-1">
        {companies.map((c, i) => (
          <div key={c.id} className="bg-card border border-card-border rounded-xl p-5 flex-none min-w-64 flex-1" style={{ borderTopColor: COMPANY_ACCENT[i], borderTopWidth: 3 }}>
            <Link href={`/companies/${c.id}`} className="font-bold text-lg hover:text-accent-light block truncate">{c.name}</Link>
            <p className="text-muted text-xs mt-0.5">{c.sector}</p>
            {c.funding_round && (
              <span className={`inline-block mt-2 text-xs px-1.5 py-0.5 rounded font-medium ${fundingBadgeColor(c.funding_round)}`}>
                {c.funding_round}
              </span>
            )}
            <div className="grid grid-cols-2 gap-3 mt-4">
              <div>
                <p className="text-xs text-muted">Active Jobs</p>
                <p className="text-xl font-bold font-mono mt-0.5">{c.active_jobs.toLocaleString()}</p>
              </div>
              <div>
                <p className="text-xs text-muted">Total Added</p>
                <p className="text-xl font-bold font-mono text-green mt-0.5">+{c.total_added.toLocaleString()}</p>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Department breakdown */}
      <div>
        <h3 className="text-sm font-semibold text-muted mb-4">Department Breakdown</h3>
        <div className="flex gap-4 overflow-x-auto pb-1">
          {companies.map((c, ci) => (
            <div key={c.id} className="bg-card border border-card-border rounded-xl p-4 flex-none min-w-64 flex-1">
              <p className="text-xs font-medium mb-3" style={{ color: COMPANY_ACCENT[ci] }}>{c.name}</p>
              {c.departments.length === 0 ? (
                <p className="text-muted text-xs">No data</p>
              ) : (
                <ResponsiveContainer width="100%" height={180}>
                  <PieChart>
                    <Pie data={c.departments} dataKey="job_count" nameKey="category" cx="50%" cy="50%" outerRadius={70} label={false}>
                      {c.departments.map((_, i) => <Cell key={i} fill={DEPT_COLORS[i % DEPT_COLORS.length]} />)}
                    </Pie>
                    <Tooltip {...TOOLTIP_STYLE} />
                    <Legend iconSize={8} formatter={(val) => <span style={{ color: "#9ca3af", fontSize: 10 }}>{val}</span>} />
                  </PieChart>
                </ResponsiveContainer>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Seniority distribution */}
      <div>
        <h3 className="text-sm font-semibold text-muted mb-4">Seniority Distribution</h3>
        <div className="flex gap-4 overflow-x-auto pb-1">
          {companies.map((c, ci) => (
            <div key={c.id} className="bg-card border border-card-border rounded-xl p-4 flex-none min-w-64 flex-1">
              <p className="text-xs font-medium mb-3" style={{ color: COMPANY_ACCENT[ci] }}>{c.name}</p>
              <p className="text-xs text-muted">
                Visit the{" "}
                <Link href={`/companies/${c.id}`} className="text-accent-light hover:underline">
                  company page
                </Link>{" "}
                for full seniority breakdown.
              </p>
            </div>
          ))}
        </div>
      </div>

      {/* Top Skills */}
      <div>
        <h3 className="text-sm font-semibold text-muted mb-4">Top Skills</h3>
        <div className="flex gap-4 overflow-x-auto pb-1">
          {companies.map((c, ci) => (
            <div key={c.id} className="bg-card border border-card-border rounded-xl p-4 flex-none min-w-64 flex-1">
              <p className="text-xs font-medium mb-3" style={{ color: COMPANY_ACCENT[ci] }}>{c.name}</p>
              {c.top_skills.length === 0 ? (
                <p className="text-muted text-xs">No skill data</p>
              ) : (
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart
                    data={c.top_skills.slice(0, 8)}
                    layout="vertical"
                    margin={{ left: 0, right: 8 }}
                  >
                    <XAxis type="number" tick={{ fill: "#9ca3af", fontSize: 10 }} />
                    <YAxis type="category" dataKey="skill" width={80} tick={{ fill: "#9ca3af", fontSize: 10 }} />
                    <Tooltip {...TOOLTIP_STYLE} />
                    <Bar dataKey="count" fill={COMPANY_ACCENT[ci]} radius={[0, 3, 3, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
