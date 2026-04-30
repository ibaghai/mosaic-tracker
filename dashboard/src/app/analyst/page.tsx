"use client";

import { useEffect, useMemo, useState } from "react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  BarChart,
  Bar,
  Cell,
} from "recharts";
import { api, AnalystCohortResponse, CompanyRow } from "@/lib/api";
import { downloadCSV } from "@/lib/export";

const COLORS = ["#22c55e", "#f59e0b", "#06b6d4", "#ef4444", "#6366f1", "#84cc16", "#f97316"];

export default function AnalystPage() {
  const [companies, setCompanies] = useState<CompanyRow[]>([]);
  const [cohort, setCohort] = useState<AnalystCohortResponse | null>(null);
  const [sector, setSector] = useState("");
  const [fundingRound, setFundingRound] = useState("");
  const [companyType, setCompanyType] = useState("");
  const [atsType, setAtsType] = useState("");
  const [weeks, setWeeks] = useState(12);

  useEffect(() => {
    void api.companies().then(setCompanies);
  }, []);

  useEffect(() => {
    let cancelled = false;
    void api.analystCohort({
      sector: sector || undefined,
      funding_round: fundingRound || undefined,
      company_type: companyType || undefined,
      ats_type: atsType || undefined,
      weeks,
    }).then((res) => {
      if (cancelled) return;
      setCohort(res);
    });
    return () => {
      cancelled = true;
    };
  }, [sector, fundingRound, companyType, atsType, weeks]);

  const sectors = useMemo(
    () => [...new Set(companies.map((c) => c.sector).filter((v): v is string => Boolean(v)))].sort(),
    [companies]
  );
  const fundingRounds = useMemo(
    () => [...new Set(companies.map((c) => c.funding_round).filter((v): v is string => Boolean(v)))].sort(),
    [companies]
  );
  const atsTypes = useMemo(
    () => [...new Set(companies.map((c) => c.ats_type).filter((v): v is string => Boolean(v)))].sort(),
    [companies]
  );

  const weekly = useMemo(() => cohort?.weekly_index ?? [], [cohort?.weekly_index]);
  const roleDeltaTop = useMemo(
    () => (cohort?.role_mix_change ?? []).slice(0, 10),
    [cohort]
  );

  const netWindow = useMemo(
    () => weekly.reduce((sum, row) => sum + (row.net || 0), 0),
    [weekly]
  );

  const exportCohort = () => {
    if (!cohort?.companies?.length) return;
    const rows = cohort.companies.map((c) => ({
      Company: c.name,
      Sector: c.sector || "",
      Type: c.company_type,
      "Funding Round": c.funding_round || "",
      ATS: c.ats_type || "",
      "Active Jobs": c.active_jobs,
      "Added (28d)": c.added_28d,
      "Removed (28d)": c.removed_28d,
      "Net (28d)": c.net_28d,
    }));
    downloadCSV(rows as Record<string, unknown>[], "mosaic-analyst-cohort.csv");
  };

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h2 className="text-2xl font-bold">Analyst</h2>
          <p className="text-muted text-sm mt-1">
            Cohort hiring index and role mix movement
          </p>
        </div>
        <button
          onClick={exportCohort}
          className="px-3 py-2 text-xs bg-card border border-card-border rounded-lg text-muted hover:text-foreground transition-colors"
        >
          Export Cohort CSV
        </button>
      </div>

      <div className="bg-card border border-card-border rounded-xl p-4 flex flex-wrap gap-3">
        <select value={sector} onChange={(e) => setSector(e.target.value)} className="bg-background border border-card-border rounded-lg px-3 py-2 text-sm text-foreground">
          <option value="">All Sectors</option>
          {sectors.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <select value={fundingRound} onChange={(e) => setFundingRound(e.target.value)} className="bg-background border border-card-border rounded-lg px-3 py-2 text-sm text-foreground">
          <option value="">All Funding Stages</option>
          {fundingRounds.map((f) => <option key={f} value={f}>{f}</option>)}
        </select>
        <select value={companyType} onChange={(e) => setCompanyType(e.target.value)} className="bg-background border border-card-border rounded-lg px-3 py-2 text-sm text-foreground">
          <option value="">All Company Types</option>
          <option value="startup">Startup</option>
          <option value="bigco">Bigco</option>
        </select>
        <select value={atsType} onChange={(e) => setAtsType(e.target.value)} className="bg-background border border-card-border rounded-lg px-3 py-2 text-sm text-foreground">
          <option value="">All ATS</option>
          {atsTypes.map((a) => <option key={a} value={a}>{a}</option>)}
        </select>
        <select value={weeks} onChange={(e) => setWeeks(Number(e.target.value))} className="bg-background border border-card-border rounded-lg px-3 py-2 text-sm text-foreground">
          {[8, 12, 16, 24].map((w) => <option key={w} value={w}>{w} weeks</option>)}
        </select>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KpiCard label="Cohort Companies" value={cohort?.cohort_company_count ?? 0} />
        <KpiCard label="Active Jobs" value={cohort?.cohort_active_jobs ?? 0} />
        <KpiCard label="Net Momentum" value={netWindow} />
        <KpiCard label="Role Families" value={cohort?.role_mix_change?.length ?? 0} />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-card border border-card-border rounded-xl p-5">
          <h3 className="text-sm font-semibold text-muted mb-4">Hiring Index by Week</h3>
          <ResponsiveContainer width="100%" height={320}>
            <LineChart data={weekly}>
              <CartesianGrid stroke="#1f2430" strokeDasharray="3 3" />
              <XAxis dataKey="week_start" tick={{ fill: "#9ca3af", fontSize: 11 }} />
              <YAxis tick={{ fill: "#9ca3af", fontSize: 11 }} />
              <Tooltip
                contentStyle={{ background: "#1a1d27", border: "1px solid #2a2d3a", borderRadius: 8 }}
                labelStyle={{ color: "#e5e7eb" }}
                itemStyle={{ color: "#e5e7eb" }}
              />
              <Line type="monotone" dataKey="net" stroke="#22c55e" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-card border border-card-border rounded-xl p-5">
          <h3 className="text-sm font-semibold text-muted mb-4">Role Mix Change (Last 4 Weeks vs Prior 4)</h3>
          <ResponsiveContainer width="100%" height={320}>
            <BarChart data={roleDeltaTop}>
              <CartesianGrid stroke="#1f2430" strokeDasharray="3 3" />
              <XAxis dataKey="role_family" tick={{ fill: "#9ca3af", fontSize: 11 }} />
              <YAxis tick={{ fill: "#9ca3af", fontSize: 11 }} />
              <Tooltip
                contentStyle={{ background: "#1a1d27", border: "1px solid #2a2d3a", borderRadius: 8 }}
                labelStyle={{ color: "#e5e7eb" }}
                itemStyle={{ color: "#e5e7eb" }}
              />
              <Bar dataKey="delta">
                {roleDeltaTop.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="bg-card border border-card-border rounded-xl overflow-hidden">
        <div className="max-h-[50vh] overflow-y-auto overflow-x-auto">
          <table className="w-full text-sm min-w-[760px]">
            <thead className="sticky top-0 bg-card z-10">
              <tr className="text-muted text-left border-b border-card-border">
                <th className="px-4 py-3 font-medium">Company</th>
                <th className="px-4 py-3 font-medium">Sector</th>
                <th className="px-4 py-3 font-medium">ATS</th>
                <th className="px-4 py-3 font-medium text-right">Active Jobs</th>
                <th className="px-4 py-3 font-medium text-right">Added 28d</th>
                <th className="px-4 py-3 font-medium text-right">Removed 28d</th>
                <th className="px-4 py-3 font-medium text-right">Net 28d</th>
              </tr>
            </thead>
            <tbody>
              {cohort === null ? (
                <tr><td colSpan={7} className="px-4 py-8 text-center text-muted">Loading...</td></tr>
              ) : (cohort?.companies ?? []).map((c) => (
                <tr key={c.id} className="border-b border-card-border/50 hover:bg-white/5">
                  <td className="px-4 py-2.5 font-medium">{c.name}</td>
                  <td className="px-4 py-2.5 text-muted text-xs">{c.sector || "—"}</td>
                  <td className="px-4 py-2.5 text-muted text-xs">{c.ats_type || "—"}</td>
                  <td className="px-4 py-2.5 text-right font-mono">{c.active_jobs}</td>
                  <td className="px-4 py-2.5 text-right font-mono text-green">{c.added_28d}</td>
                  <td className="px-4 py-2.5 text-right font-mono text-red">{c.removed_28d}</td>
                  <td className="px-4 py-2.5 text-right font-mono">{c.net_28d > 0 ? `+${c.net_28d}` : c.net_28d}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function KpiCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="bg-card border border-card-border rounded-xl p-5">
      <p className="text-sm text-muted">{label}</p>
      <p className="text-2xl font-bold mt-1">{value.toLocaleString()}</p>
    </div>
  );
}
