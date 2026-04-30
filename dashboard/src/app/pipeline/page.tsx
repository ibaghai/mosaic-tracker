"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { api, JobStatus, PipelineJob, PipelineResponse } from "@/lib/api";
import { formatSeniority, formatWorkModel } from "@/lib/format";
import { JobStatusPill } from "@/components/JobStatusPill";
import { OutreachSummaryBadge } from "@/components/outreach/OutreachSummaryBadge";

const STATUS_TABS: { value: "" | JobStatus; label: string; tone: string }[] = [
  { value: "", label: "All", tone: "border-card-border" },
  { value: "saved", label: "Saved", tone: "border-yellow-400/40 text-yellow-300" },
  { value: "applied", label: "Applied", tone: "border-accent/40 text-accent-light" },
  { value: "interviewing", label: "Interviewing", tone: "border-accent/60 text-accent-light" },
  { value: "offered", label: "Offered", tone: "border-green/40 text-green" },
  { value: "rejected", label: "Rejected", tone: "border-red/40 text-red" },
  { value: "dismissed", label: "Dismissed", tone: "border-card-border text-muted" },
];

const KANBAN_ORDER: JobStatus[] = [
  "saved",
  "applied",
  "interviewing",
  "offered",
  "rejected",
  "dismissed",
];

const STATUS_LABELS: Record<JobStatus, string> = {
  saved: "Saved",
  applied: "Applied",
  interviewing: "Interviewing",
  offered: "Offered",
  rejected: "Rejected",
  dismissed: "Dismissed",
};

export default function PipelinePage() {
  const [data, setData] = useState<PipelineResponse | null>(null);
  const [status, setStatus] = useState<"" | JobStatus>("");
  const [view, setView] = useState<"list" | "kanban">("list");
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const refresh = () => {
    setLoading(true);
    setErr(null);
    api
      .pipeline(status || undefined)
      .then(setData)
      .catch((e) => setErr(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status]);

  const jobs = data?.jobs ?? [];
  const counts = data?.counts ?? {};

  const grouped = useMemo(() => {
    const groups: Record<JobStatus, PipelineJob[]> = {
      saved: [], applied: [], interviewing: [], offered: [], rejected: [], dismissed: [],
    };
    for (const j of jobs) groups[j.status]?.push(j);
    return groups;
  }, [jobs]);

  return (
    <div className="space-y-6">
      <div className="flex items-baseline justify-between">
        <div>
          <h2 className="text-2xl font-bold">My Pipeline</h2>
          <p className="text-muted text-sm mt-1">
            Jobs you've saved, applied to, or are progressing through. Set status from any job
            row in <Link href="/jobs" className="text-accent-light hover:underline">/jobs</Link>,{" "}
            <Link href="/fit" className="text-accent-light hover:underline">/fit</Link>, or a company page.
          </p>
        </div>
        <div className="flex gap-2 text-xs">
          <button
            onClick={() => setView("list")}
            className={`px-3 py-1.5 rounded-lg border ${view === "list" ? "border-accent bg-accent/10 text-accent-light" : "border-card-border text-muted hover:text-foreground"}`}
          >
            List
          </button>
          <button
            onClick={() => setView("kanban")}
            className={`px-3 py-1.5 rounded-lg border ${view === "kanban" ? "border-accent bg-accent/10 text-accent-light" : "border-card-border text-muted hover:text-foreground"}`}
          >
            Kanban
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-7 gap-3">
        {STATUS_TABS.map((tab) => {
          const n = tab.value === "" ? jobs.length : counts[tab.value as JobStatus] ?? 0;
          const active = status === tab.value;
          return (
            <button
              key={tab.value}
              onClick={() => setStatus(tab.value)}
              className={`text-left px-3 py-2 rounded-lg border transition-colors ${
                active
                  ? "border-accent bg-accent/10 text-accent-light"
                  : `bg-card hover:border-accent-light/40 ${tab.tone}`
              }`}
            >
              <div className="text-[10px] uppercase tracking-wide text-muted">{tab.label}</div>
              <div className="text-lg font-semibold">{n}</div>
            </button>
          );
        })}
      </div>

      {err && (
        <div className="border border-red/40 bg-red/10 rounded-lg p-3 text-sm text-red">{err}</div>
      )}
      {loading && <p className="text-sm text-muted">Loading…</p>}

      {!loading && jobs.length === 0 && (
        <div className="bg-card border border-card-border rounded-xl p-8 text-center text-muted">
          <p className="text-sm">No jobs match these filters.</p>
          <p className="text-xs mt-2">
            Save a job from{" "}
            <Link href="/jobs" className="text-accent-light hover:underline">/jobs</Link>{" "}
            to start tracking.
          </p>
        </div>
      )}

      {!loading && jobs.length > 0 && view === "list" && (
        <div className="bg-card border border-card-border rounded-xl overflow-hidden">
          <table className="w-full text-sm min-w-[760px]">
            <thead className="sticky top-0 bg-card z-10">
              <tr className="text-muted text-left border-b border-card-border">
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Job</th>
                <th className="px-4 py-3 font-medium">Company</th>
                <th className="px-4 py-3 font-medium">Seniority</th>
                <th className="px-4 py-3 font-medium">Work Model</th>
                <th className="px-4 py-3 font-medium">Outreach</th>
                <th className="px-4 py-3 font-medium">Updated</th>
                <th className="px-4 py-3 font-medium">Open</th>
              </tr>
            </thead>
            <tbody>
              {jobs.map((j) => (
                <tr key={j.job_id} className="border-b border-card-border/50 hover:bg-white/5">
                  <td className="px-4 py-2.5">
                    <JobStatusPill jobId={j.job_id} initialStatus={j.status} onChange={refresh} />
                  </td>
                  <td className="px-4 py-2.5 font-medium">
                    <Link href={`/fit?jobId=${j.job_id}`} className="hover:text-accent-light">
                      {j.job_title}
                    </Link>
                  </td>
                  <td className="px-4 py-2.5">
                    <Link href={`/companies/${j.company_id}`} className="text-muted hover:text-accent-light">
                      {j.company_name}
                    </Link>
                  </td>
                  <td className="px-4 py-2.5 text-muted text-xs">{formatSeniority(j.seniority)}</td>
                  <td className="px-4 py-2.5 text-muted text-xs">{formatWorkModel(j.work_model)}</td>
                  <td className="px-4 py-2.5">
                    <OutreachSummaryBadge jobId={j.job_id} summary={j.outreach} />
                  </td>
                  <td className="px-4 py-2.5 text-muted text-xs">
                    {new Date(j.action_at).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-2.5">
                    {j.job_url && (
                      <a
                        href={j.job_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-accent-light hover:underline text-xs"
                      >
                        Apply →
                      </a>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {!loading && jobs.length > 0 && view === "kanban" && (
        <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-6 gap-3">
          {KANBAN_ORDER.map((s) => (
            <section key={s} className="bg-card border border-card-border rounded-xl p-3 min-h-[200px]">
              <header className="flex items-baseline justify-between mb-2">
                <h3 className="text-xs uppercase tracking-wide text-muted">{STATUS_LABELS[s]}</h3>
                <span className="text-xs text-muted">{grouped[s].length}</span>
              </header>
              <div className="space-y-2">
                {grouped[s].map((j) => (
                  <div key={j.job_id} className="bg-background border border-card-border rounded-lg p-2 text-xs">
                    <Link
                      href={`/fit?jobId=${j.job_id}`}
                      className="block font-medium hover:text-accent-light"
                    >
                      {j.job_title}
                    </Link>
                    <Link
                      href={`/companies/${j.company_id}`}
                      className="block text-muted text-[11px] mt-1 hover:text-accent-light"
                    >
                      {j.company_name}
                    </Link>
                    <div className="mt-1.5">
                      <OutreachSummaryBadge jobId={j.job_id} summary={j.outreach} variant="compact" />
                    </div>
                    <div className="mt-2 flex items-center justify-between">
                      <JobStatusPill
                        jobId={j.job_id}
                        initialStatus={j.status}
                        onChange={refresh}
                      />
                      {j.job_url && (
                        <a
                          href={j.job_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-accent-light hover:underline text-[11px]"
                        >
                          Apply →
                        </a>
                      )}
                    </div>
                  </div>
                ))}
                {grouped[s].length === 0 && (
                  <p className="text-[11px] text-muted text-center pt-4">empty</p>
                )}
              </div>
            </section>
          ))}
        </div>
      )}
    </div>
  );
}
