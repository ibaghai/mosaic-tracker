"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { useAuth } from "@/components/AuthProvider";

export default function SignupPage() {
  const router = useRouter();
  const { refresh, signupsAllowed, loading } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!loading && !signupsAllowed) {
      router.replace("/login");
    }
  }, [loading, signupsAllowed, router]);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setErr(null);
    try {
      await api.authSignup(email, password);
      await refresh();
      router.replace("/");
    } catch (exc) {
      setErr(exc instanceof Error ? exc.message : "Signup failed.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-[60vh] flex items-center justify-center">
      <form
        onSubmit={onSubmit}
        className="w-full max-w-sm bg-card border border-card-border rounded-xl p-6 space-y-4"
      >
        <div>
          <h1 className="text-xl font-semibold">Create account</h1>
          <p className="text-xs text-muted mt-1">
            Already have one?{" "}
            <Link href="/login" className="text-accent-light hover:underline">Sign in</Link>.
          </p>
        </div>

        <label className="block">
          <span className="text-xs text-muted">Email</span>
          <input
            type="email"
            required
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="mt-1 w-full bg-background border border-card-border rounded-lg px-3 py-2 text-sm text-foreground"
          />
        </label>

        <label className="block">
          <span className="text-xs text-muted">Password (min 8 chars)</span>
          <input
            type="password"
            required
            minLength={8}
            autoComplete="new-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mt-1 w-full bg-background border border-card-border rounded-lg px-3 py-2 text-sm text-foreground"
          />
        </label>

        {err && (
          <p className="text-xs text-red border border-red/40 bg-red/10 rounded-lg p-2">{err}</p>
        )}

        <button
          type="submit"
          disabled={busy}
          className="w-full px-4 py-2 bg-accent text-white text-sm rounded-lg hover:bg-accent-light disabled:opacity-50 transition-colors"
        >
          {busy ? "Creating…" : "Create account"}
        </button>
      </form>
    </div>
  );
}
