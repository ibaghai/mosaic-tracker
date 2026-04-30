"use client";

import { usePathname } from "next/navigation";
import { AuthProvider, useAuth } from "@/components/AuthProvider";
import Sidebar from "@/components/Sidebar";

const HIDE_SIDEBAR_ON = new Set(["/login", "/signup"]);

// Surfaces that require login. Mirrors AuthProvider's AUTH_REQUIRED_PREFIXES —
// kept in sync so we don't render the page (and fire 401-bound API calls)
// while the redirect to /login is still pending.
const AUTH_REQUIRED_PREFIXES = ["/pipeline", "/saved"];

export default function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <AuthProvider>
      <Inner>{children}</Inner>
    </AuthProvider>
  );
}

function Inner({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { user, loading } = useAuth();
  const hideSidebar = HIDE_SIDEBAR_ON.has(pathname);

  // Initial /me check: render the empty shell until we know — keeps the
  // sidebar from flickering between anon/auth states.
  if (loading) {
    return (
      <main className="flex-1 flex items-center justify-center text-muted text-sm">
        Loading…
      </main>
    );
  }

  // On the auth pages (login/signup), no sidebar.
  if (hideSidebar) {
    return <main className="flex-1 overflow-y-auto p-4 pt-16 md:p-8">{children}</main>;
  }

  // Auth-required surfaces: hold the page render until we know we have a user.
  // AuthProvider's effect will be redirecting to /login in parallel — we just
  // render the sidebar + a placeholder so the page itself never mounts and
  // never fires its own (would-be 401) API calls.
  const needsAuth = AUTH_REQUIRED_PREFIXES.some((p) => pathname.startsWith(p));
  if (needsAuth && !user) {
    return (
      <>
        <Sidebar />
        <main className="flex-1 overflow-y-auto p-4 pt-16 md:p-8">
          <div className="text-muted text-sm">Redirecting to sign in…</div>
        </main>
      </>
    );
  }

  // Everywhere else: sidebar + page. Anonymous users see the same shell;
  // browsable surfaces work without auth (auth-only actions show "sign in" prompts).
  return (
    <>
      <Sidebar />
      <main className="flex-1 overflow-y-auto p-4 pt-16 md:p-8">{children}</main>
    </>
  );
}
