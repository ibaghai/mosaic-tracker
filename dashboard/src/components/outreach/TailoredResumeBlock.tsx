"use client";

import { useState } from "react";
import { TailoredResume } from "@/lib/api";

export function TailoredResumeBlock({
  tailored,
  jobTitle,
}: {
  tailored: TailoredResume;
  jobTitle: string;
}) {
  const [expanded, setExpanded] = useState(false);

  if (tailored._error) {
    return <p className="text-xs text-red">Tailored resume: {tailored._error}</p>;
  }
  if (!tailored.tailored_text) return null;

  const download = () => {
    const blob = new Blob([tailored.tailored_text || ""], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `resume-tailored-${jobTitle.replace(/[^a-z0-9]+/gi, "-").toLowerCase()}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const keywords = tailored.diff_summary?.keywords_added || [];
  const rephrased = tailored.diff_summary?.bullets_rephrased || [];

  return (
    <div className="bg-background border border-card-border rounded-lg p-3">
      <div className="flex items-center justify-between">
        <p className="text-xs uppercase tracking-wide text-muted">Tailored resume</p>
        <div className="flex gap-3 text-xs">
          <button type="button" onClick={() => setExpanded(!expanded)} className="text-accent-light hover:underline">
            {expanded ? "Collapse" : "Expand"}
          </button>
          <button type="button" onClick={download} className="text-accent-light hover:underline">
            Download .txt
          </button>
        </div>
      </div>

      {keywords.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {keywords.map((kw) => (
            <span key={kw} className="px-1.5 py-0.5 rounded bg-green/10 text-green text-[10px]">
              +{kw}
            </span>
          ))}
        </div>
      )}

      {expanded && (
        <>
          {rephrased.length > 0 && (
            <details className="mt-3 text-xs">
              <summary className="cursor-pointer text-muted">{rephrased.length} bullet(s) rephrased</summary>
              <ul className="mt-2 space-y-2">
                {rephrased.map((r, i) => (
                  <li key={i}>
                    <span className="text-muted line-through">{r.before}</span><br />
                    <span className="text-foreground">{r.after}</span>
                  </li>
                ))}
              </ul>
            </details>
          )}
          <pre className="mt-3 whitespace-pre-wrap font-sans text-xs text-foreground border-t border-card-border pt-3 max-h-96 overflow-auto">
            {tailored.tailored_text}
          </pre>
        </>
      )}
    </div>
  );
}
