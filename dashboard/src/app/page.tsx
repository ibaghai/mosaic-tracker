"use client";

import { useEffect, useState } from "react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
  PieChart, Pie, Legend,
} from "recharts";
import { api, OverviewStats, SectorRow, DepartmentRow, RoleFamilyRow, FreshnessRow } from "@/lib/api";
import { formatRoleFamily } from "@/lib/format";

const COLORS = [
  "#6366f1", "#818cf8", "#a5b4fc", "#8b5cf6", "#a78bfa",
  "#c084fc", "#6d28d9", "#4f46e5", "#7c3aed", "#5b21b6",
  "#4338ca", "#3730a3", "#312e81", "#4c1d95", "#2e1065",
];

const TOOLTIP_STYLE = {
  contentStyle: { background: "#1a1d27", border: "1px solid #2a2d3a", borderRadius: 8 },
  labelStyle: { color: "#e5e7eb" },
  itemStyle: { color: "#e5e7eb" },
};

function KpiCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="bg-card border border-card-border rounded-xl p-5">
      <p className="text-sm text-muted">{label}</p>
      <p className="text-2xl font-bold mt-1">
        {typeof value === "number" ? value.toLocaleString() : value}
      </p>
      {sub && <p className="text-xs text-muted mt-1">{sub}</p>}
    </div>
  );
}

type Scope = "startup" | "all";

export default function PulsePage() {
  const [overview, setOverview] = useState<OverviewStats | null>(null);
  const [sectors, setSectors] = useState<SectorRow[]>([]);
  const [departments, setDepartments] = useState<DepartmentRow[]>([]);
  const [roleFamilies, setRoleFamilies] = useState<RoleFamilyRow[]>([]);
  const [freshness, setFreshness] = useState<FreshnessRow[]>([]);
  const [scope, setScope] = useState<Scope>("startup");
  const [deptView, setDeptView] = useState<"bar" | "pie">("bar");

  useEffect(() => {
    const ct = scope === "startup" ? "startup" : undefined;
    api.overview(ct).then(setOverview);
    api.sectors().then(setSectors);
    api.departments(ct).then(setDepartments);
    api.roleFamilies(ct).then(setRoleFamilies);
    api.jobFreshness(ct).then(setFreshness);
  }, [scope]);

  if (!overview) return <div className="text-muted">Loading...</div>;

  const net = overview.net_added - overview.net_removed;

  return (
    <div className="space-y-8">
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-2xl font-bold">Pulse</h2>
          <p className="text-muted text-sm mt-1">Startup hiring market at a glance</p>
        </div>
        <div className="flex gap-1 bg-card border border-card-border rounded-lg p-1">
          {(["startup", "all"] as Scope[]).map((s) => (
            <button
              key={s}
              onClick={() => setScope(s)}
              className={`px-3 py-1 text-xs rounded transition-colors ${
                scope === s ? "bg-accent text-white" : "text-muted hover:text-foreground"
              }`}
            >
              {s === "startup" ? "Startups Only" : "All Companies"}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KpiCard label={scope === "startup" ? "Startups Tracked" : "Companies Tracked"} value={overview.total_companies} />
        <KpiCard
          label="Active Jobs"
          value={overview.total_active_jobs}
          sub={net !== 0 ? `${net > 0 ? "+" : ""}${net.toLocaleString()} since last update` : undefined}
        />
        <KpiCard label="New This Week" value={overview.net_added} />
        <KpiCard label="Closed This Week" value={overview.net_removed} />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-card border border-card-border rounded-xl p-5">
          <h3 className="text-sm font-semibold text-muted mb-4">Active Jobs by Sector</h3>
          <ResponsiveContainer width="100%" height={360}>
            <BarChart data={sectors} layout="vertical" margin={{ left: 20 }}>
              <XAxis type="number" tick={{ fill: "#9ca3af", fontSize: 12 }} />
              <YAxis type="category" dataKey="sector" width={160} tick={{ fill: "#9ca3af", fontSize: 12 }} />
              <Tooltip {...TOOLTIP_STYLE} />
              <Bar dataKey="job_count" radius={[0, 4, 4, 0]}>
                {sectors.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-card border border-card-border rounded-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-muted">
              Active Jobs by Department
              {scope === "startup" && <span className="text-accent-light ml-2 font-normal">· Startups</span>}
            </h3>
            <div className="flex gap-1 bg-background border border-card-border rounded-lg p-0.5">
              {(["bar", "pie"] as const).map((v) => (
                <button
                  key={v}
                  onClick={() => setDeptView(v)}
                  className={`px-2.5 py-1 text-xs rounded transition-colors ${deptView === v ? "bg-accent text-white" : "text-muted hover:text-foreground"}`}
                >
                  {v === "bar" ? "Bar" : "Pie"}
                </button>
              ))}
            </div>
          </div>
          {deptView === "bar" ? (
            <ResponsiveContainer width="100%" height={360}>
              <BarChart data={departments} layout="vertical" margin={{ left: 20 }}>
                <XAxis type="number" tick={{ fill: "#9ca3af", fontSize: 12 }} />
                <YAxis type="category" dataKey="category" width={140} tick={{ fill: "#9ca3af", fontSize: 12 }} />
                <Tooltip {...TOOLTIP_STYLE} />
                <Bar dataKey="job_count" fill="#6366f1" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <ResponsiveContainer width="100%" height={360}>
              <PieChart>
                <Pie
                  data={departments}
                  dataKey="job_count"
                  nameKey="category"
                  cx="50%"
                  cy="45%"
                  outerRadius={120}
                  label={false}
                >
                  {departments.map((_, i) => (
                    <Cell key={i} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip {...TOOLTIP_STYLE} formatter={(v) => [v, "Jobs"]} />
                <Legend
                  layout="vertical"
                  align="right"
                  verticalAlign="middle"
                  iconSize={8}
                  formatter={(val) => <span style={{ color: "#9ca3af", fontSize: 11 }}>{val}</span>}
                />
              </PieChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-card border border-card-border rounded-xl p-5">
          <h3 className="text-sm font-semibold text-muted mb-4">Active Jobs by Role Family</h3>
          <ResponsiveContainer width="100%" height={320}>
            <BarChart data={roleFamilies.slice(0, 8)} layout="vertical" margin={{ left: 20 }}>
              <XAxis type="number" tick={{ fill: "#9ca3af", fontSize: 12 }} />
              <YAxis
                type="category"
                dataKey="role_family"
                width={160}
                tick={{ fill: "#9ca3af", fontSize: 12 }}
                tickFormatter={formatRoleFamily}
              />
              <Tooltip
                {...TOOLTIP_STYLE}
                formatter={(value) => [value, "Jobs"]}
                labelFormatter={(label) => formatRoleFamily(String(label))}
              />
              <Bar dataKey="count" fill="#22c55e" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-card border border-card-border rounded-xl p-5">
          <h3 className="text-sm font-semibold text-muted mb-4">Job Freshness</h3>
          <ResponsiveContainer width="100%" height={320}>
            <BarChart data={freshness}>
              <XAxis dataKey="bucket" tick={{ fill: "#9ca3af", fontSize: 12 }} />
              <YAxis tick={{ fill: "#9ca3af", fontSize: 12 }} />
              <Tooltip {...TOOLTIP_STYLE} formatter={(value) => [value, "Jobs"]} />
              <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                {freshness.map((_, i) => <Cell key={i} fill={COLORS[(i + 4) % COLORS.length]} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <p className="text-xs text-muted">
        Updated: {overview.last_run ? new Date(overview.last_run).toLocaleString() : "Never"}
      </p>
    </div>
  );
}
