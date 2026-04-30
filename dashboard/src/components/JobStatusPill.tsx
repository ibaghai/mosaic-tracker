"use client";

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { api, JobStatus } from "@/lib/api";
import { useAuth } from "@/components/AuthProvider";

const STATUS_OPTIONS: { value: JobStatus; label: string }[] = [
  { value: "saved", label: "Save" },
  { value: "applied", label: "Applied" },
  { value: "interviewing", label: "Interviewing" },
  { value: "rejected", label: "Rejected" },
  { value: "offered", label: "Offered" },
  { value: "dismissed", label: "Dismiss" },
];

const STATUS_LABELS: Record<JobStatus, string> = {
  saved: "★ Saved",
  applied: "Applied",
  interviewing: "Interviewing",
  rejected: "Rejected",
  offered: "Offered",
  dismissed: "Dismissed",
};

const STATUS_TONE: Record<JobStatus, string> = {
  saved: "bg-yellow-400/10 text-yellow-300 border-yellow-400/30",
  applied: "bg-accent/10 text-accent-light border-accent/30",
  interviewing: "bg-accent/20 text-accent-light border-accent/40",
  rejected: "bg-red/10 text-red border-red/30",
  offered: "bg-green/10 text-green border-green/30",
  dismissed: "bg-card text-muted border-card-border line-through",
};

/**
 * Compact inline status control for a job. Shows current status as a colored
 * pill; click to open a small menu of next-state actions.
 *
 * Optimistic local state — the parent doesn't need to refetch.
 */
export function JobStatusPill({
  jobId,
  initialStatus,
  onChange,
}: {
  jobId: number;
  initialStatus?: JobStatus | null;
  onChange?: (next: JobStatus | null) => void;
}) {
  const { user, requireLogin } = useAuth();
  // All hooks declared up front so the call order is stable across renders
  // (react-hooks/rules-of-hooks). Anonymous-state branch is a render-time
  // conditional below, NOT an early return that skips hook calls.
  const [status, setStatus] = useState<JobStatus | null>(initialStatus ?? null);
  const [open, setOpen] = useState(false);
  const [pending, setPending] = useState(false);
  const triggerRef = useRef<HTMLButtonElement | null>(null);

  const apply = async (next: JobStatus | null) => {
    if (pending) return;
    setPending(true);
    setOpen(false);
    const previous = status;
    setStatus(next); // optimistic
    try {
      if (next === null) {
        await api.jobClearStatus(jobId);
      } else {
        await api.jobSetStatus(jobId, next);
      }
      onChange?.(next);
    } catch {
      setStatus(previous); // rollback
    } finally {
      setPending(false);
    }
  };

  // Anonymous: render a tiny "Sign in to track" link — preserves layout, no
  // dropdown menu, click bumps to login.
  if (!user) {
    return (
      <button
        type="button"
        onClick={() => requireLogin()}
        className="text-[10px] uppercase tracking-wide text-muted hover:text-accent-light"
        title="Sign in to track jobs"
      >
        Sign in to track
      </button>
    );
  }

  if (status) {
    return (
      <>
        <button
          ref={triggerRef}
          type="button"
          onClick={() => setOpen(!open)}
          className={`text-[10px] uppercase tracking-wide px-2 py-0.5 rounded-full border ${STATUS_TONE[status]}`}
        >
          {STATUS_LABELS[status]}
        </button>
        {open && (
          <PortalMenu
            anchor={triggerRef}
            onApply={apply}
            current={status}
            onClose={() => setOpen(false)}
          />
        )}
      </>
    );
  }

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        onClick={() => setOpen(!open)}
        className="text-[10px] uppercase tracking-wide text-muted hover:text-foreground"
      >
        + Track
      </button>
      {open && (
        <PortalMenu
          anchor={triggerRef}
          onApply={apply}
          current={null}
          onClose={() => setOpen(false)}
        />
      )}
    </>
  );
}

/**
 * The status menu, rendered into document.body via a portal so no
 * `overflow: hidden` ancestor (table wrappers, kanban cards) can clip it.
 * Position is computed from the trigger's bounding rect once on open and
 * updated on scroll/resize.
 */
function PortalMenu({
  anchor,
  onApply,
  current,
  onClose,
}: {
  anchor: React.RefObject<HTMLButtonElement | null>;
  onApply: (next: JobStatus | null) => void;
  current: JobStatus | null;
  onClose: () => void;
}) {
  const [pos, setPos] = useState<{ top: number; left: number } | null>(null);
  const MENU_W = 160;

  useLayoutEffect(() => {
    const update = () => {
      const el = anchor.current;
      if (!el) return;
      const r = el.getBoundingClientRect();
      // Place below + right-aligned to the trigger; keep on screen.
      const left = Math.max(8, Math.min(window.innerWidth - MENU_W - 8, r.right - MENU_W));
      const top = r.bottom + 4;
      setPos({ top, left });
    };
    update();
    window.addEventListener("resize", update);
    window.addEventListener("scroll", update, true);
    return () => {
      window.removeEventListener("resize", update);
      window.removeEventListener("scroll", update, true);
    };
  }, [anchor]);

  // Close on Escape
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  if (typeof document === "undefined" || !pos) return null;
  return createPortal(
    <>
      <div
        className="fixed inset-0"
        style={{ zIndex: 100 }}
        onClick={onClose}
      />
      <div
        className="fixed bg-card border border-card-border rounded-lg shadow-lg py-1 text-xs"
        style={{ top: pos.top, left: pos.left, width: MENU_W, zIndex: 101 }}
      >
        {STATUS_OPTIONS.map((opt) => (
          <button
            key={opt.value}
            type="button"
            onClick={() => onApply(opt.value)}
            className={`w-full text-left px-3 py-1.5 hover:bg-background ${
              current === opt.value ? "text-accent-light" : "text-foreground"
            }`}
          >
            {opt.label}
          </button>
        ))}
        {current && (
          <>
            <div className="my-1 border-t border-card-border/50" />
            <button
              type="button"
              onClick={() => onApply(null)}
              className="w-full text-left px-3 py-1.5 hover:bg-background text-muted"
            >
              Remove tracking
            </button>
          </>
        )}
      </div>
    </>,
    document.body,
  );
}
