"use client";

import { useEffect, useState } from "react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import { api, SkillRow } from "@/lib/api";

const TOOLTIP_STYLE = {
  contentStyle: { background: "#1a1d27", border: "1px solid #2a2d3a", borderRadius: 8 },
  labelStyle: { color: "#e5e7eb" },
  itemStyle: { color: "#e5e7eb" },
};

type View = "all" | "compare";

export default function SkillsPage() {
  const [startupSkills, setStartupSkills] = useState<SkillRow[]>([]);
  const [bigcoSkills, setBigcoSkills] = useState<SkillRow[]>([]);
  const [allSkills, setAllSkills] = useState<SkillRow[]>([]);
  const [view, setView] = useState<View>("all");

  useEffect(() => {
    api.skills(undefined, 30).then(setAllSkills);
    api.skills("startup", 25).then(setStartupSkills);
    api.skills("bigco", 25).then(setBigcoSkills);
  }, []);

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">Skills</h2>
          <p className="text-muted text-sm mt-1">
            Most in-demand skills extracted from job descriptions
          </p>
        </div>
        <div className="flex gap-1 bg-card border border-card-border rounded-lg p-1">
          <button
            onClick={() => setView("all")}
            className={`px-3 py-1 text-xs rounded transition-colors ${
              view === "all" ? "bg-accent text-white" : "text-muted hover:text-foreground"
            }`}
          >
            All Companies
          </button>
          <button
            onClick={() => setView("compare")}
            className={`px-3 py-1 text-xs rounded transition-colors ${
              view === "compare" ? "bg-accent text-white" : "text-muted hover:text-foreground"
            }`}
          >
            Startups vs. Big Tech
          </button>
        </div>
      </div>

      {view === "all" ? (
        <div className="bg-card border border-card-border rounded-xl p-5">
          <h3 className="text-sm font-semibold text-muted mb-4">Top 30 Skills — All Companies</h3>
          <ResponsiveContainer width="100%" height={700}>
            <BarChart data={allSkills} layout="vertical" margin={{ left: 10 }}>
              <XAxis type="number" tick={{ fill: "#9ca3af", fontSize: 12 }} />
              <YAxis type="category" dataKey="skill" width={120} tick={{ fill: "#9ca3af", fontSize: 12 }} />
              <Tooltip {...TOOLTIP_STYLE} />
              <Bar dataKey="count" fill="#6366f1" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-6">
          <div className="bg-card border border-card-border rounded-xl p-5">
            <div className="flex items-center gap-2 mb-4">
              <h3 className="text-sm font-semibold text-muted">Top 25 Skills</h3>
              <span className="text-xs px-2 py-0.5 rounded bg-accent/10 text-accent-light border border-accent/20">Startups</span>
            </div>
            <ResponsiveContainer width="100%" height={600}>
              <BarChart data={startupSkills} layout="vertical" margin={{ left: 10 }}>
                <XAxis type="number" tick={{ fill: "#9ca3af", fontSize: 12 }} />
                <YAxis type="category" dataKey="skill" width={120} tick={{ fill: "#9ca3af", fontSize: 12 }} />
                <Tooltip {...TOOLTIP_STYLE} />
                <Bar dataKey="count" fill="#6366f1" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="bg-card border border-card-border rounded-xl p-5">
            <div className="flex items-center gap-2 mb-4">
              <h3 className="text-sm font-semibold text-muted">Top 25 Skills</h3>
              <span className="text-xs px-2 py-0.5 rounded bg-purple-500/10 text-purple-400 border border-purple-500/20">Big Tech</span>
            </div>
            <ResponsiveContainer width="100%" height={600}>
              <BarChart data={bigcoSkills} layout="vertical" margin={{ left: 10 }}>
                <XAxis type="number" tick={{ fill: "#9ca3af", fontSize: 12 }} />
                <YAxis type="category" dataKey="skill" width={120} tick={{ fill: "#9ca3af", fontSize: 12 }} />
                <Tooltip {...TOOLTIP_STYLE} />
                <Bar dataKey="count" fill="#8b5cf6" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </div>
  );
}
