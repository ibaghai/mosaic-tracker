"use client";

import { useEffect, useState, useMemo } from "react";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, AreaChart, Area,
  BarChart, Bar,
} from "recharts";
import { api, TrendRow, CrossTabRow } from "@/lib/api";
import { formatWorkModel } from "@/lib/format";

const SECTOR_COLORS: Record<string, string> = {
  "AI & Machine Learning":       "#6366f1",
  "Dev Tools & Infrastructure":  "#8b5cf6",
  "Security":                    "#ec4899",
  "Enterprise Software":         "#f59e0b",
  "Data & Analytics":            "#22c55e",
  "Fintech & Payments":          "#06b6d4",
  "Cloud & Infrastructure":      "#3b82f6",
  "Health & Wellness":           "#ef4444",
  "Climate & Energy":            "#14b8a6",
  "Robotics & Hardware":         "#f97316",
  "Communications & Identity":   "#a78bfa",
  "Consumer & Marketplace":      "#fb923c",
  "HR & Workforce":              "#34d399",
  "Logistics & Operations":      "#f472b6",
};

const TOOLTIP_STYLE = {
  contentStyle: { background: "#1a1d27", border: "1px solid #2a2d3a", borderRadius: 8 },
  labelStyle: { color: "#e5e7eb" },
  itemStyle: { color: "#e5e7eb" },
};

const DEPT_COLORS: Record<string, string> = {
  "Engineering":        "#6366f1",
  "Go-to-Market":       "#22c55e",
  "Operations":         "#f59e0b",
  "Marketing":          "#ec4899",
  "Data & Analytics":   "#06b6d4",
  "Product":            "#8b5cf6",
  "Design":             "#f97316",
  "Finance":            "#14b8a6",
  "HR & People":        "#a78bfa",
  "Customer Success":   "#fb923c",
  "Support":            "#34d399",
  "Legal":              "#f472b6",
  "Security":           "#ef4444",
  "Research":           "#3b82f6",
};

export default function TrendsPage() {
  const [raw, setRaw] = useState<TrendRow[]>([]);
  const [crossTab, setCrossTab] = useState<CrossTabRow[]>([]);
  const [remoteMix, setRemoteMix] = useState<CrossTabRow[]>([]);

  useEffect(() => {
    api.jobTrends().then(setRaw);
    api.deptSectorCross().then(setCrossTab);
    api.remoteSectorCross("startup").then(setRemoteMix);
  }, []);

  const hiringIndex = useMemo(() => {
    const byDate: Record<string, number> = {};
    raw.forEach((r) => { byDate[r.date] = (byDate[r.date] || 0) + r.job_count; });
    return Object.entries(byDate)
      .map(([date, total]) => ({ date, total }))
      .sort((a, b) => a.date.localeCompare(b.date));
  }, [raw]);

  const sectorTrends = useMemo(() => {
    const byDateSector: Record<string, Record<string, number>> = {};
    const allSectors = new Set<string>();
    raw.forEach((r) => {
      if (!byDateSector[r.date]) byDateSector[r.date] = {};
      byDateSector[r.date][r.sector] = (byDateSector[r.date][r.sector] || 0) + r.job_count;
      allSectors.add(r.sector);
    });
    const sectors = Array.from(allSectors);
    const data = Object.entries(byDateSector)
      .map(([date, counts]) => ({ date, ...counts }))
      .sort((a, b) => a.date.localeCompare(b.date));
    return { data, sectors };
  }, [raw]);

  // Pivot cross-tab: [{sector, Engineering: 120, Marketing: 40, ...}]
  const deptSectorData = useMemo(() => {
    const bySector: Record<string, Record<string, number>> = {};
    const depts = new Set<string>();
    crossTab.forEach((r) => {
      if (!bySector[r.sector]) bySector[r.sector] = {};
      bySector[r.sector][r.department!] = r.job_count;
      depts.add(r.department!);
    });
    return {
      data: Object.entries(bySector).map(([sector, counts]) => ({ sector, ...counts }))
               .sort((a, b) => {
                 const ta = Object.values(a).filter((v) => typeof v === "number").reduce((s, v) => s + (v as number), 0);
                 const tb = Object.values(b).filter((v) => typeof v === "number").reduce((s, v) => s + (v as number), 0);
                 return (tb as number) - (ta as number);
               }),
      depts: Array.from(depts),
    };
  }, [crossTab]);

  const remoteSectorData = useMemo(() => {
    const bySector: Record<string, Record<string, number>> = {};
    remoteMix.forEach((r) => {
      if (!bySector[r.sector]) bySector[r.sector] = {};
      if (r.work_model) bySector[r.sector][r.work_model] = r.job_count;
    });
    return Object.entries(bySector)
      .map(([sector, counts]) => ({
        sector,
        remote: counts.remote || 0,
        hybrid: counts.hybrid || 0,
        onsite: counts.onsite || 0,
        total: (counts.remote || 0) + (counts.hybrid || 0) + (counts.onsite || 0),
      }))
      .sort((a, b) => b.total - a.total)
      .slice(0, 10);
  }, [remoteMix]);

  if (!raw.length) return <div className="text-muted">Loading...</div>;

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-2xl font-bold">Trends</h2>
        <p className="text-muted text-sm mt-1">
          Hiring velocity over time —{" "}
          <span className="text-accent-light">Startups only</span>
        </p>
      </div>

      <div className="bg-card border border-card-border rounded-xl p-5">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-muted">Startup Hiring Index — Total Active Jobs</h3>
          <span className="text-xs px-2 py-1 rounded bg-accent/10 text-accent-light border border-accent/20">
            Startups Only
          </span>
        </div>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={hiringIndex}>
            <XAxis dataKey="date" tick={{ fill: "#9ca3af", fontSize: 12 }} />
            <YAxis tick={{ fill: "#9ca3af", fontSize: 12 }} />
            <Tooltip {...TOOLTIP_STYLE} />
            <Line type="monotone" dataKey="total" stroke="#6366f1" strokeWidth={2} dot={true} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="bg-card border border-card-border rounded-xl p-5">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-muted">Active Jobs by Sector Over Time</h3>
          <span className="text-xs px-2 py-1 rounded bg-accent/10 text-accent-light border border-accent/20">
            Startups Only
          </span>
        </div>
        <ResponsiveContainer width="100%" height={400}>
          <AreaChart data={sectorTrends.data}>
            <XAxis dataKey="date" tick={{ fill: "#9ca3af", fontSize: 12 }} />
            <YAxis tick={{ fill: "#9ca3af", fontSize: 12 }} />
            <Tooltip {...TOOLTIP_STYLE} />
            {sectorTrends.sectors.map((sector) => (
              <Area
                key={sector}
                type="monotone"
                dataKey={sector}
                stackId="1"
                fill={SECTOR_COLORS[sector] || "#6b7280"}
                stroke={SECTOR_COLORS[sector] || "#6b7280"}
                fillOpacity={0.6}
              />
            ))}
          </AreaChart>
        </ResponsiveContainer>
        <div className="flex flex-wrap gap-3 mt-4">
          {sectorTrends.sectors.map((s) => (
            <div key={s} className="flex items-center gap-1.5 text-xs text-muted">
              <div className="w-2.5 h-2.5 rounded-full" style={{ background: SECTOR_COLORS[s] || "#6b7280" }} />
              {s}
            </div>
          ))}
        </div>
      </div>
      {/* Dept × Sector Cross-Tab */}
      {deptSectorData.data.length > 0 && (
        <div className="bg-card border border-card-border rounded-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-sm font-semibold text-muted">Department Mix by Sector</h3>
              <p className="text-xs text-muted mt-0.5">What each sector is actually hiring for</p>
            </div>
            <span className="text-xs px-2 py-1 rounded bg-accent/10 text-accent-light border border-accent/20">
              Startups Only
            </span>
          </div>
          <ResponsiveContainer width="100%" height={420}>
            <BarChart data={deptSectorData.data} layout="vertical" margin={{ left: 8, right: 16 }}>
              <XAxis type="number" tick={{ fill: "#9ca3af", fontSize: 11 }} />
              <YAxis type="category" dataKey="sector" width={168} tick={{ fill: "#9ca3af", fontSize: 11 }} />
              <Tooltip
                contentStyle={{ background: "#1a1d27", border: "1px solid #2a2d3a", borderRadius: 8 }}
                labelStyle={{ color: "#e5e7eb" }}
              />
              {deptSectorData.depts.map((dept) => (
                <Bar
                  key={dept}
                  dataKey={dept}
                  stackId="a"
                  fill={DEPT_COLORS[dept] || "#6b7280"}
                  name={dept}
                />
              ))}
            </BarChart>
          </ResponsiveContainer>
          <div className="flex flex-wrap gap-3 mt-4">
            {deptSectorData.depts.map((d) => (
              <div key={d} className="flex items-center gap-1.5 text-xs text-muted">
                <div className="w-2.5 h-2.5 rounded-full" style={{ background: DEPT_COLORS[d] || "#6b7280" }} />
                {d}
              </div>
            ))}
          </div>
        </div>
      )}

      {remoteSectorData.length > 0 && (
        <div className="bg-card border border-card-border rounded-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-sm font-semibold text-muted">Remote Mix by Sector</h3>
              <p className="text-xs text-muted mt-0.5">Where startup hiring is actually flexible</p>
            </div>
            <span className="text-xs px-2 py-1 rounded bg-accent/10 text-accent-light border border-accent/20">
              Startups Only
            </span>
          </div>
          <ResponsiveContainer width="100%" height={380}>
            <BarChart data={remoteSectorData} layout="vertical" margin={{ left: 8, right: 16 }}>
              <XAxis type="number" tick={{ fill: "#9ca3af", fontSize: 11 }} />
              <YAxis type="category" dataKey="sector" width={168} tick={{ fill: "#9ca3af", fontSize: 11 }} />
              <Tooltip {...TOOLTIP_STYLE} />
              <Bar dataKey="remote" stackId="remoteMix" fill="#22c55e" name={formatWorkModel("remote")} />
              <Bar dataKey="hybrid" stackId="remoteMix" fill="#f59e0b" name={formatWorkModel("hybrid")} />
              <Bar dataKey="onsite" stackId="remoteMix" fill="#6366f1" name={formatWorkModel("onsite")} />
            </BarChart>
          </ResponsiveContainer>
          <div className="flex flex-wrap gap-3 mt-4">
            {["remote", "hybrid", "onsite"].map((mode) => (
              <div key={mode} className="flex items-center gap-1.5 text-xs text-muted">
                <div
                  className="w-2.5 h-2.5 rounded-full"
                  style={{ background: mode === "remote" ? "#22c55e" : mode === "hybrid" ? "#f59e0b" : "#6366f1" }}
                />
                {formatWorkModel(mode)}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
