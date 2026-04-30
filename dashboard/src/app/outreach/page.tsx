"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { api, OutreachDraft, OutreachListResponse, OutreachStatus, ReplyBreakdown } from "@/lib/api";
import { DraftCard } from "@/components/outreach/DraftCard";
import { MultiValuePicker } from "@/components/MultiValuePicker";
import { useAuth } from "@/components/AuthProvider";

const STATUS_TABS: { value: "" | OutreachStatus; label: string }[] = [
  { value: "", label: "All" },
  { value: "draft", label: "Draft" },
  { value: "sent", label: "Sent" },
  { value: "replied", label: "Replied" },
  { value: "no_reply", label: "No reply" },
  { value: "bounced", label: "Bounced" },
];

const ARCHETYPES = ["recruiter", "hiring_manager", "recent_joiner"];

export default function OutreachPage() {
  return (
    <Suspense fallback={<div className="text-muted text-sm">Loading…</div>}>
      <OutreachInner />
    </Suspense>
  );
}

function OutreachInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user, loading: authLoading } = useAuth();

  // Filter state — initialized from URL search params so deep links work and
  // the user can share filtered views.
  const [data, setData] = useState<OutreachListResponse | null>(null);
  const [reply, setReply] = useState<ReplyBreakdown | null>(null);
  const [companies, setCompanies] = useState<{ company_id: number; company_name: string; n: number }[]>([]);

  const initialStatus = (searchParams.get("status") as OutreachStatus | null) ?? "";
  const initialArchetype = searchParams.get("archetype") ?? "";
  const initialOverdue = searchParams.get("overdue_only") === "true";
  const initialCompanyIds = (searchParams.get("company_ids") || "")
    .split(",")
    .map((v) => v.trim())
    .filter(Boolean);
  const initialJobId = searchParams.get("job") ? Number(searchParams.get("job")) : null;

  const [status, setStatus] = useState<"" | OutreachStatus>(initialStatus as "" | OutreachStatus);
  const [archetype, setArchetype] = useState<string>(initialArchetype);
  const [overdueOnly, setOverdueOnly] = useState(initialOverdue);
  const [companyIds, setCompanyIds] = useState<string[]>(initialCompanyIds);
  const [jobId, setJobId] = useState<number | null>(initialJobId);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  // Fetch the company list once (used to populate the multi-select).
  // Skip when anonymous — endpoint is auth-gated and would 401.
  useEffect(() => {
    if (!user) return;
    void api
      .outreachCompanies()
      .then((d) => setCompanies(d.companies))
      .catch(() => {
        // Non-fatal: the dropdown just stays empty.
      });
  }, [user]);

  // Push filter changes to the URL so the view is shareable.
  useEffect(() => {
    const params = new URLSearchParams();
    if (status) params.set("status", status);
    if (archetype) params.set("archetype", archetype);
    if (overdueOnly) params.set("overdue_only", "true");
    if (companyIds.length) params.set("company_ids", companyIds.join(","));
    if (jobId) params.set("job", String(jobId));
    const qs = params.toString();
    router.replace(qs ? `/outreach?${qs}` : "/outreach", { scroll: false });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status, archetype, overdueOnly, companyIds, jobId]);

  const refresh = () => {
    if (!user) return;  // anonymous: nothing to fetch (endpoints are auth-gated)
    setLoading(true);
    setErr(null);
    Promise.all([
      api.outreachListDrafts({
        status: status || undefined,
        archetype: archetype || undefined,
        overdue_only: overdueOnly || undefined,
        company_ids: companyIds.length ? companyIds.map(Number) : undefined,
        job_id: jobId ?? undefined,
      }),
      api.outreachReplyBreakdown(),
    ])
      .then(([list, breakdown]) => {
        setData(list);
        setReply(breakdown);
      })
      .catch((e) => setErr(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status, archetype, overdueOnly, companyIds, jobId, user]);

  // Anonymous: render a friendly empty state instead of the empty filter UI.
  if (!authLoading && !user) {
    return <AnonymousOutreachEmptyState />;
  }

  const counts = data?.counts;
  const drafts = data?.drafts ?? [];

  const groupedByCompany = useMemo(() => {
    const groups = new Map<string, { company_name: string; company_id?: number; drafts: OutreachDraft[] }>();
    for (const d of drafts) {
      const key = `${d.company_id ?? 0}|${d.company_name ?? ""}`;
      if (!groups.has(key)) {
        groups.set(key, {
          company_name: d.company_name ?? "—",
          company_id: d.company_id,
          drafts: [],
        });
      }
      groups.get(key)!.drafts.push(d);
    }
    return Array.from(groups.values());
  }, [drafts]);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold">My Outreach</h2>
        <p className="text-muted text-sm mt-1">
          Every draft you've generated, with lifecycle tracking. Mark sends from the per-job
          panel and replies will be flagged here when overdue.
        </p>
      </div>

      {reply && (reply.totals.replied + reply.totals.sent + reply.totals.no_reply) > 0 && (
        <ResponseStatsPanel data={reply} />
      )}

      <div className="grid grid-cols-2 md:grid-cols-6 gap-3">
        {STATUS_TABS.map((tab) => {
          const n = tab.value === "" ? drafts.length : counts?.by_status?.[tab.value as OutreachStatus] ?? 0;
          const active = status === tab.value;
          return (
            <button
              key={tab.value}
              onClick={() => setStatus(tab.value)}
              className={`text-left px-3 py-2 rounded-lg border transition-colors ${
                active
                  ? "border-accent bg-accent/10 text-accent-light"
                  : "border-card-border bg-card hover:border-accent-light/40"
              }`}
            >
              <div className="text-[10px] uppercase tracking-wide text-muted">{tab.label}</div>
              <div className="text-lg font-semibold">{n}</div>
            </button>
          );
        })}
      </div>

      <div className="bg-card border border-card-border rounded-xl p-4 space-y-3">
        <div className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-1 text-xs flex-1 min-w-[260px]">
            <span className="text-muted">Companies</span>
            <MultiValuePicker
              placeholder={
                companies.length
                  ? `Filter by company (${companies.length} with outreach)`
                  : "Loading companies…"
              }
              options={companies.map((c) => ({
                value: String(c.company_id),
                label: `${c.company_name} (${c.n})`,
              }))}
              values={companyIds}
              onChange={setCompanyIds}
            />
          </label>
          <label className="flex flex-col gap-1 text-xs">
            <span className="text-muted">Archetype</span>
            <select
              value={archetype}
              onChange={(e) => setArchetype(e.target.value)}
              className="bg-background border border-card-border rounded-lg px-2 py-1.5 text-sm text-foreground"
            >
              <option value="">All</option>
              {ARCHETYPES.map((a) => (
                <option key={a} value={a}>{a.replace("_", " ")}</option>
              ))}
            </select>
          </label>
          <label className="flex items-center gap-2 text-xs cursor-pointer pb-1.5">
            <input
              type="checkbox"
              checked={overdueOnly}
              onChange={(e) => setOverdueOnly(e.target.checked)}
            />
            <span>Overdue only ({counts?.overdue ?? 0})</span>
          </label>
          <button
            type="button"
            onClick={refresh}
            className="ml-auto text-xs text-muted hover:text-foreground pb-1.5"
          >
            Refresh
          </button>
        </div>
        {jobId && (
          <div className="flex items-center gap-2 text-xs bg-accent/10 border border-accent/30 rounded-lg px-3 py-2">
            <span className="text-accent-light">▶</span>
            <span className="text-foreground">
              Filtered to a single job (id <span className="font-mono">{jobId}</span>) — drilled in from /pipeline
            </span>
            <button
              type="button"
              onClick={() => setJobId(null)}
              className="ml-auto text-muted hover:text-foreground"
            >
              Clear
            </button>
          </div>
        )}
      </div>

      {err && (
        <div className="border border-red/40 bg-red/10 rounded-lg p-3 text-sm text-red">{err}</div>
      )}

      {loading && <p className="text-sm text-muted">Loading…</p>}

      {!loading && drafts.length === 0 && (
        <div className="bg-card border border-card-border rounded-xl p-8 text-center text-muted">
          <p className="text-sm">No drafts match these filters.</p>
          <p className="text-xs mt-2">
            Generate outreach from <Link href="/jobs" className="text-accent-light hover:underline">/jobs</Link>{" "}
            or <Link href="/fit" className="text-accent-light hover:underline">/fit</Link>.
          </p>
        </div>
      )}

      <div className="space-y-6">
        {groupedByCompany.map((group) => (
          <section key={`${group.company_id}-${group.company_name}`} className="space-y-3">
            <header className="flex items-baseline gap-3">
              <h3 className="font-semibold">
                {group.company_id ? (
                  <Link href={`/companies/${group.company_id}`} className="hover:text-accent-light">
                    {group.company_name}
                  </Link>
                ) : (
                  group.company_name
                )}
              </h3>
              <span className="text-xs text-muted">
                {group.drafts.length} draft{group.drafts.length === 1 ? "" : "s"}
              </span>
            </header>
            <div className="space-y-3">
              {group.drafts.map((d) => (
                <div key={d.id ?? `${d.person_id}-${d.archetype}`}>
                  <p className="text-[11px] text-muted mb-1">
                    Job:{" "}
                    {d.job_url ? (
                      <a href={d.job_url} target="_blank" rel="noopener noreferrer" className="text-accent-light hover:underline">
                        {d.job_title}
                      </a>
                    ) : (
                      d.job_title ?? "—"
                    )}
                  </p>
                  <DraftCard draft={d} onUpdate={refresh} />
                </div>
              ))}
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}

/**
 * Empty state shown to anonymous users — explains what /outreach would do
 * once they sign in, and points them at the surfaces where they can already
 * draft messages without an account.
 */
function AnonymousOutreachEmptyState() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold">My Outreach</h2>
        <p className="text-muted text-sm mt-1">
          Tracks the lifecycle of every outreach you send: sent / replied / overdue,
          response rates by category, and per-company rollups.
        </p>
      </div>

      <div className="bg-card border border-card-border rounded-xl p-6 space-y-4">
        <p className="text-sm">
          You're browsing as a guest. <Link href="/login" className="text-accent-light hover:underline">Sign in</Link>{" "}
          to start tracking your outreach pipeline here.
        </p>
        <p className="text-xs text-muted">
          You can still draft messages without an account — open any job on{" "}
          <Link href="/jobs" className="text-accent-light hover:underline">/jobs</Link> or{" "}
          <Link href="/fit" className="text-accent-light hover:underline">/fit</Link>{" "}
          and click <em>Reach out</em>. To save and follow up on those drafts later,
          you'll need to sign in.
        </p>
      </div>
    </div>
  );
}

/**
 * Response breakdown panel — top-of-page dashboard for /outreach.
 * Shows: total sent / replied / awaiting + a stacked bar of reply categories
 * (positive / interview / neutral / negative) and the overall reply rate.
 */
function ResponseStatsPanel({ data }: { data: ReplyBreakdown }) {
  const t = data.totals;
  const c = data.by_category;
  const replied = t.replied;
  const positive = c.positive ?? 0;
  const interview = c.interview ?? 0;
  const neutral = c.neutral ?? 0;
  const negative = c.negative ?? 0;
  const categorized = positive + interview + neutral + negative;
  const uncategorized = Math.max(0, replied - categorized);

  // Bar segments — only render if there's something to show.
  const segments: { key: string; label: string; n: number; cls: string }[] = [
    { key: "positive", label: "positive", n: positive, cls: "bg-green" },
    { key: "interview", label: "interview", n: interview, cls: "bg-green/60" },
    { key: "neutral", label: "neutral", n: neutral, cls: "bg-yellow-400/60" },
    { key: "negative", label: "negative", n: negative, cls: "bg-red/70" },
    { key: "unc", label: "uncategorized", n: uncategorized, cls: "bg-card-border" },
  ].filter((s) => s.n > 0);
  const total = segments.reduce((a, s) => a + s.n, 0) || 1;

  return (
    <div className="bg-card border border-card-border rounded-xl p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-3 mb-3">
        <div>
          <p className="text-xs uppercase tracking-wide text-muted">Responses</p>
          <p className="text-sm">
            <span className="text-foreground">{replied}</span>
            <span className="text-muted"> replied</span>
            {" · "}
            <span className="text-foreground">{t.awaiting_reply}</span>
            <span className="text-muted"> awaiting</span>
            {" · "}
            <span className="text-foreground">{t.no_reply}</span>
            <span className="text-muted"> no reply</span>
          </p>
        </div>
        <div className="text-right">
          <p className="text-xs uppercase tracking-wide text-muted">Reply rate</p>
          <p className="text-2xl font-semibold tabular-nums">
            {(t.reply_rate * 100).toFixed(0)}%
          </p>
          <p className="text-[10px] text-muted">
            of {t.sent + t.replied + t.no_reply} decided outreaches
          </p>
        </div>
      </div>

      {replied > 0 ? (
        <>
          <div className="flex h-2 w-full rounded overflow-hidden">
            {segments.map((s) => (
              <div
                key={s.key}
                className={s.cls}
                style={{ width: `${(s.n / total) * 100}%` }}
                title={`${s.label}: ${s.n}`}
              />
            ))}
          </div>
          <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[11px]">
            {segments.map((s) => (
              <span key={s.key} className="flex items-center gap-1.5">
                <span className={`inline-block w-2 h-2 rounded-sm ${s.cls}`} />
                <span className="text-foreground">{s.n}</span>
                <span className="text-muted">{s.label}</span>
              </span>
            ))}
          </div>
        </>
      ) : (
        <p className="text-xs text-muted">
          No replies recorded yet. Mark replies as positive / neutral / negative / interview from any sent draft.
        </p>
      )}
    </div>
  );
}
