"use client";

import { useState } from "react";
import { api, FitMatchesResponse, JobRow } from "@/lib/api";
import { formatRoleFamily, formatSeniority } from "@/lib/format";
import { FitCard } from "@/components/fit/FitCard";

/**
 * Inline panel for /jobs that lets the user score their resume against the
 * currently-filtered job set.
 *
 * Design: collapsed by default to keep the page tidy. Once expanded, takes
 * a resume file + match-count and POSTs to /api/fit/from-jobs with the
 * visible job ids. Results render below as full FitCards.
 *
 * No account required — scoring just runs and the results live in browser
 * state. Save / track actions on each FitCard prompt sign-in inline.
 */
export function ScoreFilteredJobsPanel({ jobs }: { jobs: JobRow[] }) {
  const [open, setOpen] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [limit, setLimit] = useState(10);
  const [data, setData] = useState<FitMatchesResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const visibleIds = jobs.slice(0, 500).map((j) => j.id);
  const cap = visibleIds.length;
  const max = Math.min(40, cap);

  const score = async () => {
    if (!file || loading || visibleIds.length === 0) return;
    setLoading(true);
    setErr(null);
    setData(null);
    try {
      const res = await api.fitFromJobs(file, visibleIds, Math.min(limit, max));
      setData(res);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-card border border-card-border rounded-xl">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-4 py-3 text-left"
      >
        <div>
          <p className="text-sm font-medium">
            Score my resume against {cap === 0 ? "these" : cap.toLocaleString()} filtered job{cap === 1 ? "" : "s"}
          </p>
          <p className="text-xs text-muted mt-0.5">
            Upload your resume → get the top-N best fits from this exact filter set.
            {cap > 500 && " (Capped at 500 — narrow the filter further if you want a smaller pool.)"}
          </p>
        </div>
        <span className="text-accent-light text-sm">{open ? "▾" : "▸"}</span>
      </button>

      {open && (
        <div className="px-4 pb-4 space-y-4 border-t border-card-border pt-4">
          {cap === 0 ? (
            <p className="text-sm text-muted">
              No jobs match the current filters — adjust the filters above first.
            </p>
          ) : (
            <>
              <div className="flex flex-wrap items-end gap-3">
                <label className="flex flex-col gap-1 text-xs flex-1 min-w-[260px]">
                  <span className="text-muted">Resume</span>
                  <input
                    type="file"
                    accept=".txt,.md,.pdf,.docx"
                    onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                    className="text-sm text-muted file:mr-3 file:rounded-lg file:border file:border-card-border file:bg-background file:px-3 file:py-2 file:text-foreground"
                  />
                </label>
                <label className="flex flex-col gap-1 text-xs">
                  <span className="text-muted">Top N</span>
                  <input
                    type="number"
                    min={1}
                    max={max || 1}
                    value={limit}
                    onChange={(e) => setLimit(Math.max(1, Math.min(40, Number(e.target.value))))}
                    className="w-24 px-2 py-1.5 bg-background border border-card-border rounded-lg text-sm"
                  />
                </label>
                <button
                  type="button"
                  onClick={score}
                  disabled={!file || loading}
                  className="px-4 py-2 bg-accent text-white text-sm rounded-lg hover:bg-accent-light disabled:opacity-50 transition-colors"
                >
                  {loading
                    ? "Scoring…"
                    : `Score against ${cap.toLocaleString()} job${cap === 1 ? "" : "s"}`}
                </button>
              </div>

              <p className="text-[11px] text-muted">
                Resume text is parsed into a de-identified profile for matching and is not stored.
                Each click costs ~1 LLM call per scored job (so {limit} ≈ {limit} LLM calls).
              </p>

              {err && (
                <p className="text-xs text-red border border-red/40 bg-red/10 rounded-lg p-2">{err}</p>
              )}

              {data && (
                <ResultsBlock data={data} resumeFile={file} />
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}

function ResultsBlock({
  data,
  resumeFile,
}: {
  data: FitMatchesResponse;
  resumeFile: File | null;
}) {
  return (
    <div className="space-y-4">
      <div className="bg-background border border-card-border rounded-lg p-3 text-xs">
        <p className="text-muted">
          Parsed profile:{" "}
          <span className="text-foreground">
            {data.profile.headline || "—"}
          </span>
          {data.profile.target_roles?.length ? (
            <span> · roles: {data.profile.target_roles.slice(0, 3).join(", ")}</span>
          ) : null}
          {data.profile.seniority ? (
            <span> · {formatSeniority(data.profile.seniority)}</span>
          ) : null}
          {data.profile.role_families?.length ? (
            <span> · {data.profile.role_families.map(formatRoleFamily).join(", ")}</span>
          ) : null}
          <span className="text-muted">
            {" "}· {data.shortlist_count} shortlisted → top {data.matches.length}
          </span>
        </p>
      </div>

      <div className="space-y-4">
        {data.matches.map((m) => (
          <FitCard key={m.job.id} match={m} resumeFile={resumeFile} />
        ))}
      </div>
    </div>
  );
}
