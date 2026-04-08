"use client";

import { useEffect, useState, useMemo } from "react";
import Link from "next/link";
import { api, CompanyRow } from "@/lib/api";
import { formatMoney, fundingBadgeColor, FUNDING_ORDER } from "@/lib/format";

export default function CoveragePage() {
  const [companies, setCompanies] = useState<CompanyRow[]>([]);
  const [search, setSearch] = useState("");
  const [sectorFilter, setSectorFilter] = useState("");
  const [fundingFilter, setFundingFilter] = useState("");
  const [hideZeroJobs, setHideZeroJobs] = useState(true);
  const [view, setView] = useState<"grid" | "list">("grid");

  useEffect(() => {
    api.companies().then(setCompanies);
  }, []);

  const startups = useMemo(
    () => companies.filter((c) => c.company_type === "startup"),
    [companies]
  );
  const bigcos = useMemo(
    () => companies.filter((c) => c.company_type === "bigco"),
    [companies]
  );

  const sectors = useMemo(
    () => [...new Set(startups.map((c) => c.sector).filter(Boolean))].sort(),
    [startups]
  );

  const fundingRounds = useMemo(
    () => FUNDING_ORDER.filter((r) => startups.some((c) => c.funding_round === r)),
    [startups]
  );

  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    return {
      startups: startups.filter((c) =>
        (!q || c.name.toLowerCase().includes(q)) &&
        (!sectorFilter || c.sector === sectorFilter) &&
        (!fundingFilter || c.funding_round === fundingFilter) &&
        (!hideZeroJobs || c.active_jobs > 0)
      ),
      bigcos: bigcos.filter((c) =>
        (!q || c.name.toLowerCase().includes(q)) &&
        (!hideZeroJobs || c.active_jobs > 0)
      ),
    };
  }, [startups, bigcos, search, sectorFilter, fundingFilter, hideZeroJobs]);

  // Group startups by sector
  const startupsBySector = useMemo(() => {
    const groups: Record<string, CompanyRow[]> = {};
    filtered.startups.forEach((c) => {
      const s = c.sector || "Other";
      if (!groups[s]) groups[s] = [];
      groups[s].push(c);
    });
    // Sort each group by active_jobs desc
    Object.values(groups).forEach((arr) => arr.sort((a, b) => b.active_jobs - a.active_jobs));
    return Object.entries(groups).sort((a, b) => b[1].length - a[1].length);
  }, [filtered.startups]);

  return (
    <div className="space-y-8">
      <div className="flex items-start justify-between flex-wrap gap-4">
        <div>
          <h2 className="text-2xl font-bold">Coverage</h2>
          <p className="text-muted text-sm mt-1">
            {companies.length === 0
              ? "Loading..."
              : `${startups.length} startups · ${bigcos.length} Big Tech companies tracked`}
          </p>
        </div>
        <div className="flex gap-2">
          <div className="flex gap-1 bg-card border border-card-border rounded-lg p-1">
            <button
              onClick={() => setView("grid")}
              className={`px-3 py-1 text-xs rounded transition-colors ${view === "grid" ? "bg-accent text-white" : "text-muted hover:text-foreground"}`}
            >
              Grid
            </button>
            <button
              onClick={() => setView("list")}
              className={`px-3 py-1 text-xs rounded transition-colors ${view === "list" ? "bg-accent text-white" : "text-muted hover:text-foreground"}`}
            >
              List
            </button>
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-3 flex-wrap">
        <input
          type="text"
          placeholder="Search companies..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="bg-card border border-card-border rounded-lg px-3 py-2 text-sm text-foreground w-full sm:w-64"
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
          Hide 0-job companies
        </label>
        {(search || sectorFilter || fundingFilter) && (
          <button
            onClick={() => { setSearch(""); setSectorFilter(""); setFundingFilter(""); }}
            className="px-3 py-2 text-xs text-red border border-red/30 rounded-lg hover:bg-red/10 transition-colors"
          >
            Clear
          </button>
        )}
      </div>

      {/* Big Tech section */}
      {filtered.bigcos.length > 0 && (
        <section>
          <h3 className="text-sm font-semibold text-muted mb-3 flex items-center gap-2">
            Big Tech
            <span className="text-xs font-normal px-1.5 py-0.5 bg-card-border rounded">
              {filtered.bigcos.length}
            </span>
          </h3>
          {view === "grid" ? (
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
              {filtered.bigcos.map((c) => (
                <CompanyCard key={c.id} company={c} fundingBadgeColor={fundingBadgeColor} />
              ))}
            </div>
          ) : (
            <CompanyListTable companies={filtered.bigcos} fundingBadgeColor={fundingBadgeColor} />
          )}
        </section>
      )}

      {/* Startups grouped by sector */}
      {startupsBySector.map(([sector, sectorCompanies]) => (
        <section key={sector}>
          <h3 className="text-sm font-semibold text-muted mb-3 flex items-center gap-2">
            {sector}
            <span className="text-xs font-normal px-1.5 py-0.5 bg-card-border rounded">
              {sectorCompanies.length}
            </span>
          </h3>
          {view === "grid" ? (
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
              {sectorCompanies.map((c) => (
                <CompanyCard key={c.id} company={c} fundingBadgeColor={fundingBadgeColor} />
              ))}
            </div>
          ) : (
            <CompanyListTable companies={sectorCompanies} fundingBadgeColor={fundingBadgeColor} />
          )}
        </section>
      ))}

      {companies.length > 0 && filtered.startups.length === 0 && filtered.bigcos.length === 0 && (
        <p className="text-muted text-sm">No companies match your search.</p>
      )}
    </div>
  );
}

function CompanyCard({
  company: c,
  fundingBadgeColor,
}: {
  company: CompanyRow;
  fundingBadgeColor: (r: string | null) => string;
}) {
  return (
    <Link
      href={`/companies/${c.id}`}
      className="bg-card border border-card-border rounded-xl p-4 hover:border-accent/40 transition-colors group block"
    >
      <p className="font-medium text-sm group-hover:text-accent-light truncate">{c.name}</p>
      <p className="text-xs text-muted mt-0.5 truncate">{c.sector}</p>
      <div className="flex items-center justify-between mt-3">
        {c.funding_round ? (
          <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${fundingBadgeColor(c.funding_round)}`}>
            {c.funding_round}
          </span>
        ) : <span />}
        <span className="text-xs font-mono text-muted">{c.active_jobs} jobs</span>
      </div>
      {c.funding_amount_m && (
        <p className="text-xs text-muted mt-1">{formatMoney(c.funding_amount_m)}</p>
      )}
    </Link>
  );
}

function CompanyListTable({
  companies,
  fundingBadgeColor,
}: {
  companies: CompanyRow[];
  fundingBadgeColor: (r: string | null) => string;
}) {
  return (
    <div className="bg-card border border-card-border rounded-xl overflow-hidden">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-muted text-left border-b border-card-border">
            <th className="px-4 py-3 font-medium">Company</th>
            <th className="px-4 py-3 font-medium">Sector</th>
            <th className="px-4 py-3 font-medium">Funding Stage</th>
            <th className="px-4 py-3 font-medium">Raised</th>
            <th className="px-4 py-3 font-medium text-right">Active Jobs</th>
            <th className="px-4 py-3 font-medium">Website</th>
          </tr>
        </thead>
        <tbody>
          {companies.map((c) => (
            <tr key={c.id} className="border-b border-card-border/50 hover:bg-white/5">
              <td className="px-4 py-2.5 font-medium">
                <Link href={`/companies/${c.id}`} className="hover:text-accent-light">
                  {c.name}
                </Link>
              </td>
              <td className="px-4 py-2.5 text-muted text-xs">{c.sector}</td>
              <td className="px-4 py-2.5">
                {c.funding_round ? (
                  <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${fundingBadgeColor(c.funding_round)}`}>
                    {c.funding_round}
                  </span>
                ) : <span className="text-muted">—</span>}
              </td>
              <td className="px-4 py-2.5 text-muted text-xs">{formatMoney(c.funding_amount_m)}</td>
              <td className="px-4 py-2.5 text-right font-mono text-sm">{c.active_jobs}</td>
              <td className="px-4 py-2.5">
                {c.website ? (
                  <a
                    href={c.website.startsWith("http") ? c.website : `https://${c.website}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs text-accent-light hover:underline"
                    onClick={(e) => e.stopPropagation()}
                  >
                    {c.website.replace(/^https?:\/\//, "").replace(/\/$/, "")}
                  </a>
                ) : <span className="text-muted">—</span>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
