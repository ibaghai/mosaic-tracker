"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { api, SavedSearch } from "@/lib/api";

export default function SavedSearchesPage() {
  const [searches, setSearches] = useState<SavedSearch[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);

  const refresh = () => {
    setLoading(true);
    setErr(null);
    api
      .savedSearchesList()
      .then((d) => setSearches(d.searches))
      .catch((e) => setErr(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false));
  };

  useEffect(refresh, []);

  const grouped = useMemo(() => {
    const m = new Map<string, SavedSearch[]>();
    for (const s of searches) {
      if (!m.has(s.surface)) m.set(s.surface, []);
      m.get(s.surface)!.push(s);
    }
    return Array.from(m.entries()).sort();
  }, [searches]);

  const remove = async (id: number) => {
    if (busyId) return;
    setBusyId(id);
    try {
      await api.savedSearchesDelete(id);
      setSearches((prev) => prev.filter((s) => s.id !== id));
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold">Saved Searches</h2>
        <p className="text-muted text-sm mt-1">
          Snapshots of filter combinations you cared about. Open them from each
          surface&apos;s &ldquo;Load saved&rdquo; dropdown — or jump back here to delete one.
        </p>
      </div>

      {err && (
        <div className="border border-red/40 bg-red/10 rounded-lg p-3 text-sm text-red">{err}</div>
      )}
      {loading && <p className="text-sm text-muted">Loading…</p>}

      {!loading && searches.length === 0 && (
        <div className="bg-card border border-card-border rounded-xl p-8 text-center text-muted">
          <p className="text-sm">You haven&apos;t saved any searches yet.</p>
          <p className="text-xs mt-2">
            Go to <Link href="/jobs" className="text-accent-light hover:underline">/jobs</Link>,
            set some filters, and click <em>Save search</em>.
          </p>
        </div>
      )}

      {grouped.map(([surface, group]) => (
        <section key={surface} className="space-y-2">
          <h3 className="text-sm uppercase tracking-wide text-muted">
            {surface} <span className="text-foreground/60">· {group.length}</span>
          </h3>
          <div className="bg-card border border-card-border rounded-xl divide-y divide-card-border">
            {group.map((s) => (
              <div key={s.id} className="px-4 py-3 flex items-start gap-3">
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-sm">{s.name}</p>
                  <FilterChips surface={s.surface} paramsJson={s.params_json} />
                  <p className="text-[10px] text-muted mt-2">
                    Created {new Date(s.created_at).toLocaleString()}
                  </p>
                </div>
                <div className="flex flex-col gap-2 text-xs">
                  <Link
                    href={surfaceLink(surface)}
                    className="text-accent-light hover:underline text-right"
                  >
                    Open {surface} →
                  </Link>
                  <button
                    type="button"
                    onClick={() => void remove(s.id)}
                    disabled={busyId === s.id}
                    className="text-muted hover:text-red text-right"
                  >
                    {busyId === s.id ? "…" : "Delete"}
                  </button>
                </div>
              </div>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}

/**
 * Render a saved-search's params_json as a row of human-readable chips
 * ("Sector: AI", "Seniority: senior, staff", etc.). Falls back to a JSON
 * preview if the surface is unknown.
 */
function FilterChips({ surface, paramsJson }: { surface: string; paramsJson: string }) {
  let parsed: Record<string, unknown> = {};
  try {
    parsed = JSON.parse(paramsJson) as Record<string, unknown>;
  } catch {
    return <pre className="mt-1 text-[11px] text-muted">{paramsJson}</pre>;
  }

  const chips = paramsToChips(surface, parsed);
  if (chips.length === 0) {
    return <p className="mt-1 text-[11px] text-muted italic">No filters — matches everything</p>;
  }
  return (
    <div className="mt-1.5 flex flex-wrap gap-1.5">
      {chips.map((c, i) => (
        <span
          key={i}
          className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-background border border-card-border text-[11px]"
        >
          <span className="text-muted">{c.label}:</span>
          <span className="text-foreground">{c.value}</span>
        </span>
      ))}
    </div>
  );
}

type Chip = { label: string; value: string };

const JOBS_FILTER_LABELS: Record<string, string> = {
  search: "Title contains",
  sector: "Sector",
  empType: "Employment type",
  skill: "Skill",
  seniority: "Seniority",
  workModel: "Work model",
  companyType: "Company type",
  department: "Department",
  atsType: "ATS",
  fundingRound: "Funding round",
};

function paramsToChips(surface: string, params: Record<string, unknown>): Chip[] {
  const out: Chip[] = [];
  const labels = surface === "jobs" ? JOBS_FILTER_LABELS : null;

  for (const [key, value] of Object.entries(params)) {
    if (value === null || value === undefined || value === "") continue;
    if (Array.isArray(value)) {
      if (value.length === 0) continue;
      out.push({
        label: labels?.[key] ?? prettyKey(key),
        value: value.map((v) => String(v)).join(", "),
      });
    } else {
      out.push({
        label: labels?.[key] ?? prettyKey(key),
        value: String(value),
      });
    }
  }
  return out;
}

function prettyKey(k: string): string {
  // camelCase / snake_case → Title Case fallback
  return k
    .replace(/_/g, " ")
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function surfaceLink(surface: string): string {
  // Future: each surface adds itself here. For now, only /jobs.
  switch (surface) {
    case "jobs":
      return "/jobs";
    case "outreach":
      return "/outreach";
    case "pipeline":
      return "/pipeline";
    case "companies":
      return "/companies";
    default:
      return "/";
  }
}
