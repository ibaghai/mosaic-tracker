"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import {
  Activity,
  ArrowLeftRight,
  TrendingUp,
  Building2,
  Code2,
  Users,
  Briefcase,
  Wrench,
  Globe2,
  Sparkles,
  LineChart,
  Menu,
  X,
} from "lucide-react";
import { api } from "@/lib/api";

const NAV = [
  { href: "/", label: "Pulse", icon: Activity },
  { href: "/changes", label: "Changes", icon: ArrowLeftRight },
  { href: "/trends", label: "Trends", icon: TrendingUp },
  { href: "/companies", label: "Companies", icon: Building2 },
  { href: "/coverage", label: "Coverage", icon: Globe2 },
  { href: "/analyst", label: "Analyst", icon: LineChart },
  { href: "/fit", label: "Resume Fit", icon: Sparkles },
  { href: "/skills", label: "Skills", icon: Code2 },
  { href: "/roles", label: "Roles", icon: Users },
  { href: "/jobs", label: "Job Feed", icon: Briefcase },
];

export default function Sidebar() {
  const pathname = usePathname();
  const [companyCount, setCompanyCount] = useState<number | null>(null);
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    api.overview().then((d) => setCompanyCount(d.total_companies));
  }, []);

  const navLinks = (
    <>
      <nav className="flex-1 px-3 space-y-0.5">
        {NAV.map(({ href, label, icon: Icon }) => {
          const active = pathname === href;
          return (
            <Link
              key={href}
              href={href}
              onClick={() => setMobileOpen(false)}
              className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
                active
                  ? "bg-accent/15 text-accent-light font-medium"
                  : "text-muted hover:text-foreground hover:bg-white/5"
              }`}
            >
              <Icon size={18} />
              {label}
            </Link>
          );
        })}
      </nav>
      <div className="px-3 pb-2">
        <Link
          href="/health"
          onClick={() => setMobileOpen(false)}
          className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
            pathname === "/health"
              ? "bg-accent/15 text-accent-light font-medium"
              : "text-muted hover:text-foreground hover:bg-white/5"
          }`}
        >
          <Wrench size={18} />
          Health
        </Link>
      </div>
      <div className="px-5 py-4 text-xs text-muted border-t border-card-border">
        {companyCount !== null ? `${companyCount} startups tracked` : "Loading..."}
      </div>
    </>
  );

  return (
    <>
      {/* Mobile hamburger button — visible only on small screens */}
      <button
        onClick={() => setMobileOpen(true)}
        className="md:hidden fixed top-4 left-4 z-40 p-2 bg-card border border-card-border rounded-lg text-muted hover:text-foreground"
        aria-label="Open navigation"
      >
        <Menu size={18} />
      </button>

      {/* Mobile backdrop */}
      {mobileOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-30 md:hidden"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* Sidebar — hidden on mobile unless open, always visible on md+ */}
      <aside
        className={`${
          mobileOpen ? "flex" : "hidden"
        } md:flex fixed md:relative inset-y-0 left-0 z-40 w-56 shrink-0 border-r border-card-border bg-card flex-col`}
      >
        <div className="px-5 py-5 flex items-center justify-between">
          <div>
            <h1 className="text-lg font-bold tracking-tight text-accent-light">
              Mosaic
            </h1>
            <p className="text-xs text-muted mt-0.5">Startup Hiring Tracker</p>
          </div>
          {/* Close button — mobile only */}
          <button
            onClick={() => setMobileOpen(false)}
            className="md:hidden text-muted hover:text-foreground p-1"
            aria-label="Close navigation"
          >
            <X size={16} />
          </button>
        </div>
        {navLinks}
      </aside>
    </>
  );
}
