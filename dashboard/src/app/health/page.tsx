"use client";

import { useEffect, useState } from "react";
import { api, HealthRow } from "@/lib/api";
import { formatDate } from "@/lib/format";

type StatusFilter = "" | "ok" | "error" | "stale";

function statusBadge(row: HealthRow) {
  if (row.status === "error" || row.error_msg) {
    return (
      <span className="text-xs px-2 py-0.5 rounded font-medium bg-red/10 text-red">Error</span>
    );
  }
  if (!row.last_run) {
    return <span className="text-xs px-2 py-0.5 rounded font-medium bg-card-border text-muted">Never</span>;
  }
  // Stale if last run more than 10 days ago
  const daysSince = (Date.now() - new Date(row.last_run).getTime()) / 86400000;
  if (daysSince > 10) {
    return <span className="text-xs px-2 py-0.5 rounded font-medium bg-yellow/10 text-yellow-400">Stale</span>;
  }
  return <span className="text-xs px-2 py-0.5 rounded font-medium bg-green/10 text-green">OK</span>;
}

function getStatusKey(row: HealthRow): StatusFilter {
  if (row.status === "error" || row.error_msg) return "error";
  if (!row.last_run) return "stale";
  const daysSince = (Date.now() - new Date(row.last_run).getTime()) / 86400000;
  if (daysSince > 10) return "stale";
  return "ok";
}

export default function HealthPage() {
  const [rows, setRows] = useState<HealthRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("");
  const [atsFilter, setAtsFilter] = useState("");

  useEffect(() => {
    api.health().then((data) => {
      setRows(data);
      setLoading(false);
    });
  }, []);

  const atsList = [...new Set(rows.map((r) => r.ats_type).filter(Boolean))].sort() as string[];

  const filtered = rows.filter((r) => {
    if (search && !r.name.toLowerCase().includes(search.toLowerCase())) return false;
    if (statusFilter && getStatusKey(r) !== statusFilter) return false;
    if (atsFilter && r.ats_type !== atsFilter) return false;
    return true;
  });

  const counts = {
    ok: rows.filter((r) => getStatusKey(r) === "ok").length,
    error: rows.filter((r) => getStatusKey(r) === "error").length,
    stale: rows.filter((r) => getStatusKey(r) === "stale").length,
  };

  const atsDist = atsList.reduce<Record<string, number>>((acc, ats) => {
    acc[ats] = rows.filter((r) => r.ats_type === ats).length;
    return acc;
  }, {});

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-2xl font-bold">Scraper Health</h2>
          <p className="text-muted text-sm mt-1">
            {loading ? "Loading..." : `${rows.length} companies monitored`}
          </p>
        </div>
      </div>

      {/* Summary KPIs */}
      {!loading && (
        <div className="grid grid-cols-3 gap-4">
          <div
            className={`bg-card border rounded-xl p-4 cursor-pointer transition-colors ${statusFilter === "ok" ? "border-green/50" : "border-card-border hover:border-card-border/80"}`}
            onClick={() => setStatusFilter(statusFilter === "ok" ? "" : "ok")}
          >
            <p className="text-xs text-muted mb-1">Healthy</p>
            <p className="text-2xl font-bold font-mono text-green">{counts.ok}</p>
          </div>
          <div
            className={`bg-card border rounded-xl p-4 cursor-pointer transition-colors ${statusFilter === "error" ? "border-red/50" : "border-card-border hover:border-card-border/80"}`}
            onClick={() => setStatusFilter(statusFilter === "error" ? "" : "error")}
          >
            <p className="text-xs text-muted mb-1">Errors</p>
            <p className="text-2xl font-bold font-mono text-red">{counts.error}</p>
          </div>
          <div
            className={`bg-card border rounded-xl p-4 cursor-pointer transition-colors ${statusFilter === "stale" ? "border-yellow-400/50" : "border-card-border hover:border-card-border/80"}`}
            onClick={() => setStatusFilter(statusFilter === "stale" ? "" : "stale")}
          >
            <p className="text-xs text-muted mb-1">Stale (&gt;10 days)</p>
            <p className="text-2xl font-bold font-mono text-yellow-400">{counts.stale}</p>
          </div>
        </div>
      )}

      {/* ATS Distribution */}
      {!loading && atsList.length > 0 && (
        <div className="bg-card border border-card-border rounded-xl p-5">
          <h3 className="text-sm font-semibold mb-3">ATS Platform Distribution</h3>
          <div className="flex flex-wrap gap-2">
            {Object.entries(atsDist).sort((a, b) => b[1] - a[1]).map(([ats, count]) => (
              <button
                key={ats}
                onClick={() => setAtsFilter(atsFilter === ats ? "" : ats)}
                className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs border transition-colors ${
                  atsFilter === ats
                    ? "bg-accent/20 border-accent/40 text-accent-light"
                    : "bg-background border-card-border text-muted hover:text-foreground"
                }`}
              >
                <span className="font-medium capitalize">{ats}</span>
                <span className="opacity-60">{count}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="flex gap-3 flex-wrap">
        <input
          type="text"
          placeholder="Search companies..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="bg-card border border-card-border rounded-lg px-3 py-2 text-sm text-foreground w-64"
        />
        {(search || statusFilter || atsFilter) && (
          <button
            onClick={() => { setSearch(""); setStatusFilter(""); setAtsFilter(""); }}
            className="px-3 py-2 text-xs text-red border border-red/30 rounded-lg hover:bg-red/10 transition-colors"
          >
            Clear filters
          </button>
        )}
        <p className="ml-auto text-xs text-muted self-center">{filtered.length} of {rows.length} companies</p>
      </div>

      {/* Table */}
      <div className="bg-card border border-card-border rounded-xl overflow-hidden">
        <div className="max-h-[65vh] overflow-y-auto">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-card z-10">
              <tr className="text-muted text-left border-b border-card-border">
                <th className="px-4 py-3 font-medium">Company</th>
                <th className="px-4 py-3 font-medium">ATS</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium text-right">Active Jobs</th>
                <th className="px-4 py-3 font-medium text-right">Jobs Found</th>
                <th className="px-4 py-3 font-medium">Last Run</th>
                <th className="px-4 py-3 font-medium">Error</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-muted">Loading...</td>
                </tr>
              ) : filtered.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-muted">No companies match filters</td>
                </tr>
              ) : filtered.map((r) => (
                <tr key={r.id} className="border-b border-card-border/50 hover:bg-white/5">
                  <td className="px-4 py-2.5 font-medium">
                    <div className="flex items-center gap-2">
                      <a href={`/companies/${r.id}`} className="hover:text-accent-light">
                        {r.name}
                      </a>
                      {r.company_type === "bigco" && (
                        <span className="text-xs bg-card-border text-muted px-1.5 py-0.5 rounded">Big Tech</span>
                      )}
                    </div>
                    <p className="text-xs text-muted">{r.sector}</p>
                  </td>
                  <td className="px-4 py-2.5 text-muted text-xs capitalize">{r.ats_type || "—"}</td>
                  <td className="px-4 py-2.5">{statusBadge(r)}</td>
                  <td className="px-4 py-2.5 text-right font-mono text-xs">{r.active_jobs}</td>
                  <td className="px-4 py-2.5 text-right font-mono text-xs text-muted">{r.jobs_found ?? "—"}</td>
                  <td className="px-4 py-2.5 text-xs text-muted">{formatDate(r.last_run)}</td>
                  <td className="px-4 py-2.5 text-xs text-red max-w-xs truncate" title={r.error_msg || ""}>
                    {r.error_msg || "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
