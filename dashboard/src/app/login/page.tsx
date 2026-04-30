"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import { useAuth } from "@/components/AuthProvider";

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <Inner />
    </Suspense>
  );
}

function Inner() {
  const router = useRouter();
  const params = useSearchParams();
  const { refresh } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setErr(null);
    try {
      await api.authLogin(email, password);
      await refresh();
      const dest = params.get("from") || "/";
      router.replace(dest);
    } catch (exc) {
      setErr(exc instanceof Error ? exc.message : "Login failed.");
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
          <h1 className="text-xl font-semibold">Sign in</h1>
          <p className="text-xs text-muted mt-1">
            New here? <Link href="/signup" className="text-accent-light hover:underline">Create an account</Link>.
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
          <span className="text-xs text-muted">Password</span>
          <input
            type="password"
            required
            autoComplete="current-password"
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
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </div>
  );
}
