"use client";

import Link from "next/link";
import { OutreachJobSummary } from "@/lib/api";

/**
 * Tiny pill that summarises outreach activity for a single job.
 * Renders as `✉ N sent · M replied · K positive` in muted tones.
 * Click → deep-link to /outreach pre-filtered to this job's drafts.
 *
 * Returns nothing if there's been zero outreach (so cards stay clean).
 */
export function OutreachSummaryBadge({
  jobId,
  summary,
  variant = "inline",
}: {
  jobId: number;
  summary?: OutreachJobSummary;
  variant?: "inline" | "compact";
}) {
  const total = summary?.total ?? 0;
  if (total === 0) {
    return variant === "inline" ? (
      <span className="text-[10px] text-muted">no outreach yet</span>
    ) : null;
  }

  const sent = summary?.sent ?? 0;
  const replied = summary?.replied ?? 0;
  const positive = summary?.positive ?? 0;
  const interview = summary?.interview ?? 0;
  const negative = summary?.negative ?? 0;
  const noReply = summary?.no_reply ?? 0;

  const parts: React.ReactNode[] = [];
  parts.push(<span key="t">✉ {total}</span>);
  if (sent) parts.push(<span key="s" className="text-muted">{sent} sent</span>);
  if (replied) parts.push(<span key="r" className="text-accent-light">{replied} replied</span>);
  if (positive) parts.push(<span key="p" className="text-green">{positive} positive</span>);
  if (interview) parts.push(<span key="i" className="text-green">{interview} interview</span>);
  if (negative) parts.push(<span key="n" className="text-red">{negative} negative</span>);
  if (noReply) parts.push(<span key="nr" className="text-muted">{noReply} no reply</span>);

  return (
    <Link
      href={`/outreach?job=${jobId}`}
      className="inline-flex flex-wrap items-center gap-x-1.5 gap-y-0.5 text-[10px] text-foreground hover:text-accent-light"
      title="View these conversations on /outreach"
    >
      {parts.map((p, i) => (
        <span key={i} className="flex items-center gap-1.5">
          {i > 0 && <span className="text-muted">·</span>}
          {p}
        </span>
      ))}
    </Link>
  );
}
