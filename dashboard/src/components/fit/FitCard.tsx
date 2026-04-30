"use client";

import Link from "next/link";
import { JobFitMatch } from "@/lib/api";
import { formatRoleFamily, formatSeniority, formatWorkModel } from "@/lib/format";
import { JobStatusPill } from "@/components/JobStatusPill";
import { ReachOutPanel } from "@/components/outreach/ReachOutPanel";

function scoreColor(score: number) {
  if (score >= 80) return "text-green";
  if (score >= 65) return "text-accent-light";
  if (score >= 50) return "text-yellow-400";
  return "text-red";
}

/**
 * Big result card for a single resume-vs-job fit. Used by /fit and by the
 * "score against filtered jobs" panel on /jobs. Includes the score, why /
 * gaps / pointers, location note, status pill, and the reach-out panel.
 */
export function FitCard({ match, resumeFile }: { match: JobFitMatch; resumeFile: File | null }) {
  return (
    <article className="bg-card border border-card-border rounded-xl p-5">
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="font-semibold">{match.job.title}</h3>
            {match.cached && (
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-background text-muted border border-card-border">
                cached
              </span>
            )}
          </div>
          <p className="text-sm text-muted mt-1">
            <Link href={`/companies/${match.job.company_id}`} className="hover:text-accent-light">
              {match.job.company_name}
            </Link>
            {match.job.sector ? ` · ${match.job.sector}` : ""}
          </p>
          <p className="text-xs text-muted mt-2">
            {formatRoleFamily(match.job.role_family)} · {formatSeniority(match.job.seniority)} · {formatWorkModel(match.job.work_model)}
            {match.job.location ? ` · ${match.job.location}` : ""}
          </p>
        </div>
        <div className="md:text-right">
          <p className={`text-3xl font-bold font-mono ${scoreColor(match.fit_score)}`}>{match.fit_score}</p>
          <p className="text-xs text-muted">{match.verdict}</p>
          <p className="text-[10px] text-muted mt-1">shortlist {match.deterministic_score}</p>
        </div>
      </div>

      {match.matched_skills.length > 0 && (
        <div className="mt-4 flex flex-wrap gap-1.5">
          {match.matched_skills.map((skill) => (
            <span key={skill} className="px-2 py-1 rounded-full bg-green/10 text-green text-xs">
              {skill}
            </span>
          ))}
        </div>
      )}

      <div className="mt-5 grid gap-4 md:grid-cols-3">
        <ReasonBlock title="Why" rows={match.why} />
        <ReasonBlock title="Gaps" rows={match.gaps} />
        <ReasonBlock title="Pointers" rows={match.resume_pointers} />
      </div>

      {match.location_note && (
        <p className={`mt-4 text-xs ${match.location_blocker ? "text-red" : "text-muted"}`}>
          {match.location_note}
        </p>
      )}

      <div className="mt-4 flex flex-wrap items-center gap-3 text-xs">
        {match.job.url && (
          <a href={match.job.url} target="_blank" rel="noopener noreferrer" className="text-accent-light hover:underline">
            Apply
          </a>
        )}
        <Link href={`/fit?jobId=${match.job.id}`} className="text-muted hover:text-foreground">
          Focus on this job
        </Link>
        <span className="ml-auto">
          <JobStatusPill jobId={match.job.id} />
        </span>
      </div>

      <ReachOutPanel jobId={match.job.id} resumeFile={resumeFile} />
    </article>
  );
}

function ReasonBlock({ title, rows }: { title: string; rows: string[] }) {
  return (
    <div>
      <p className="text-xs font-semibold text-muted mb-2">{title}</p>
      {rows.length ? (
        <ul className="space-y-1.5 text-sm text-foreground">
          {rows.map((row, index) => (
            <li key={`${title}-${index}`} className="leading-relaxed">
              {row}
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-muted">No notes.</p>
      )}
    </div>
  );
}
