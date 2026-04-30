"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import {
  api,
  FitJobResponse,
  FitMatchesResponse,
  JobRow,
} from "@/lib/api";
import { formatRoleFamily, formatSeniority, formatWorkModel } from "@/lib/format";
import { FitCard } from "@/components/fit/FitCard";

type CompanyTypeFilter = "" | "startup" | "bigco";

export default function FitPage() {
  return (
    <Suspense fallback={<div className="text-muted text-sm">Loading...</div>}>
      <FitInner />
    </Suspense>
  );
}

function FitInner() {
  const params = useSearchParams();
  const router = useRouter();
  const selectedJobId = params.get("jobId") || "";
  const [file, setFile] = useState<File | null>(null);
  const [limit, setLimit] = useState(10);
  const [companyType, setCompanyType] = useState<CompanyTypeFilter>("");
  const [jobId, setJobId] = useState(selectedJobId);
  const [selectedJob, setSelectedJob] = useState<JobRow | null>(null);
  const [jobLoading, setJobLoading] = useState(false);
  const [jobError, setJobError] = useState<string | null>(null);
  const [result, setResult] = useState<FitMatchesResponse | FitJobResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const matches = useMemo(() => {
    if (!result) return [];
    if ("matches" in result) return result.matches;
    return [result.match];
  }, [result]);

  useEffect(() => {
    setJobId(selectedJobId);
    setSelectedJob(null);
    setJobError(null);
    setJobLoading(false);
    if (!selectedJobId) return;

    const numericJobId = Number(selectedJobId);
    if (!Number.isInteger(numericJobId) || numericJobId <= 0) {
      setJobError("Selected job was not found.");
      return;
    }

    let cancelled = false;
    setJobLoading(true);
    void api.jobDetail(numericJobId)
      .then((job) => {
        if (!cancelled) setSelectedJob(job);
      })
      .catch(() => {
        if (!cancelled) setJobError("Selected job was not found.");
      })
      .finally(() => {
        if (!cancelled) setJobLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [selectedJobId]);

  const clearSelectedJob = () => {
    setJobId("");
    setSelectedJob(null);
    setJobError(null);
    router.push("/fit");
  };

  const loadAdvancedJob = () => {
    const trimmedJobId = jobId.trim();
    if (!trimmedJobId) {
      clearSelectedJob();
      return;
    }
    router.push(`/fit?jobId=${encodeURIComponent(trimmedJobId)}`);
  };

  const handleSubmit = async () => {
    if (!file) {
      setError("Choose a resume file first.");
      return;
    }
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const trimmedJobId = jobId.trim();
      if (trimmedJobId) {
        const numericJobId = Number(trimmedJobId);
        if (!Number.isInteger(numericJobId) || numericJobId <= 0) {
          setError("Enter a valid job ID.");
          return;
        }
        const data = await api.fitJob(numericJobId, file);
        setResult(data);
      } else {
        const data = await api.fitMatches(file, {
          company_type: companyType || undefined,
          limit,
        });
        setResult(data);
      }
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Fit analysis failed.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold">Resume Fit</h2>
        <p className="text-muted text-sm mt-1">
          Prioritize roles with LLM reasoning. Location is context only and does not affect score.
        </p>
      </div>

      <div className="bg-card border border-card-border rounded-xl p-4 space-y-4">
        {(jobLoading || jobError || selectedJob) && (
          <SelectedJobCard
            job={selectedJob}
            loading={jobLoading}
            error={jobError}
            onClear={clearSelectedJob}
          />
        )}

        <div className={jobId.trim() ? "grid gap-3 md:grid-cols-[1fr_auto] md:items-end" : "grid gap-3 md:grid-cols-[1fr_150px_170px_auto] md:items-end"}>
          <label className="block">
            <span className="text-xs text-muted">Resume</span>
            <input
              type="file"
              accept=".txt,.md,.pdf,.docx"
              onChange={(event) => setFile(event.target.files?.[0] || null)}
              className="mt-1 block w-full text-sm text-muted file:mr-3 file:rounded-lg file:border file:border-card-border file:bg-background file:px-3 file:py-2 file:text-foreground"
            />
          </label>
          {!jobId.trim() && (
            <>
              <label className="block">
                <span className="text-xs text-muted">Matches</span>
                <input
                  type="number"
                  min={1}
                  max={40}
                  value={limit}
                  onChange={(event) => setLimit(Number(event.target.value))}
                  className="mt-1 w-full bg-background border border-card-border rounded-lg px-3 py-2 text-sm text-foreground"
                />
              </label>
              <label className="block">
                <span className="text-xs text-muted">Company set</span>
                <select
                  value={companyType}
                  onChange={(event) => setCompanyType(event.target.value as CompanyTypeFilter)}
                  className="mt-1 w-full bg-background border border-card-border rounded-lg px-3 py-2 text-sm text-foreground"
                >
                  <option value="">Both</option>
                  <option value="startup">Startups</option>
                  <option value="bigco">Big companies</option>
                </select>
              </label>
            </>
          )}
          <button
            onClick={handleSubmit}
            disabled={loading}
            className="px-4 py-2 bg-accent text-white text-sm rounded-lg hover:bg-accent-light disabled:opacity-50 transition-colors"
          >
            {loading ? "Analyzing..." : jobId.trim() ? "Compare Resume To This Job" : "Find Fits"}
          </button>
        </div>

        <details className="text-xs text-muted">
          <summary className="cursor-pointer hover:text-foreground">Advanced: paste job ID</summary>
          <div className="mt-3 flex flex-col gap-2 sm:flex-row">
            <input
              type="text"
              value={jobId}
              onChange={(event) => setJobId(event.target.value)}
              placeholder="Optional"
              className="bg-background border border-card-border rounded-lg px-3 py-2 text-sm text-foreground sm:w-48"
            />
            <button
              onClick={loadAdvancedJob}
              className="px-3 py-2 text-xs bg-background border border-card-border rounded-lg text-muted hover:text-foreground"
            >
              Load job
            </button>
          </div>
        </details>

        <p className="text-xs text-muted">
          Raw resume text is parsed into a de-identified compact profile for matching and is not stored.
        </p>
        {error && (
          <div className="border border-red/40 bg-red/10 rounded-lg p-3 text-sm text-red">
            {error}
          </div>
        )}
      </div>

      {result && (
        <div className="grid gap-4 lg:grid-cols-[320px_1fr]">
          <aside className="bg-card border border-card-border rounded-xl p-4 h-fit">
            <p className="text-xs text-muted">Parsed profile</p>
            <h3 className="font-semibold mt-1">{result.profile.headline || "Resume profile"}</h3>
            <div className="mt-4 space-y-3 text-sm">
              <ProfileRow label="Roles" value={result.profile.target_roles.join(", ") || "Unknown"} />
              <ProfileRow label="Seniority" value={formatSeniority(result.profile.seniority)} />
              <ProfileRow label="Families" value={result.profile.role_families.map(formatRoleFamily).join(", ") || "Unknown"} />
              <ProfileRow label="Remote" value={result.profile.remote_preference || "unknown"} />
            </div>
            <div className="mt-4">
              <p className="text-xs text-muted mb-2">Skills</p>
              <div className="flex flex-wrap gap-1.5">
                {result.profile.skills.slice(0, 24).map((skill) => (
                  <span key={skill} className="px-2 py-1 rounded-full bg-background border border-card-border text-xs text-muted">
                    {skill}
                  </span>
                ))}
              </div>
            </div>
            <p className="mt-4 text-xs text-muted">
              {result.provider} · {result.model} · {"matches" in result ? `${result.shortlist_count} shortlisted` : "single job"}
            </p>
          </aside>

          <section className="space-y-4">
            {matches.map((match) => (
              <FitCard key={match.job.id} match={match} resumeFile={file} />
            ))}
          </section>
        </div>
      )}
    </div>
  );
}

function SelectedJobCard({
  job,
  loading,
  error,
  onClear,
}: {
  job: JobRow | null;
  loading: boolean;
  error: string | null;
  onClear: () => void;
}) {
  if (loading) {
    return (
      <div className="bg-background border border-card-border rounded-lg p-4 text-sm text-muted">
        Loading selected job...
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-background border border-red/40 rounded-lg p-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm text-red">{error}</p>
        <button onClick={onClear} className="text-xs text-muted hover:text-foreground">
          Clear selected job
        </button>
      </div>
    );
  }

  if (!job) return null;

  return (
    <div className="bg-background border border-card-border rounded-lg p-4">
      <p className="text-xs text-muted">Comparing against</p>
      <div className="mt-2 flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
        <div>
          <h3 className="font-semibold">{job.title}</h3>
          <p className="text-sm text-muted mt-1">
            <Link href={`/companies/${job.company_id}`} className="hover:text-accent-light">{job.company_name}</Link>
            {job.sector ? ` · ${job.sector}` : ""}
          </p>
          <p className="text-xs text-muted mt-2">
            {formatRoleFamily(job.role_family)} · {formatSeniority(job.seniority)} · {formatWorkModel(job.work_model)}
            {job.location ? ` · ${job.location}` : ""}
          </p>
        </div>
        <div className="flex gap-3 text-xs md:justify-end">
          {job.url && (
            <a href={job.url} target="_blank" rel="noopener noreferrer" className="text-accent-light hover:underline">
              Apply
            </a>
          )}
          <button onClick={onClear} className="text-muted hover:text-foreground">
            Clear selected job
          </button>
        </div>
      </div>
    </div>
  );
}

function ProfileRow({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs text-muted">{label}</p>
      <p className="text-foreground">{value}</p>
    </div>
  );
}

