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
} from "lucide-react";
import { api } from "@/lib/api";

const NAV = [
  { href: "/", label: "Pulse", icon: Activity },
  { href: "/changes", label: "Changes", icon: ArrowLeftRight },
  { href: "/trends", label: "Trends", icon: TrendingUp },
  { href: "/companies", label: "Companies", icon: Building2 },
  { href: "/coverage", label: "Coverage", icon: Globe2 },
  { href: "/skills", label: "Skills", icon: Code2 },
  { href: "/roles", label: "Roles", icon: Users },
  { href: "/jobs", label: "Job Feed", icon: Briefcase },
];

export default function Sidebar() {
  const pathname = usePathname();
  const [companyCount, setCompanyCount] = useState<number | null>(null);

  useEffect(() => {
    api.overview().then((d) => setCompanyCount(d.total_companies));
  }, []);

  return (
    <aside className="w-56 shrink-0 border-r border-card-border bg-card flex flex-col">
      <div className="px-5 py-5">
        <h1 className="text-lg font-bold tracking-tight text-accent-light">
          Mosaic
        </h1>
        <p className="text-xs text-muted mt-0.5">Startup Hiring Tracker</p>
      </div>
      <nav className="flex-1 px-3 space-y-0.5">
        {NAV.map(({ href, label, icon: Icon }) => {
          const active = pathname === href;
          return (
            <Link
              key={href}
              href={href}
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
    </aside>
  );
}
