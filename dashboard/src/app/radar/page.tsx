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
import { api, CompanyRow, RadarResponse, RoleFamilyRow, Watchlist, WatchlistItem } from "@/lib/api";

const COLORS = ["#ef4444", "#22c55e", "#06b6d4", "#f59e0b", "#6366f1", "#14b8a6", "#f97316"];

export default function RadarPage() {
  const [watchlists, setWatchlists] = useState<Watchlist[]>([]);
  const [companies, setCompanies] = useState<CompanyRow[]>([]);
  const [roleFamilies, setRoleFamilies] = useState<RoleFamilyRow[]>([]);
  const [selectedWatchlistId, setSelectedWatchlistId] = useState<number | "">("");
  const [watchlistName, setWatchlistName] = useState("");
  const [items, setItems] = useState<WatchlistItem[]>([]);
  const [radar, setRadar] = useState<RadarResponse | null>(null);
  const [companyToAdd, setCompanyToAdd] = useState<number | "">("");
  const [roleFamilyToAdd, setRoleFamilyToAdd] = useState("");
  const [weeks, setWeeks] = useState(8);

  useEffect(() => {
    void Promise.all([
      api.watchlists("recruiter"),
      api.companies(),
      api.roleFamilies("startup"),
    ]).then(([lists, companyRows, roles]) => {
      setWatchlists(lists);
      setCompanies(companyRows);
      setRoleFamilies(roles);
      if (lists.length > 0) setSelectedWatchlistId(lists[0].id);
      if (roles.length > 0) setRoleFamilyToAdd(String(roles[0].role_family || ""));
      if (companyRows.length > 0) setCompanyToAdd(companyRows[0].id);
    });
  }, []);

  useEffect(() => {
    if (!selectedWatchlistId) {
      return;
    }
    void Promise.all([
      api.watchlistItems(Number(selectedWatchlistId)),
      api.radar({ watchlist_id: Number(selectedWatchlistId), weeks }),
    ]).then(([itemRows, radarRows]) => {
      setItems(itemRows);
      setRadar(radarRows);
    });
  }, [selectedWatchlistId, weeks]);

  const refreshWatchlists = () => {
    void api.watchlists("recruiter").then((lists) => {
      setWatchlists(lists);
      if (!selectedWatchlistId && lists.length > 0) setSelectedWatchlistId(lists[0].id);
    });
  };

  const createWatchlist = async () => {
    const name = watchlistName.trim();
    if (!name) return;
    const created = await api.createWatchlist({ name, persona: "recruiter" });
    setWatchlistName("");
    setSelectedWatchlistId(created.id);
    refreshWatchlists();
  };

  const addCompany = async () => {
    if (!selectedWatchlistId || !companyToAdd) return;
    await api.addWatchlistItem(Number(selectedWatchlistId), {
      item_type: "company",
      item_value: String(companyToAdd),
      company_id: Number(companyToAdd),
    });
    const itemRows = await api.watchlistItems(Number(selectedWatchlistId));
    setItems(itemRows);
    const radarRows = await api.radar({ watchlist_id: Number(selectedWatchlistId), weeks });
    setRadar(radarRows);
    refreshWatchlists();
  };

  const addRoleFamily = async () => {
    if (!selectedWatchlistId || !roleFamilyToAdd) return;
    await api.addWatchlistItem(Number(selectedWatchlistId), {
      item_type: "role_family",
      item_value: roleFamilyToAdd,
    });
    const itemRows = await api.watchlistItems(Number(selectedWatchlistId));
    setItems(itemRows);
    refreshWatchlists();
  };

  const removeItem = async (item: WatchlistItem) => {
    if (!selectedWatchlistId) return;
    await api.removeWatchlistItem(Number(selectedWatchlistId), item.item_type, item.item_value);
    const itemRows = await api.watchlistItems(Number(selectedWatchlistId));
    setItems(itemRows);
    const radarRows = await api.radar({ watchlist_id: Number(selectedWatchlistId), weeks });
    setRadar(radarRows);
    refreshWatchlists();
  };

  const companyItems = items.filter((i) => i.item_type === "company");
  const roleItems = items.filter((i) => i.item_type === "role_family");

  const roleSummary = useMemo(() => {
    const map: Record<string, number> = {};
    (radar?.role_deltas ?? []).forEach((row) => {
      map[row.role_family] = (map[row.role_family] || 0) + row.net;
    });
    return Object.entries(map)
      .map(([role_family, net]) => ({ role_family, net }))
      .sort((a, b) => Math.abs(b.net) - Math.abs(a.net))
      .slice(0, 12);
  }, [radar]);

  const locationSummary = useMemo(() => {
    const map: Record<string, number> = {};
    (radar?.location_deltas ?? []).forEach((row) => {
      map[row.location_label] = (map[row.location_label] || 0) + row.net;
    });
    return Object.entries(map)
      .map(([location_label, net]) => ({ location_label, net }))
      .sort((a, b) => Math.abs(b.net) - Math.abs(a.net))
      .slice(0, 12);
  }, [radar]);

  const totalActiveJobs = useMemo(
    () => (radar?.companies ?? []).reduce((sum, row) => sum + row.active_jobs, 0),
    [radar]
  );
  const totalNet = useMemo(
    () => (radar?.weekly_momentum ?? []).reduce((sum, row) => sum + row.net, 0),
    [radar]
  );

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold">Radar</h2>
        <p className="text-muted text-sm mt-1">Competitor watchlists and hiring momentum</p>
      </div>

      <div className="bg-card border border-card-border rounded-xl p-4 space-y-3">
        <div className="flex flex-wrap gap-3">
          <select
            value={selectedWatchlistId}
            onChange={(e) => {
              const next = e.target.value ? Number(e.target.value) : "";
              setSelectedWatchlistId(next);
              if (!next) {
                setItems([]);
                setRadar(null);
              }
            }}
            className="bg-background border border-card-border rounded-lg px-3 py-2 text-sm text-foreground"
          >
            <option value="">Select watchlist</option>
            {watchlists.map((w) => (
              <option key={w.id} value={w.id}>{w.name} ({w.company_count} companies)</option>
            ))}
          </select>
          <select
            value={weeks}
            onChange={(e) => setWeeks(Number(e.target.value))}
            className="bg-background border border-card-border rounded-lg px-3 py-2 text-sm text-foreground"
          >
            {[4, 8, 12, 16].map((w) => <option key={w} value={w}>{w} weeks</option>)}
          </select>
        </div>
        <div className="flex flex-wrap gap-3">
          <input
            type="text"
            placeholder="New watchlist name..."
            value={watchlistName}
            onChange={(e) => setWatchlistName(e.target.value)}
            className="bg-background border border-card-border rounded-lg px-3 py-2 text-sm text-foreground w-full sm:w-64"
          />
          <button
            onClick={() => { void createWatchlist(); }}
            className="px-3 py-2 text-xs bg-accent text-white rounded-lg hover:bg-accent/90 transition-colors"
          >
            Create watchlist
          </button>
        </div>
        {selectedWatchlistId && (
          <div className="flex flex-wrap gap-3">
            <select
              value={companyToAdd}
              onChange={(e) => setCompanyToAdd(e.target.value ? Number(e.target.value) : "")}
              className="bg-background border border-card-border rounded-lg px-3 py-2 text-sm text-foreground"
            >
              <option value="">Add company</option>
              {companies.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
            <button
              onClick={() => { void addCompany(); }}
              className="px-3 py-2 text-xs bg-card border border-card-border rounded-lg text-muted hover:text-foreground"
            >
              Add company
            </button>
            <select
              value={roleFamilyToAdd}
              onChange={(e) => setRoleFamilyToAdd(e.target.value)}
              className="bg-background border border-card-border rounded-lg px-3 py-2 text-sm text-foreground"
            >
              <option value="">Add role family</option>
              {roleFamilies.map((r) => (
                <option key={r.role_family} value={r.role_family}>{r.role_family}</option>
              ))}
            </select>
            <button
              onClick={() => { void addRoleFamily(); }}
              className="px-3 py-2 text-xs bg-card border border-card-border rounded-lg text-muted hover:text-foreground"
            >
              Add role family
            </button>
          </div>
        )}
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KpiCard label="Competitors" value={companyItems.length} />
        <KpiCard label="Tracked Roles" value={roleItems.length} />
        <KpiCard label="Active Jobs" value={totalActiveJobs} />
        <KpiCard label="Net Hiring Momentum" value={totalNet} />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-card border border-card-border rounded-xl p-5">
          <h3 className="text-sm font-semibold text-muted mb-4">Net Hiring Momentum by Week</h3>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={radar?.weekly_momentum ?? []}>
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
          <h3 className="text-sm font-semibold text-muted mb-4">Role-family Delta</h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={roleSummary}>
              <CartesianGrid stroke="#1f2430" strokeDasharray="3 3" />
              <XAxis dataKey="role_family" tick={{ fill: "#9ca3af", fontSize: 11 }} />
              <YAxis tick={{ fill: "#9ca3af", fontSize: 11 }} />
              <Tooltip
                contentStyle={{ background: "#1a1d27", border: "1px solid #2a2d3a", borderRadius: 8 }}
                labelStyle={{ color: "#e5e7eb" }}
                itemStyle={{ color: "#e5e7eb" }}
              />
              <Bar dataKey="net">
                {roleSummary.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-card border border-card-border rounded-xl p-5">
          <h3 className="text-sm font-semibold text-muted mb-4">Competitor Momentum</h3>
          <div className="space-y-2 max-h-[320px] overflow-auto">
            {(radar?.companies ?? []).map((c) => (
              <div key={c.company_id} className="flex items-center justify-between text-sm border-b border-card-border/40 pb-2">
                <span className="truncate pr-3">{c.name}</span>
                <span className="font-mono text-xs">{c.net > 0 ? `+${c.net}` : c.net}</span>
              </div>
            ))}
            {(radar?.companies ?? []).length === 0 && (
              <p className="text-xs text-muted">Add companies to start the radar.</p>
            )}
          </div>
        </div>

        <div className="bg-card border border-card-border rounded-xl p-5">
          <h3 className="text-sm font-semibold text-muted mb-4">Location Delta</h3>
          <div className="space-y-2 max-h-[320px] overflow-auto">
            {locationSummary.map((row) => (
              <div key={row.location_label} className="flex items-center justify-between text-sm border-b border-card-border/40 pb-2">
                <span className="truncate pr-3">{row.location_label}</span>
                <span className="font-mono text-xs">{row.net > 0 ? `+${row.net}` : row.net}</span>
              </div>
            ))}
            {locationSummary.length === 0 && (
              <p className="text-xs text-muted">No location movement yet.</p>
            )}
          </div>
        </div>
      </div>

      {selectedWatchlistId && (
        <div className="bg-card border border-card-border rounded-xl p-5">
          <h3 className="text-sm font-semibold text-muted mb-3">Watchlist Items</h3>
          <div className="flex flex-wrap gap-2">
            {items.map((item) => (
              <button
                key={`${item.item_type}:${item.item_value}`}
                onClick={() => { void removeItem(item); }}
                className="px-2 py-1 text-xs bg-background border border-card-border rounded-lg text-muted hover:text-red"
                title="Remove item"
              >
                {item.item_type === "company" ? (item.company_name || item.item_value) : item.item_value} x
              </button>
            ))}
            {items.length === 0 && <p className="text-xs text-muted">No items yet.</p>}
          </div>
        </div>
      )}
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
