"use client";

import Link from "next/link";
import { useState } from "react";
import {
  api,
  SimilarJobMatch,
  SimilarJobsResponse,
} from "@/lib/api";
import { formatRoleFamily, formatSeniority, formatWorkModel } from "@/lib/format";
import { ReachOutPanel } from "@/components/outreach/ReachOutPanel";

export default function JdMatchPage() {
  const [jdText, setJdText] = useState("");
  const [jdUrl, setJdUrl] = useState("");
  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [companyType, setCompanyType] = useState<"" | "startup" | "bigco">("");
  const [limit, setLimit] = useState(10);
  const [data, setData] = useState<SimilarJobsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const search = async () => {
    const trimmedUrl = jdUrl.trim();
    const trimmedText = jdText.trim();
    if (!trimmedUrl && trimmedText.length < 100) {
      setErr("Paste a URL to a JD, or at least 100 characters of JD text.");
      return;
    }
    setLoading(true);
    setErr(null);
    try {
      const res = await api.similarJobsFromJd({
        url: trimmedUrl || undefined,
        jdText: trimmedUrl ? undefined : trimmedText,
        limit,
        companyType: companyType || undefined,
      });
      setData(res);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="px-6 py-8 md:px-8 max-w-5xl">
      <header className="mb-6">
        <h1 className="text-2xl font-semibold">JD Match</h1>
        <p className="text-sm text-muted mt-1">
          Paste a job description you like — we&apos;ll find similar open roles in the tracker
          and (with your resume) generate outreach drafts to reach the right humans at each.
        </p>
      </header>

      <section className="bg-card border border-card-border rounded-xl p-5 space-y-4">
        <div>
          <label className="block text-xs text-muted mb-1">JD URL (Greenhouse, Lever, or any public JD page)</label>
          <input
            type="url"
            value={jdUrl}
            onChange={(e) => setJdUrl(e.target.value)}
            placeholder="https://job-boards.greenhouse.io/<board>/jobs/<id>  or  https://jobs.lever.co/<co>/<id>"
            className="w-full p-2 bg-background border border-card-border rounded-lg text-sm font-mono"
          />
          <p className="text-[11px] text-muted mt-1">
            We fetch the JD on the server (Greenhouse and Lever via their JSON APIs;
            other hosts via HTML extraction). URL takes precedence over pasted text.
          </p>
        </div>

        <div className="flex items-center gap-3 text-[11px] text-muted">
          <span className="flex-1 border-t border-card-border" />
          <span className="uppercase tracking-wide">or paste text below</span>
          <span className="flex-1 border-t border-card-border" />
        </div>

        <div>
          <label className="block text-xs text-muted mb-1">Paste JD text</label>
          <textarea
            value={jdText}
            onChange={(e) => setJdText(e.target.value)}
            placeholder="Paste the full JD here (title + description + requirements)..."
            className="w-full h-48 p-3 bg-background border border-card-border rounded-lg text-sm font-mono"
            disabled={!!jdUrl.trim()}
          />
          <p className="text-[11px] text-muted mt-1">
            {jdText.length} chars · LLM extracts level / function / skills, then matches against the active job pool deterministically.
          </p>
        </div>

        <div className="flex flex-wrap gap-3 items-end">
          <label className="flex flex-col gap-1">
            <span className="text-xs text-muted">Resume (optional, for outreach drafts)</span>
            <input
              type="file"
              accept=".txt,.md,.pdf,.docx"
              onChange={(e) => setResumeFile(e.target.files?.[0] ?? null)}
              className="text-xs"
            />
          </label>

          <label className="flex flex-col gap-1">
            <span className="text-xs text-muted">Top N</span>
            <input
              type="number"
              min={1}
              max={50}
              value={limit}
              onChange={(e) => setLimit(Number(e.target.value) || 10)}
              className="w-24 px-2 py-1 bg-background border border-card-border rounded text-sm"
            />
          </label>

          <label className="flex flex-col gap-1">
            <span className="text-xs text-muted">Company set</span>
            <select
              value={companyType}
              onChange={(e) => setCompanyType(e.target.value as "" | "startup" | "bigco")}
              className="px-2 py-1 bg-background border border-card-border rounded text-sm"
            >
              <option value="">Both</option>
              <option value="startup">Startups</option>
              <option value="bigco">Big companies</option>
            </select>
          </label>

          <button
            type="button"
            onClick={search}
            disabled={loading}
            className="px-4 py-2 bg-accent rounded text-sm font-medium hover:bg-accent-light disabled:opacity-50"
          >
            {loading ? "Searching…" : "Find similar jobs"}
          </button>
        </div>

        {err && <p className="text-red text-xs">⚠ {err}</p>}
      </section>

      {data && (
        <section className="mt-6 space-y-3">
          {data.fetched && (
            <div className="bg-card border border-card-border rounded-lg p-3 text-xs flex flex-wrap items-center gap-x-3 gap-y-1">
              <span className="text-[10px] uppercase tracking-wide text-accent-light">
                Fetched via {data.fetched.source}
              </span>
              {data.fetched.title && (
                <span className="text-foreground font-medium">{data.fetched.title}</span>
              )}
              {data.fetched.company && (
                <span className="text-muted">@ {data.fetched.company}</span>
              )}
              {data.fetched.location && (
                <span className="text-muted">· {data.fetched.location}</span>
              )}
              <span className="ml-auto text-muted">
                {data.fetched.char_count} chars
                {data.fetched.source === "html" && " · lossy HTML extraction"}
              </span>
            </div>
          )}
          <div className="text-xs text-muted">
            Parsed JD: <span className="text-foreground">{data.parsed_jd.role_title || "?"}</span>
            {" · "}
            level <span className="text-foreground">{data.parsed_jd.level || "?"}</span>
            {" · "}
            function <span className="text-foreground">{data.parsed_jd.function || "?"}</span>
            {data.parsed_jd.must_have_skills?.length ? (
              <span> · skills: {data.parsed_jd.must_have_skills.slice(0, 5).join(", ")}</span>
            ) : null}
            <span className="text-muted"> · {data.shortlist_count} candidates → top {data.matches.length}</span>
          </div>

          {data.matches.map((m) => (
            <SimilarJobCard key={m.id} match={m} resumeFile={resumeFile} />
          ))}
        </section>
      )}
    </div>
  );
}

function scoreColor(s: number) {
  if (s >= 80) return "text-green";
  if (s >= 60) return "text-accent-light";
  if (s >= 40) return "text-yellow-400";
  return "text-muted";
}

function SimilarJobCard({ match, resumeFile }: { match: SimilarJobMatch; resumeFile: File | null }) {
  return (
    <article className="bg-card border border-card-border rounded-xl p-5">
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div>
          <h3 className="font-semibold">{match.title}</h3>
          <p className="text-sm text-muted mt-1">
            <Link href={`/companies/${match.company_id}`} className="hover:text-accent-light">
              {match.company_name || "?"}
            </Link>
            {match.sector ? ` · ${match.sector}` : ""}
          </p>
          <p className="text-xs text-muted mt-2">
            {formatRoleFamily(match.role_family)} · {formatSeniority(match.seniority)} · {formatWorkModel(match.work_model)}
            {match.location ? ` · ${match.location}` : ""}
          </p>
        </div>
        <div className="md:text-right">
          <p className={`text-3xl font-bold font-mono ${scoreColor(match.deterministic_score)}`}>
            {Math.round(match.deterministic_score)}
          </p>
          <p className="text-xs text-muted">similarity</p>
        </div>
      </div>

      {match.matched_skills && match.matched_skills.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {match.matched_skills.map((s) => (
            <span key={s} className="px-2 py-1 rounded-full bg-green/10 text-green text-xs">
              {s}
            </span>
          ))}
        </div>
      )}

      <div className="mt-3 flex gap-3 text-xs">
        {match.url && (
          <a href={match.url} target="_blank" rel="noopener noreferrer" className="text-accent-light hover:underline">
            Apply
          </a>
        )}
        <Link href={`/fit?jobId=${match.id}`} className="text-muted hover:text-foreground">
          Score against my resume
        </Link>
      </div>

      <ReachOutPanel jobId={match.id} resumeFile={resumeFile} />
    </article>
  );
}

