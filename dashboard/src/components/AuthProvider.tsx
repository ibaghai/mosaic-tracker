"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { api } from "@/lib/api";

type User = { id: number; email: string };

type AuthState = {
  user: User | null;
  loading: boolean;
  signupsAllowed: boolean;
  refresh: () => Promise<void>;
  logout: () => Promise<void>;
  /** Push the user to /login with a redirect-back. Use when an action needs auth. */
  requireLogin: (returnTo?: string) => void;
};

const Ctx = createContext<AuthState | null>(null);

// Surfaces that require login to be useful (they show only the current user's
// data). Browsable surfaces (jobs, companies, fit, jd-match, outreach, etc.)
// work anonymously — auth is only needed for write actions on them.
//
// Note: /outreach is intentionally NOT here. Guests can land on it and see an
// empty-state explaining what would be tracked once they sign in.
const AUTH_REQUIRED_PREFIXES = ["/pipeline", "/saved"];
const PUBLIC_AUTH_ROUTES = new Set(["/login", "/signup"]);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [signupsAllowed, setSignupsAllowed] = useState(true);

  const refresh = async () => {
    try {
      const me = await api.authMe();
      setUser(me.user);
      setSignupsAllowed(me.signups_allowed);
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void refresh();
  }, []);

  // Bounce only when:
  //   - the user is unauth AND on a surface that needs auth (e.g. /pipeline)
  //   - the user IS auth and on /login or /signup (avoid the empty form)
  useEffect(() => {
    if (loading) return;
    const needsAuth = AUTH_REQUIRED_PREFIXES.some((p) => pathname.startsWith(p));
    if (!user && needsAuth) {
      router.replace(`/login?from=${encodeURIComponent(pathname)}`);
    } else if (user && PUBLIC_AUTH_ROUTES.has(pathname)) {
      router.replace("/");
    }
  }, [loading, user, pathname, router]);

  const logout = async () => {
    try {
      await api.authLogout();
    } catch {
      // ignore
    }
    setUser(null);
    // Only kick out of an auth-required page; let anonymous browsers stay put.
    if (AUTH_REQUIRED_PREFIXES.some((p) => pathname.startsWith(p))) {
      router.replace("/");
    }
  };

  const requireLogin = useCallback(
    (returnTo?: string) => {
      const dest = returnTo ?? pathname ?? "/";
      router.push(`/login?from=${encodeURIComponent(dest)}`);
    },
    [pathname, router],
  );

  return (
    <Ctx.Provider value={{ user, loading, signupsAllowed, refresh, logout, requireLogin }}>
      {children}
    </Ctx.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
