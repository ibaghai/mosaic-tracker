"use client";

import { useState } from "react";
import { api, JobStatus, OutreachDraft, OutreachStatus } from "@/lib/api";
import { useAuth } from "@/components/AuthProvider";

export function DraftCard({
  draft: initial,
  onUpdate,
}: {
  draft: OutreachDraft;
  /** Optional: parent refresh hook, fired after any status mutation succeeds.
   *  Used by /outreach to re-fetch the status-tab counts. */
  onUpdate?: () => void;
}) {
  const { user, requireLogin } = useAuth();
  const [draft, setDraft] = useState<OutreachDraft>(initial);
  const [copied, setCopied] = useState(false);
  const [editing, setEditing] = useState(false);
  const [editedBody, setEditedBody] = useState<string | null>(null);

  if (draft._error) {
    return <p className="text-xs text-red">[{draft.archetype}] {draft._error}</p>;
  }

  const archetypeLabel = (draft.archetype || "").replace("_", " ");
  const body = editedBody ?? draft.message ?? "";
  const subject = draft.subject ?? "";
  const email = draft.person_email ?? "";
  const status: OutreachStatus = (draft.status as OutreachStatus) || "draft";

  const composedForCopy = `${subject ? `Subject: ${subject}\n\n` : ""}${body}`;

  const copy = async () => {
    if (!body) return;
    try {
      await navigator.clipboard.writeText(composedForCopy);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // ignore
    }
  };

  const mailtoHref = email
    ? `mailto:${encodeURIComponent(email)}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`
    : null;

  const gmailHref = email
    ? `https://mail.google.com/mail/?view=cm&fs=1&to=${encodeURIComponent(email)}&su=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`
    : null;

  // Track which channel was last clicked, to pre-fill `sent_via` when the
  // user clicks "Mark sent". Defaults to whichever launcher they used last.
  const [launchedVia, setLaunchedVia] = useState<"gmail" | "mail" | "linkedin" | null>(null);
  const [marking, setMarking] = useState(false);

  // True = the draft exists in the DB. False = ephemeral, generated this
  // session and only persisted if the user clicks Save / Mark sent.
  const isPersisted = draft.id != null;

  const persistEphemeral = async (
    initialStatus: "draft" | "sent",
    via?: "gmail" | "mail" | "linkedin" | "manual",
  ): Promise<OutreachDraft | null> => {
    // Required by the API: person_id, job_id, message.
    if (!draft.person_id || !draft.job_id || !draft.message) return null;
    return api.outreachCreateDraft({
      person_id: draft.person_id,
      job_id: draft.job_id,
      message: editedBody ?? draft.message,
      subject: draft.subject,
      archetype: draft.archetype ?? undefined,
      tone: draft.tone,
      rationale: draft.rationale,
      provider: draft.provider,
      model: draft.model,
      prompt_version: draft.prompt_version,
      user_edits: editedBody ?? undefined,
      status: initialStatus,
      sent_via: initialStatus === "sent" ? (via ?? launchedVia ?? "manual") : undefined,
    });
  };

  const markSent = async (via?: "gmail" | "mail" | "linkedin" | "manual") => {
    if (marking) return;
    setMarking(true);
    try {
      let updated: OutreachDraft | null = null;
      if (isPersisted) {
        updated = await api.outreachMarkSent(draft.id!, {
          sent_via: via ?? launchedVia ?? "manual",
          user_edits: editedBody ?? undefined,
        });
      } else {
        // Create + send in one round-trip.
        updated = await persistEphemeral("sent", via);
      }
      if (updated) {
        setDraft((d) => ({ ...d, ...updated, status: updated.status ?? "sent" }));
        onUpdate?.();
      }
    } finally {
      setMarking(false);
    }
  };

  const saveAsDraft = async () => {
    if (isPersisted || marking) return;
    setMarking(true);
    try {
      const updated = await persistEphemeral("draft");
      if (updated) {
        setDraft((d) => ({ ...d, ...updated, status: updated.status ?? "draft" }));
        onUpdate?.();
      }
    } finally {
      setMarking(false);
    }
  };

  // After a positive/interview reply, suggest bumping the linked job's
  // pipeline status. State holds the suggested next status (or null).
  const [pipelineNudge, setPipelineNudge] = useState<JobStatus | null>(null);
  const [nudgeBusy, setNudgeBusy] = useState(false);

  const suggestNudge = (category: "positive" | "neutral" | "negative" | "interview") => {
    // We can't read the current job status from here without an extra request,
    // so we suggest the obvious next step:
    //   interview → "interviewing"
    //   positive  → "applied"   (or interviewing if it's already applied — user confirms)
    if (category === "interview") return "interviewing" as JobStatus;
    if (category === "positive") return "applied" as JobStatus;
    return null;
  };

  const setReplied = (category: "positive" | "neutral" | "negative" | "interview") => {
    if (!draft.id) return;
    void api
      .outreachLogReply(draft.id, { reply_category: category })
      .then((updated) => {
        setDraft((d) => ({ ...d, ...updated }));
        // If a nudge is suggested, hold off on the parent refresh — refreshing
        // would unmount this card (status changed from sent → replied) and
        // wipe the nudge before the user could act on it. The parent will be
        // refreshed inside acceptNudge / dismissNudge.
        const next = draft.job_id ? suggestNudge(category) : null;
        if (next) {
          setPipelineNudge(next);
        } else {
          onUpdate?.();
        }
      });
  };

  const acceptNudge = async () => {
    if (!draft.job_id || !pipelineNudge || nudgeBusy) return;
    setNudgeBusy(true);
    try {
      await api.jobSetStatus(draft.job_id, pipelineNudge);
      setPipelineNudge(null);
      onUpdate?.();
    } finally {
      setNudgeBusy(false);
    }
  };

  const dismissNudge = () => {
    setPipelineNudge(null);
    onUpdate?.();
  };

  const setStatus = (s: OutreachStatus) => {
    if (!draft.id) return;
    void api.outreachSetStatus(draft.id, s).then((updated) => {
      setDraft((d) => ({ ...d, ...updated }));
      onUpdate?.();
    });
  };

  const statusBadge =
    status === "sent" ? (
      <span className="text-[10px] uppercase tracking-wide text-accent-light">
        ✓ sent {draft.sent_via ? `via ${draft.sent_via}` : ""}
      </span>
    ) : status === "replied" ? (
      <span className="text-[10px] uppercase tracking-wide text-green">
        ✓ replied {draft.reply_category ? `(${draft.reply_category})` : ""}
      </span>
    ) : status === "no_reply" ? (
      <span className="text-[10px] uppercase tracking-wide text-muted">no reply</span>
    ) : status === "bounced" ? (
      <span className="text-[10px] uppercase tracking-wide text-red">bounced</span>
    ) : null;

  return (
    <div className="bg-background border border-card-border rounded-lg p-3">
      <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
        <span className="text-[10px] uppercase tracking-wide text-accent-light">{archetypeLabel}</span>
        <span className="font-medium">{draft.person_name || "—"}</span>
        <span className="text-xs text-muted">{draft.person_title}</span>
        {statusBadge && <span className="ml-auto">{statusBadge}</span>}
      </div>

      <div className="mt-1 flex flex-wrap gap-3 text-xs">
        {draft.person_linkedin_url && (
          <a href={draft.person_linkedin_url} target="_blank" rel="noopener noreferrer" className="text-accent-light hover:underline">
            LinkedIn
          </a>
        )}
        {email && <span className="text-muted">{email}</span>}
      </div>

      {subject && <p className="mt-2 text-sm font-medium">Subject: {subject}</p>}

      {editing ? (
        <textarea
          value={body}
          onChange={(e) => setEditedBody(e.target.value)}
          className="mt-2 w-full min-h-[140px] p-2 bg-card border border-card-border rounded text-sm font-sans text-foreground"
        />
      ) : (
        <pre className="mt-2 whitespace-pre-wrap font-sans text-sm text-foreground">{body}</pre>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-2">
        {email ? (
          <>
            <a
              href={gmailHref!}
              target="_blank"
              rel="noopener noreferrer"
              onClick={() => setLaunchedVia("gmail")}
              className="px-3 py-1.5 bg-background border border-card-border text-foreground text-xs rounded hover:border-accent-light transition-colors"
            >
              Open in Gmail
            </a>
            <a
              href={mailtoHref!}
              onClick={() => setLaunchedVia("mail")}
              className="px-3 py-1.5 bg-background border border-card-border text-foreground text-xs rounded hover:border-accent-light transition-colors"
            >
              Open in mail
            </a>
          </>
        ) : draft.person_linkedin_url ? (
          <a
            href={draft.person_linkedin_url}
            target="_blank"
            rel="noopener noreferrer"
            onClick={() => setLaunchedVia("linkedin")}
            className="px-3 py-1.5 bg-background border border-card-border text-foreground text-xs rounded hover:border-accent-light transition-colors"
          >
            Open LinkedIn
          </a>
        ) : (
          <span className="text-xs text-muted">No email or LinkedIn on file</span>
        )}

        {status === "draft" && user && (
          <>
            <button
              type="button"
              onClick={() => markSent()}
              disabled={marking}
              className="px-3 py-1.5 bg-accent text-white text-xs rounded hover:bg-accent-light transition-colors disabled:opacity-50"
              title={
                launchedVia
                  ? `Mark as sent via ${launchedVia}`
                  : "Click after you actually send the message — adds it to /outreach as 'sent' for follow-up tracking"
              }
            >
              {marking ? "…" : launchedVia ? `✓ Mark sent (${launchedVia})` : "Mark sent"}
            </button>
            {!isPersisted && (
              <button
                type="button"
                onClick={saveAsDraft}
                disabled={marking}
                className="px-3 py-1.5 bg-background border border-card-border text-foreground text-xs rounded hover:border-accent-light transition-colors disabled:opacity-50"
                title="Persist this draft to /outreach without sending it"
              >
                {marking ? "…" : "Save as draft"}
              </button>
            )}
          </>
        )}
        {status === "draft" && !user && (
          <button
            type="button"
            onClick={() => requireLogin()}
            className="px-3 py-1.5 bg-accent/20 text-accent-light text-xs rounded hover:bg-accent/30 transition-colors"
            title="Sign in to save and track this outreach"
          >
            Sign in to save / track
          </button>
        )}

        <button
          type="button"
          onClick={() => setEditing(!editing)}
          className="text-xs text-muted hover:text-foreground"
        >
          {editing ? "Done editing" : "Edit"}
        </button>

        <button
          type="button"
          onClick={copy}
          className="text-xs text-muted hover:text-foreground"
        >
          {copied ? "Copied ✓" : "Copy"}
        </button>

        {draft.rationale?.person_artifacts_referenced?.length ? (
          <span className="ml-auto text-[10px] text-muted">
            Cites: {draft.rationale.person_artifacts_referenced.slice(0, 2).join(", ")}
          </span>
        ) : null}
      </div>

      {/* Cross-feature nudge: after a positive/interview reply, suggest bumping
          the linked job's pipeline status. Dismissible. */}
      {pipelineNudge && draft.job_id && (
        <div className="mt-2 pt-2 border-t border-card-border/60 flex flex-wrap items-center gap-2 text-[11px] bg-green/10 -mx-3 -mb-3 px-3 py-2 rounded-b-lg">
          <span className="text-green">↗</span>
          <span className="text-foreground">
            Bump this job to <strong className="text-accent-light">{pipelineNudge}</strong> in your pipeline?
          </span>
          <button
            onClick={acceptNudge}
            disabled={nudgeBusy}
            className="ml-1 px-2 py-0.5 bg-accent text-white rounded text-[10px] hover:bg-accent-light disabled:opacity-50"
          >
            {nudgeBusy ? "…" : "Yes"}
          </button>
          <button
            onClick={dismissNudge}
            className="text-muted hover:text-foreground"
          >
            Skip
          </button>
        </div>
      )}

      {/* Reply / status row — only meaningful once the draft is sent */}
      {status === "sent" && (
        <div className="mt-2 pt-2 border-t border-card-border/60 flex flex-wrap items-center gap-2 text-[11px]">
          <span className="text-muted">Got a reply?</span>
          <button onClick={() => setReplied("positive")} className="text-accent-light hover:underline">positive</button>
          <button onClick={() => setReplied("neutral")} className="text-accent-light hover:underline">neutral</button>
          <button onClick={() => setReplied("negative")} className="text-accent-light hover:underline">negative</button>
          <button onClick={() => setReplied("interview")} className="text-accent-light hover:underline">interview</button>
          <span className="text-muted ml-3">·</span>
          <button onClick={() => setStatus("no_reply")} className="text-muted hover:text-foreground">no reply</button>
          <button onClick={() => setStatus("bounced")} className="text-muted hover:text-foreground">bounced</button>
          <button onClick={() => setStatus("draft")} className="text-muted hover:text-foreground">undo send</button>
        </div>
      )}
    </div>
  );
}
