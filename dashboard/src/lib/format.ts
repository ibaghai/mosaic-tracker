export const SENIORITY_LABELS: Record<string, string> = {
  "c-level":   "C-Level",
  "vp":        "VP",
  "head":      "Head",
  "director":  "Director",
  "principal": "Principal",
  "staff":     "Staff",
  "senior":    "Senior",
  "lead":      "Lead",
  "manager":   "Manager",
  "mid":       "Mid-Level",
  "junior":    "Junior",
  "intern":    "Intern",
};

export const WORK_MODEL_LABELS: Record<string, string> = {
  "remote": "Remote",
  "hybrid": "Hybrid",
  "onsite": "On-site",
};

export const ROLE_FAMILY_LABELS: Record<string, string> = {
  "software_engineering": "Software Engineering",
  "ml_ai": "ML / AI",
  "data": "Data",
  "product": "Product",
  "design": "Design",
  "sales": "Sales",
  "marketing": "Marketing",
  "customer_success": "Customer Success",
  "people": "People",
  "finance": "Finance",
  "legal": "Legal",
  "security": "Security",
  "operations": "Operations",
  "other": "Other",
};

export function formatSeniority(s: string | null | undefined): string {
  if (!s) return "—";
  return SENIORITY_LABELS[s] ?? s;
}

export function formatWorkModel(s: string | null | undefined): string {
  if (!s) return "—";
  return WORK_MODEL_LABELS[s] ?? s;
}

export function formatRoleFamily(s: string | null | undefined): string {
  if (!s) return "—";
  return ROLE_FAMILY_LABELS[s] ?? s;
}

export function formatDate(s: string | null | undefined): string {
  if (!s) return "—";
  return new Date(s).toLocaleDateString();
}

export function formatMoney(m: number | null | undefined): string {
  if (m == null) return "—";
  return `$${m}M`;
}

export const FUNDING_ORDER = [
  "Pre-Seed", "Seed", "Series A", "Series B", "Series C",
  "Series D", "Series E", "Series F", "Growth", "Public",
];

export function fundingBadgeColor(round: string | null): string {
  if (!round) return "bg-card-border text-muted";
  const idx = FUNDING_ORDER.indexOf(round);
  if (idx <= 1) return "bg-blue-500/10 text-blue-400";
  if (idx <= 3) return "bg-green/10 text-green";
  if (idx <= 5) return "bg-accent/10 text-accent-light";
  return "bg-purple-500/10 text-purple-400";
}
