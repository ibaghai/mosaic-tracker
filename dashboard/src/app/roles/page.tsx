"use client";

import { useEffect, useState, useMemo } from "react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell,
} from "recharts";
import { api, SeniorityRow, WorkModelRow, CrossTabRow, DepartmentRow } from "@/lib/api";
import { formatSeniority, formatWorkModel, SENIORITY_LABELS } from "@/lib/format";

const PIE_COLORS = ["#6366f1", "#22c55e", "#f59e0b", "#ef4444", "#8b5cf6", "#06b6d4"];

const SENIORITY_ORDER = Object.keys(SENIORITY_LABELS);

const TOOLTIP_STYLE = {
  contentStyle: { background: "#1a1d27", border: "1px solid #2a2d3a", borderRadius: 8 },
  labelStyle: { color: "#e5e7eb" },
  itemStyle: { color: "#e5e7eb" },
};

type PieLabelProps = {
  name?: string;
  percent?: number;
};

function sortSeniority(data: SeniorityRow[]): SeniorityRow[] {
  return [...data].sort(
    (a, b) => SENIORITY_ORDER.indexOf(a.seniority) - SENIORITY_ORDER.indexOf(b.seniority)
  );
}

// Map raw work_model values to display labels for pie data
function mapWorkModelLabels(data: WorkModelRow[]): Array<{ name: string; count: number }> {
  return data.map((d) => ({ name: formatWorkModel(d.work_model), count: d.count }));
}

const SENIORITY_COLORS: Record<string, string> = {
  "c-level":   "#ec4899",
  "vp":        "#a78bfa",
  "head":      "#8b5cf6",
  "director":  "#6366f1",
  "principal": "#3b82f6",
  "staff":     "#06b6d4",
  "senior":    "#22c55e",
  "lead":      "#84cc16",
  "manager":   "#f59e0b",
  "mid":       "#f97316",
  "junior":    "#fb923c",
  "intern":    "#9ca3af",
};

export default function RolesPage() {
  const [senStartup, setSenStartup] = useState<SeniorityRow[]>([]);
  const [senBigco, setSenBigco] = useState<SeniorityRow[]>([]);
  const [wmStartup, setWmStartup] = useState<Array<{ name: string; count: number }>>([]);
  const [wmBigco, setWmBigco] = useState<Array<{ name: string; count: number }>>([]);
  const [seniorityCross, setSeniorityCross] = useState<CrossTabRow[]>([]);
  const [deptStartup, setDeptStartup] = useState<DepartmentRow[]>([]);
  const [deptBigco, setDeptBigco] = useState<DepartmentRow[]>([]);

  useEffect(() => {
    api.seniority("startup").then((d) => setSenStartup(sortSeniority(d)));
    api.seniority("bigco").then((d) => setSenBigco(sortSeniority(d)));
    api.workModels("startup").then((d) => setWmStartup(mapWorkModelLabels(d)));
    api.workModels("bigco").then((d) => setWmBigco(mapWorkModelLabels(d)));
    api.senioritySectorCross().then(setSeniorityCross);
    api.departments("startup").then(setDeptStartup);
    api.departments("bigco").then(setDeptBigco);
  }, []);

  // Pivot: [{sector, senior: 400, mid: 200, ...}]
  const seniorityCrossData = useMemo(() => {
    const bySector: Record<string, Record<string, number>> = {};
    const levels = new Set<string>();
    seniorityCross.forEach((r) => {
      if (!bySector[r.sector]) bySector[r.sector] = {};
      bySector[r.sector][r.seniority!] = r.job_count;
      levels.add(r.seniority!);
    });
    const orderedLevels = SENIORITY_ORDER.filter((l) => levels.has(l));
    return {
      data: Object.entries(bySector)
              .map(([sector, counts]) => ({ sector, ...counts }))
              .sort((a, b) => {
                const ta = Object.values(a).filter((v) => typeof v === "number").reduce((s, v) => s + (v as number), 0);
                const tb = Object.values(b).filter((v) => typeof v === "number").reduce((s, v) => s + (v as number), 0);
                return (tb as number) - (ta as number);
              }),
      levels: orderedLevels,
    };
  }, [seniorityCross]);

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-2xl font-bold">Roles</h2>
        <p className="text-muted text-sm mt-1">
          Seniority distribution and work model breakdown — Startups vs. Big Tech
        </p>
      </div>

      {/* Seniority */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-card border border-card-border rounded-xl p-5">
          <div className="flex items-center gap-2 mb-4">
            <h3 className="text-sm font-semibold text-muted">Seniority Levels</h3>
            <span className="text-xs px-2 py-0.5 rounded bg-accent/10 text-accent-light border border-accent/20">Startups</span>
          </div>
          <ResponsiveContainer width="100%" height={350}>
            <BarChart data={senStartup} layout="vertical" margin={{ left: 10 }}>
              <XAxis type="number" tick={{ fill: "#9ca3af", fontSize: 12 }} />
              <YAxis
                type="category"
                dataKey="seniority"
                width={90}
                tick={{ fill: "#9ca3af", fontSize: 12 }}
                tickFormatter={formatSeniority}
              />
              <Tooltip {...TOOLTIP_STYLE} formatter={(val) => [val, "Jobs"]} />
              <Bar dataKey="count" fill="#6366f1" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-card border border-card-border rounded-xl p-5">
          <div className="flex items-center gap-2 mb-4">
            <h3 className="text-sm font-semibold text-muted">Seniority Levels</h3>
            <span className="text-xs px-2 py-0.5 rounded bg-purple-500/10 text-purple-400 border border-purple-500/20">Big Tech</span>
          </div>
          <ResponsiveContainer width="100%" height={350}>
            <BarChart data={senBigco} layout="vertical" margin={{ left: 10 }}>
              <XAxis type="number" tick={{ fill: "#9ca3af", fontSize: 12 }} />
              <YAxis
                type="category"
                dataKey="seniority"
                width={90}
                tick={{ fill: "#9ca3af", fontSize: 12 }}
                tickFormatter={formatSeniority}
              />
              <Tooltip {...TOOLTIP_STYLE} formatter={(val) => [val, "Jobs"]} />
              <Bar dataKey="count" fill="#8b5cf6" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Work Model */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-card border border-card-border rounded-xl p-5">
          <div className="flex items-center gap-2 mb-4">
            <h3 className="text-sm font-semibold text-muted">Work Model</h3>
            <span className="text-xs px-2 py-0.5 rounded bg-accent/10 text-accent-light border border-accent/20">Startups</span>
          </div>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={wmStartup}
                cx="50%"
                cy="50%"
                outerRadius={100}
                dataKey="count"
                nameKey="name"
                label={({ name, percent }: PieLabelProps) => `${name ?? ""} ${((percent ?? 0) * 100).toFixed(0)}%`}
                labelLine={false}
              >
                {wmStartup.map((_, i) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
              </Pie>
              <Tooltip {...TOOLTIP_STYLE} />
            </PieChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-card border border-card-border rounded-xl p-5">
          <div className="flex items-center gap-2 mb-4">
            <h3 className="text-sm font-semibold text-muted">Work Model</h3>
            <span className="text-xs px-2 py-0.5 rounded bg-purple-500/10 text-purple-400 border border-purple-500/20">Big Tech</span>
          </div>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={wmBigco}
                cx="50%"
                cy="50%"
                outerRadius={100}
                dataKey="count"
                nameKey="name"
                label={({ name, percent }: PieLabelProps) => `${name ?? ""} ${((percent ?? 0) * 100).toFixed(0)}%`}
                labelLine={false}
              >
                {wmBigco.map((_, i) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
              </Pie>
              <Tooltip {...TOOLTIP_STYLE} />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Department Breakdown */}
      {(deptStartup.length > 0 || deptBigco.length > 0) && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="bg-card border border-card-border rounded-xl p-5">
            <div className="flex items-center gap-2 mb-4">
              <h3 className="text-sm font-semibold text-muted">Department Breakdown</h3>
              <span className="text-xs px-2 py-0.5 rounded bg-accent/10 text-accent-light border border-accent/20">Startups</span>
            </div>
            <ResponsiveContainer width="100%" height={320}>
              <BarChart data={deptStartup} layout="vertical" margin={{ left: 10 }}>
                <XAxis type="number" tick={{ fill: "#9ca3af", fontSize: 12 }} />
                <YAxis
                  type="category"
                  dataKey="category"
                  width={140}
                  tick={{ fill: "#9ca3af", fontSize: 12 }}
                />
                <Tooltip {...TOOLTIP_STYLE} formatter={(val) => [val, "Jobs"]} />
                <Bar dataKey="job_count" fill="#22c55e" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="bg-card border border-card-border rounded-xl p-5">
            <div className="flex items-center gap-2 mb-4">
              <h3 className="text-sm font-semibold text-muted">Department Breakdown</h3>
              <span className="text-xs px-2 py-0.5 rounded bg-purple-500/10 text-purple-400 border border-purple-500/20">Big Tech</span>
            </div>
            <ResponsiveContainer width="100%" height={320}>
              <BarChart data={deptBigco} layout="vertical" margin={{ left: 10 }}>
                <XAxis type="number" tick={{ fill: "#9ca3af", fontSize: 12 }} />
                <YAxis
                  type="category"
                  dataKey="category"
                  width={140}
                  tick={{ fill: "#9ca3af", fontSize: 12 }}
                />
                <Tooltip {...TOOLTIP_STYLE} formatter={(val) => [val, "Jobs"]} />
                <Bar dataKey="job_count" fill="#8b5cf6" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Seniority × Sector Cross-Tab */}
      {seniorityCrossData.data.length > 0 && (
        <div className="bg-card border border-card-border rounded-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-sm font-semibold text-muted">Seniority Mix by Sector</h3>
              <p className="text-xs text-muted mt-0.5">Which sectors hire senior vs. junior talent</p>
            </div>
            <span className="text-xs px-2 py-1 rounded bg-accent/10 text-accent-light border border-accent/20">
              Startups Only
            </span>
          </div>
          <ResponsiveContainer width="100%" height={420}>
            <BarChart data={seniorityCrossData.data} layout="vertical" margin={{ left: 8, right: 16 }}>
              <XAxis type="number" tick={{ fill: "#9ca3af", fontSize: 11 }} />
              <YAxis
                type="category"
                dataKey="sector"
                width={168}
                tick={{ fill: "#9ca3af", fontSize: 11 }}
              />
              <Tooltip
                contentStyle={{ background: "#1a1d27", border: "1px solid #2a2d3a", borderRadius: 8 }}
                labelStyle={{ color: "#e5e7eb" }}
                formatter={(val, name) => [val, formatSeniority(String(name))]}
              />
              {seniorityCrossData.levels.map((level) => (
                <Bar
                  key={level}
                  dataKey={level}
                  stackId="a"
                  fill={SENIORITY_COLORS[level] || "#6b7280"}
                  name={level}
                />
              ))}
            </BarChart>
          </ResponsiveContainer>
          <div className="flex flex-wrap gap-3 mt-4">
            {seniorityCrossData.levels.map((l) => (
              <div key={l} className="flex items-center gap-1.5 text-xs text-muted">
                <div className="w-2.5 h-2.5 rounded-full" style={{ background: SENIORITY_COLORS[l] || "#6b7280" }} />
                {formatSeniority(l)}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
