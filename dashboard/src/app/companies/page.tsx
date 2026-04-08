"use client";

import { useEffect, useState, useMemo } from "react";
import Link from "next/link";
import { api, CompanyRow, CompanyVelocity } from "@/lib/api";
import { downloadCSV } from "@/lib/export";
import { formatDate, formatMoney, fundingBadgeColor, FUNDING_ORDER } from "@/lib/format";

type SortKey = "name" | "active_jobs" | "sector" | "funding_round" | "net";
type CompanyTypeFilter = "" | "startup" | "bigco";

export default function CompaniesPage() {
  const [companies, setCompanies] = useState<CompanyRow[]>([]);
  const [velocity, setVelocity] = useState<Record<number, number>>({});
  const [search, setSearch] = useState("");
  const [sectorFilter, setSectorFilter] = useState("");
  const [fundingFilter, setFundingFilter] = useState("");
  const [typeFilter, setTypeFilter] = useState<CompanyTypeFilter>("");
  const [hideZeroJobs, setHideZeroJobs] = useState(true);
  const [compareIds, setCompareIds] = useState<number[]>([]);
  const [sortKey, setSortKey] = useState<SortKey>("active_jobs");
  const [sortAsc, setSortAsc] = useState(false);

  useEffect(() => {
    api.companies().then(setCompanies);
    api.companyVelocity(7).then((rows) => {
      const map: Record<number, number> = {};
      rows.forEach((r) => { map[r.company_id] = r.net; });
      setVelocity(map);
    });
  }, []);

  const sectors = useMemo(
    () => [...new Set(companies.map((c) => c.sector).filter(Boolean))].sort(),
    [companies]
  );

  const fundingRounds = useMemo(
    () => FUNDING_ORDER.filter((r) => companies.some((c) => c.funding_round === r)),
    [companies]
  );

  const filtered = useMemo(() => {
    let list = companies;
    if (search) {
      const q = search.toLowerCase();
      list = list.filter((c) => c.name.toLowerCase().includes(q));
    }
    if (sectorFilter) list = list.filter((c) => c.sector === sectorFilter);
    if (typeFilter) list = list.filter((c) => c.company_type === typeFilter);
    if (fundingFilter) list = list.filter((c) => c.funding_round === fundingFilter);
    if (hideZeroJobs) list = list.filter((c) => c.active_jobs > 0);
    return list;
  }, [companies, search, sectorFilter, typeFilter, fundingFilter, hideZeroJobs]);

  const toggleCompare = (id: number) => {
    setCompareIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : prev.length < 3 ? [...prev, id] : prev
    );
  };

  const sorted = useMemo(() => {
    return [...filtered].sort((a, b) => {
      const av = sortKey === "net" ? (velocity[a.id] ?? 0) : (a[sortKey as keyof CompanyRow] ?? "");
      const bv = sortKey === "net" ? (velocity[b.id] ?? 0) : (b[sortKey as keyof CompanyRow] ?? "");
      if (typeof av === "number" && typeof bv === "number") return sortAsc ? av - bv : bv - av;
      return sortAsc ? String(av).localeCompare(String(bv)) : String(bv).localeCompare(String(av));
    });
  }, [filtered, sortKey, sortAsc, velocity]);

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) setSortAsc(!sortAsc);
    else { setSortKey(key); setSortAsc(key === "name"); }
  };

  const arrow = (key: SortKey) => sortKey === key ? (sortAsc ? " ↑" : " ↓") : "";

  const handleExport = () => {
    const rows = sorted.map((c) => ({
      Name: c.name,
      Sector: c.sector,
      Type: c.company_type,
      "Funding Stage": c.funding_round || "",
      "Raised ($M)": c.funding_amount_m || "",
      "Active Jobs": c.active_jobs,
      "7-Day Change": velocity[c.id] ?? "",
      Website: c.website || "",
      "Last Scraped": formatDate(c.last_scraped),
    }));
    downloadCSV(rows as Record<string, unknown>[], "mosaic-companies.csv");
  };

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-2xl font-bold">Companies</h2>
          <p className="text-muted text-sm mt-1">
            {filtered.length} of {companies.length} companies
          </p>
        </div>
        <div className="flex gap-1 bg-card border border-card-border rounded-lg p-1">
          {([["", "All"], ["startup", "Startups"], ["bigco", "Big Tech"]] as [CompanyTypeFilter, string][]).map(([val, label]) => (
            <button
              key={val}
              onClick={() => setTypeFilter(val)}
              className={`px-3 py-1 text-xs rounded transition-colors ${
                typeFilter === val ? "bg-accent text-white" : "text-muted hover:text-foreground"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <div className="flex gap-3 flex-wrap items-center">
        <input
          type="text"
          placeholder="Search companies..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="bg-card border border-card-border rounded-lg px-3 py-2 text-sm text-foreground w-full sm:w-56"
        />
        <select
          value={sectorFilter}
          onChange={(e) => setSectorFilter(e.target.value)}
          className="bg-card border border-card-border rounded-lg px-3 py-2 text-sm text-foreground"
        >
          <option value="">All Sectors</option>
          {sectors.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <select
          value={fundingFilter}
          onChange={(e) => setFundingFilter(e.target.value)}
          className="bg-card border border-card-border rounded-lg px-3 py-2 text-sm text-foreground"
        >
          <option value="">All Stages</option>
          {fundingRounds.map((r) => <option key={r} value={r}>{r}</option>)}
        </select>
        <label className="flex items-center gap-2 text-sm text-muted cursor-pointer select-none">
          <input
            type="checkbox"
            checked={hideZeroJobs}
            onChange={(e) => setHideZeroJobs(e.target.checked)}
            className="accent-indigo-500"
          />
          Hide 0-job
        </label>
        <button
          onClick={handleExport}
          className="ml-auto px-3 py-2 text-xs bg-card border border-card-border rounded-lg text-muted hover:text-foreground transition-colors"
        >
          Export CSV
        </button>
      </div>

      {compareIds.length > 0 && (
        <div className="flex items-center gap-3 bg-accent/10 border border-accent/30 rounded-xl px-4 py-3">
          <span className="text-sm text-accent-light font-medium">
            {compareIds.length} {compareIds.length === 1 ? "company" : "companies"} selected
          </span>
          <Link
            href={`/compare?ids=${compareIds.join(",")}`}
            className="px-3 py-1.5 text-xs bg-accent text-white rounded-lg hover:bg-accent/80 transition-colors"
          >
            Compare →
          </Link>
          <button
            onClick={() => setCompareIds([])}
            className="text-xs text-muted hover:text-foreground ml-auto"
          >
            Clear
          </button>
        </div>
      )}

      <div className="bg-card border border-card-border rounded-xl overflow-hidden">
        <div className="max-h-[70vh] overflow-y-auto overflow-x-auto">
          <table className="w-full text-sm min-w-[700px]">
            <thead className="sticky top-0 bg-card z-10">
              <tr className="text-muted text-left border-b border-card-border">
                <th className="px-3 py-3 w-8" title="Select up to 3 to compare" />
                <th className="px-4 py-3 font-medium cursor-pointer hover:text-foreground" onClick={() => toggleSort("name")}>
                  Company{arrow("name")}
                </th>
                <th className="px-4 py-3 font-medium cursor-pointer hover:text-foreground" onClick={() => toggleSort("sector")}>
                  Sector{arrow("sector")}
                </th>
                <th className="px-4 py-3 font-medium cursor-pointer hover:text-foreground" onClick={() => toggleSort("funding_round")}>
                  Funding Stage{arrow("funding_round")}
                </th>
                <th className="px-4 py-3 font-medium">Raised</th>
                <th className="px-4 py-3 font-medium cursor-pointer hover:text-foreground text-right" onClick={() => toggleSort("active_jobs")}>
                  Active Jobs{arrow("active_jobs")}
                </th>
                <th className="px-4 py-3 font-medium cursor-pointer hover:text-foreground text-right" onClick={() => toggleSort("net")}>
                  7-Day Change{arrow("net")}
                </th>
                <th className="px-4 py-3 font-medium text-right">Updated</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((c) => {
                const net = velocity[c.id];
                return (
                  <tr key={c.id} className="border-b border-card-border/50 hover:bg-white/5">
                    <td className="px-3 py-2.5">
                      <input
                        type="checkbox"
                        checked={compareIds.includes(c.id)}
                        onChange={() => toggleCompare(c.id)}
                        disabled={!compareIds.includes(c.id) && compareIds.length >= 3}
                        className="accent-indigo-500 cursor-pointer"
                        title={compareIds.length >= 3 && !compareIds.includes(c.id) ? "Max 3 companies" : "Select to compare"}
                      />
                    </td>
                    <td className="px-4 py-2.5 font-medium">
                      <div className="flex items-center gap-2">
                        <Link href={`/companies/${c.id}`} className="hover:text-accent-light">
                          {c.name}
                        </Link>
                        {c.company_type === "bigco" && (
                          <span className="text-xs bg-card-border text-muted px-1.5 py-0.5 rounded">Big Tech</span>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-2.5 text-muted">{c.sector}</td>
                    <td className="px-4 py-2.5">
                      {c.funding_round ? (
                        <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${fundingBadgeColor(c.funding_round)}`}>
                          {c.funding_round}
                        </span>
                      ) : <span className="text-muted">—</span>}
                    </td>
                    <td className="px-4 py-2.5 text-muted">{formatMoney(c.funding_amount_m)}</td>
                    <td className="px-4 py-2.5 text-right font-mono">{c.active_jobs}</td>
                    <td className="px-4 py-2.5 text-right font-mono">
                      {net !== undefined ? (
                        <span className={net > 0 ? "text-green" : net < 0 ? "text-red" : "text-muted"}>
                          {net > 0 ? "+" : ""}{net}
                        </span>
                      ) : "—"}
                    </td>
                    <td className="px-4 py-2.5 text-right text-muted text-xs">{formatDate(c.last_scraped)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
