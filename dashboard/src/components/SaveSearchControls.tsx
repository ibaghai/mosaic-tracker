"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, SavedSearch } from "@/lib/api";
import { useAuth } from "@/components/AuthProvider";

/**
 * Two-piece control: a "Save current search" inline input and a
 * "Load saved" dropdown of this user's saved searches for this surface.
 *
 * The parent owns the actual filter state. We just hand it the params object
 * via `currentParams` and call `onLoad` with the JSON when the user picks a
 * saved search.
 */
export function SaveSearchControls<T extends Record<string, unknown>>({
  surface,
  currentParams,
  onLoad,
}: {
  surface: string;
  currentParams: T;
  onLoad: (params: T) => void;
}) {
  const { user } = useAuth();
  const [searches, setSearches] = useState<SavedSearch[]>([]);
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const refresh = () => {
    if (!user) {
      setSearches([]);
      return;
    }
    void api
      .savedSearchesList(surface)
      .then((d) => setSearches(d.searches))
      .catch(() => setSearches([]));
  };

  useEffect(refresh, [surface, user]);

  if (!user) {
    return (
      <div className="text-xs text-muted">
        <Link href="/login" className="text-accent-light hover:underline">Sign in</Link>
        {" "}to save and reload your favourite filter combinations.
      </div>
    );
  }

  const save = async () => {
    const trimmed = name.trim();
    if (!trimmed || busy) return;
    setBusy(true);
    setMsg(null);
    try {
      await api.savedSearchesCreate(surface, trimmed, currentParams);
      setName("");
      setMsg(`Saved "${trimmed}"`);
      refresh();
      setTimeout(() => setMsg(null), 2500);
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Save failed");
    } finally {
      setBusy(false);
    }
  };

  const load = (id: string) => {
    if (!id) return;
    const found = searches.find((s) => s.id === Number(id));
    if (!found) return;
    try {
      const params = JSON.parse(found.params_json) as T;
      onLoad(params);
      setMsg(`Loaded "${found.name}"`);
      setTimeout(() => setMsg(null), 2000);
    } catch {
      setMsg("Could not load saved search (corrupt JSON)");
    }
  };

  return (
    <div className="flex flex-wrap items-center gap-2 text-xs">
      <select
        defaultValue=""
        onChange={(e) => {
          load(e.target.value);
          // Reset so picking the same one twice still fires.
          e.target.value = "";
        }}
        disabled={searches.length === 0}
        className="bg-background border border-card-border rounded-lg px-2 py-1.5 text-sm text-foreground disabled:opacity-50"
        title={searches.length === 0 ? "No saved searches yet" : "Load a saved search"}
      >
        <option value="">
          {searches.length ? `Load saved (${searches.length})` : "No saved searches"}
        </option>
        {searches.map((s) => (
          <option key={s.id} value={s.id}>{s.name}</option>
        ))}
      </select>

      <input
        type="text"
        value={name}
        onChange={(e) => setName(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            void save();
          }
        }}
        placeholder="Name this search…"
        className="bg-background border border-card-border rounded-lg px-2 py-1.5 text-sm text-foreground w-48"
      />
      <button
        type="button"
        onClick={save}
        disabled={!name.trim() || busy}
        className="px-3 py-1.5 bg-accent text-white rounded-lg hover:bg-accent-light disabled:opacity-50 transition-colors"
      >
        {busy ? "…" : "Save search"}
      </button>

      <Link href="/saved" className="text-muted hover:text-foreground">
        Manage
      </Link>

      {msg && <span className="text-muted">{msg}</span>}
    </div>
  );
}
