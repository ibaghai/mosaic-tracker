"use client";

import { useEffect, useState } from "react";
import { api, OutreachResponse } from "@/lib/api";
import { DraftCard } from "./DraftCard";
import { TailoredResumeBlock } from "./TailoredResumeBlock";

export function ReachOutPanel({
  jobId,
  resumeFile,
  embedded = false,
}: {
  jobId: number;
  resumeFile: File | null;
  /** When true, render the panel pre-opened with no internal toggle.
   *  Use this when the parent already controls visibility (e.g. an inline
   *  row in a table). Auto-fetches drafts on mount. */
  embedded?: boolean;
}) {
  const [open, setOpen] = useState(embedded);
  const [data, setData] = useState<OutreachResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [localFile, setLocalFile] = useState<File | null>(null);

  const effectiveFile = localFile ?? resumeFile;

  const generate = async (file: File | null) => {
    setLoading(true);
    setErr(null);
    try {
      const res = await api.outreachGenerate(jobId, {
        file,
        archetypes: ["recruiter", "hiring_manager", "recent_joiner"],
        enrichTop: 1,
        includeTailoredResume: !!file,
      });
      setData(res);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  const onFilePicked = (file: File | null) => {
    setLocalFile(file);
    if (file) void generate(file);
  };

  // Auto-fetch when embedded mode mounts.
  useEffect(() => {
    if (embedded && !data && !loading) void generate(effectiveFile);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [embedded]);

  return (
    <div className={embedded ? "" : "mt-4 pt-4 border-t border-card-border"}>
      {!embedded && (
        <button
          type="button"
          onClick={() => {
            const next = !open;
            setOpen(next);
            if (next && !data && !loading) void generate(effectiveFile);
          }}
          className="text-sm text-accent-light hover:underline"
        >
          {open ? "▾" : "▸"} Reach out
        </button>
      )}

      {open && (
        <div className="mt-3 space-y-4 text-sm">
          {loading && <p className="text-muted">Searching Apollo + drafting outreach…</p>}
          {err && <p className="text-red text-xs">⚠ {err}</p>}
          {data && (
            <>
              {data.parsed_jd?.jd_missing ? (
                <div className="text-xs bg-yellow-400/10 border border-yellow-400/30 rounded-lg p-2 text-yellow-300">
                  ⚠ This job has no description in the tracker — outreach is using
                  the role title and company only. Drafts may read more generic.
                </div>
              ) : data.parsed_jd && (
                <div className="text-xs text-muted">
                  Parsed: {data.parsed_jd.level} {data.parsed_jd.function}
                  {data.parsed_jd.team_or_org ? ` · ${data.parsed_jd.team_or_org}` : ""}
                  {data.parsed_jd.reports_to_phrase ? (
                    <span> · reports-to: <em>&ldquo;{data.parsed_jd.reports_to_phrase}&rdquo;</em></span>
                  ) : (
                    <span> · reports-to: <em>not stated in JD (inferred)</em></span>
                  )}
                </div>
              )}

              <div className="space-y-3">
                {data.drafts.map((draft, idx) => (
                  <DraftCard key={idx} draft={draft} />
                ))}
                {Object.entries(data.people_by_archetype).map(([archetype, people]) =>
                  people.filter((p) => p._error || p._enrich_error).map((p, i) => (
                    <p key={`${archetype}-err-${i}`} className="text-xs text-red">
                      [{archetype}] {p._error || p._enrich_error}
                    </p>
                  ))
                )}
              </div>

              {data.drafts.length === 0 && (
                <p className="text-xs text-muted">
                  No drafts generated. Try a different role or check the API logs.
                </p>
              )}

              {!effectiveFile && (
                <details className="text-[11px] text-muted">
                  <summary className="cursor-pointer hover:text-foreground">
                    + add resume to personalize and generate a tailored variant
                  </summary>
                  <input
                    type="file"
                    accept=".txt,.md,.pdf,.docx"
                    onChange={(e) => onFilePicked(e.target.files?.[0] ?? null)}
                    className="mt-2 text-xs"
                  />
                </details>
              )}

              {data.tailored_resume && (
                <TailoredResumeBlock tailored={data.tailored_resume} jobTitle={data.job.title} />
              )}

              <p className="text-[10px] text-muted">
                Apollo: {data.apollo_usage.used.calls_today}/{data.apollo_usage.caps.calls_daily} calls today,
                {" "}{data.apollo_usage.used.credits_month}/{data.apollo_usage.caps.credits_monthly} credits this month
                {data.apollo_usage.mock_mode ? " · MOCK MODE" : ""}
              </p>
            </>
          )}
        </div>
      )}
    </div>
  );
}
