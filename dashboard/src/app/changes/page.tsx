"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
} from "recharts";
import { api, JobEvent, Mover, SectorDelta } from "@/lib/api";

const TOOLTIP_STYLE = {
  contentStyle: { background: "#1a1d27", border: "1px solid #2a2d3a", borderRadius: 8 },
  labelStyle: { color: "#e5e7eb" },
  itemStyle: { color: "#e5e7eb" },
};

type CompanyTypeFilter = "" | "startup" | "bigco";

export default function ChangesPage() {
  const [events, setEvents] = useState<JobEvent[]>([]);
  const [movers, setMovers] = useState<Mover[]>([]);
  const [sectorDelta, setSectorDelta] = useState<SectorDelta[]>([]);
  const [searchFilter, setSearchFilter] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [companyType, setCompanyType] = useState<CompanyTypeFilter>("");
  const [days, setDays] = useState(7);

  useEffect(() => {
    api.changeEvents({ limit: 500, event_type: typeFilter || undefined }).then(setEvents);
  }, [typeFilter]);

  useEffect(() => {
    api.movers(days).then(setMovers);
  }, [days]);

  useEffect(() => {
    api.sectorDelta().then(setSectorDelta);
  }, []);

  const filteredEvents = events.filter((e) => {
    if (companyType && e.company_type !== companyType) return false;
    if (searchFilter) {
      const q = searchFilter.toLowerCase();
      return e.company.toLowerCase().includes(q) || e.title.toLowerCase().includes(q);
    }
    return true;
  });

  const filteredMovers = companyType
    ? movers.filter((m) => m.company_type === companyType)
    : movers;

  const added = filteredEvents.filter((e) => e.event_type === "added").length;
  const removed = filteredEvents.filter((e) => e.event_type === "removed").length;

  return (
    <div className="space-y-8">
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-2xl font-bold">Changes</h2>
          <p className="text-muted text-sm mt-1">What changed since the last update</p>
        </div>
        <div className="flex gap-1 bg-card border border-card-border rounded-lg p-1">
          {([["", "All"], ["startup", "Startups"], ["bigco", "Big Tech"]] as [CompanyTypeFilter, string][]).map(([val, label]) => (
            <button
              key={val}
              onClick={() => setCompanyType(val)}
              className={`px-3 py-1 text-xs rounded transition-colors ${
                companyType === val ? "bg-accent text-white" : "text-muted hover:text-foreground"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <div className="flex gap-4">
        <div className="bg-card border border-card-border rounded-xl px-5 py-3">
          <span className="text-green font-bold text-lg">+{added}</span>
          <span className="text-muted text-sm ml-2">opened</span>
        </div>
        <div className="bg-card border border-card-border rounded-xl px-5 py-3">
          <span className="text-red font-bold text-lg">-{removed}</span>
          <span className="text-muted text-sm ml-2">closed</span>
        </div>
        <div className="bg-card border border-card-border rounded-xl px-5 py-3">
          <span className={`font-bold text-lg ${added - removed >= 0 ? "text-green" : "text-red"}`}>
            {added - removed > 0 ? "+" : ""}{added - removed}
          </span>
          <span className="text-muted text-sm ml-2">net</span>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Biggest Changes */}
        <div className="bg-card border border-card-border rounded-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-muted">Biggest Changes</h3>
            <div className="flex gap-1">
              {[7, 30, 90].map((d) => (
                <button
                  key={d}
                  onClick={() => setDays(d)}
                  className={`px-2 py-1 text-xs rounded ${
                    days === d ? "bg-accent text-white" : "text-muted hover:bg-white/5"
                  }`}
                >
                  {d}d
                </button>
              ))}
            </div>
          </div>
          <div className="space-y-2 max-h-80 overflow-y-auto">
            {filteredMovers.map((m) => (
              <div
                key={m.name}
                className="flex items-center justify-between text-sm py-1.5 border-b border-card-border last:border-0"
              >
                <div>
                  <Link href={`/companies/${m.company_id}`} className="font-medium hover:text-accent-light">
                    {m.name}
                  </Link>
                  {m.company_type === "bigco" && (
                    <span className="ml-2 text-xs bg-card-border text-muted px-1.5 py-0.5 rounded">Big Tech</span>
                  )}
                  <span className="text-muted text-xs ml-2">{m.sector}</span>
                </div>
                <span className={m.net >= 0 ? "text-green" : "text-red"}>
                  {m.net > 0 ? "+" : ""}{m.net}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Net Change by Sector */}
        <div className="bg-card border border-card-border rounded-xl p-5">
          <h3 className="text-sm font-semibold text-muted mb-4">Net Change by Sector</h3>
          <ResponsiveContainer width="100%" height={320}>
            <BarChart data={sectorDelta} layout="vertical" margin={{ left: 20 }}>
              <XAxis type="number" tick={{ fill: "#9ca3af", fontSize: 12 }} />
              <YAxis type="category" dataKey="sector" width={160} tick={{ fill: "#9ca3af", fontSize: 12 }} />
              <Tooltip {...TOOLTIP_STYLE} />
              <Bar dataKey="net" radius={[0, 4, 4, 0]}>
                {sectorDelta.map((d, i) => (
                  <Cell key={i} fill={d.net >= 0 ? "#22c55e" : "#ef4444"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Activity Log */}
      <div className="bg-card border border-card-border rounded-xl p-5">
        <div className="flex items-center gap-4 mb-4">
          <h3 className="text-sm font-semibold text-muted">Activity Log</h3>
          <input
            type="text"
            placeholder="Filter by company or job title..."
            value={searchFilter}
            onChange={(e) => setSearchFilter(e.target.value)}
            className="bg-background border border-card-border rounded-lg px-3 py-1.5 text-sm text-foreground flex-1 max-w-sm"
          />
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="bg-background border border-card-border rounded-lg px-3 py-1.5 text-sm text-foreground"
          >
            <option value="">All Activity</option>
            <option value="added">Opened</option>
            <option value="removed">Closed</option>
          </select>
        </div>
        <div className="max-h-96 overflow-y-auto overflow-x-auto">
          <table className="w-full text-sm min-w-[640px]">
            <thead className="sticky top-0 bg-card">
              <tr className="text-muted text-left border-b border-card-border">
                <th className="pb-2 font-medium">Status</th>
                <th className="pb-2 font-medium">Job Title</th>
                <th className="pb-2 font-medium">Company</th>
                <th className="pb-2 font-medium">Sector</th>
                <th className="pb-2 font-medium">Department</th>
                <th className="pb-2 font-medium">Date</th>
              </tr>
            </thead>
            <tbody>
              {filteredEvents.slice(0, 300).map((e, i) => (
                <tr key={i} className="border-b border-card-border/50 hover:bg-white/5">
                  <td className="py-2">
                    <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                      e.event_type === "added"
                        ? "bg-green/15 text-green"
                        : "bg-red/15 text-red"
                    }`}>
                      {e.event_type === "added" ? "Opened" : "Closed"}
                    </span>
                  </td>
                  <td className="py-2">{e.title}</td>
                  <td className="py-2 text-muted">
                    <Link href={`/companies/${e.company_id}`} className="hover:text-accent-light">
                      {e.company}
                    </Link>
                    {e.company_type === "bigco" && (
                      <span className="ml-1 text-xs text-muted opacity-60">·BT</span>
                    )}
                  </td>
                  <td className="py-2 text-muted">{e.sector}</td>
                  <td className="py-2 text-muted">{e.normalized_department || "—"}</td>
                  <td className="py-2 text-muted text-xs">
                    {new Date(e.created_at).toLocaleDateString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {filteredEvents.length > 300 && (
            <p className="px-2 py-3 text-xs text-muted">
              Showing 300 of {filteredEvents.length.toLocaleString()} events. Use filters to narrow down.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
