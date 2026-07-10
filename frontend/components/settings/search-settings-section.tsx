"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { Portal, Settings } from "@/lib/types";
import { redirectOnUnauthenticated } from "@/lib/api-errors";

async function saveSearchSettings(settings: Settings): Promise<void> {
  const res = await fetch("/api/settings/search", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(settings),
  });
  redirectOnUnauthenticated(res);
  if (!res.ok) throw new Error("failed to save search settings");
}

export function SearchSettingsSection({
  settings,
  availablePortals,
}: {
  settings: Settings;
  availablePortals: Portal[];
}) {
  const [form, setForm] = useState(settings);
  const queryClient = useQueryClient();
  const mutation = useMutation({
    mutationFn: saveSearchSettings,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["settings"] }),
  });

  function updateField<K extends keyof Settings>(key: K, value: Settings[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  function updateLines(key: "keywords" | "target_companies", text: string) {
    updateField(
      key,
      text
        .split("\n")
        .map((l) => l.trim())
        .filter(Boolean),
    );
  }

  function togglePortal(portalId: string) {
    setForm((f) => ({
      ...f,
      enabled_portals: f.enabled_portals.includes(portalId)
        ? f.enabled_portals.filter((p) => p !== portalId)
        : [...f.enabled_portals, portalId],
    }));
  }

  return (
    <div id="search" className="rounded-xl p-6 bg-card border border-border">
      <h2 className="text-lg font-semibold mb-4">Recherche</h2>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          mutation.mutate(form);
        }}
        className="space-y-4"
      >
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm text-muted-foreground mb-1">
              Keywords (un par ligne)
            </label>
            <textarea
              rows={4}
              value={form.keywords.join("\n")}
              onChange={(e) => updateLines("keywords", e.target.value)}
              className="w-full text-sm rounded px-3 py-2 bg-background border border-border text-foreground font-mono"
            />
          </div>
          <div>
            <label className="block text-sm text-muted-foreground mb-1">Portails actifs</label>
            <p className="text-xs text-muted-foreground mb-1">
              Aucune sélection = tous les portails actifs.
            </p>
            <div className="rounded px-3 py-2 bg-background border border-border space-y-1.5">
              {availablePortals.map((portal) => (
                <label
                  key={portal.id}
                  className="flex items-start gap-2 text-sm cursor-pointer select-none"
                >
                  <input
                    type="checkbox"
                    checked={form.enabled_portals.includes(portal.id)}
                    onChange={() => togglePortal(portal.id)}
                    className="cursor-pointer mt-0.5"
                  />
                  <span className="flex flex-col">
                    <span>{portal.name}</span>
                    {portal.status === "needs_auth" && (
                      <span className="text-xs text-muted-foreground">
                        nécessite une inscription
                      </span>
                    )}
                  </span>
                </label>
              ))}
            </div>
          </div>
        </div>
        <div className="grid grid-cols-3 gap-4">
          <div>
            <label className="block text-sm text-muted-foreground mb-1">Localisation</label>
            <input
              value={form.location}
              onChange={(e) => updateField("location", e.target.value)}
              className="w-full text-sm rounded px-3 py-2 bg-background border border-border text-foreground"
            />
          </div>
          <div>
            <label className="block text-sm text-muted-foreground mb-1">Contrat</label>
            <input
              value={form.contract}
              onChange={(e) => updateField("contract", e.target.value)}
              className="w-full text-sm rounded px-3 py-2 bg-background border border-border text-foreground"
            />
          </div>
          <div>
            <label className="block text-sm text-muted-foreground mb-1">
              Exp. max (ans)
            </label>
            <input
              type="number"
              value={form.experience_max_years}
              onChange={(e) => updateField("experience_max_years", Number(e.target.value))}
              className="w-full text-sm rounded px-3 py-2 bg-background border border-border text-foreground"
            />
          </div>
        </div>
        <div className="grid grid-cols-3 gap-4">
          <div>
            <label className="block text-sm text-muted-foreground mb-1">
              Salaire min (€)
            </label>
            <input
              type="number"
              value={form.salary_min}
              onChange={(e) => updateField("salary_min", Number(e.target.value))}
              className="w-full text-sm rounded px-3 py-2 bg-background border border-border text-foreground"
            />
          </div>
          <div>
            <label className="block text-sm text-muted-foreground mb-1">
              Salaire max (€)
            </label>
            <input
              type="number"
              value={form.salary_max}
              onChange={(e) => updateField("salary_max", Number(e.target.value))}
              className="w-full text-sm rounded px-3 py-2 bg-background border border-border text-foreground"
            />
          </div>
          <div>
            <label className="block text-sm text-muted-foreground mb-1">
              Relance après (jours)
            </label>
            <input
              type="number"
              value={form.follow_up_days}
              onChange={(e) => updateField("follow_up_days", Number(e.target.value))}
              className="w-full text-sm rounded px-3 py-2 bg-background border border-border text-foreground"
            />
          </div>
        </div>
        <div>
          <label className="block text-sm text-muted-foreground mb-1">
            Entreprises cibles (une par ligne)
          </label>
          <textarea
            rows={3}
            value={form.target_companies.join("\n")}
            onChange={(e) => updateLines("target_companies", e.target.value)}
            className="w-full text-sm rounded px-3 py-2 bg-background border border-border text-foreground font-mono"
          />
        </div>
        <div className="flex items-center gap-3">
          <button
            type="submit"
            className="text-sm px-4 py-2 rounded-lg font-medium bg-primary text-primary-foreground hover:opacity-90"
          >
            Enregistrer
          </button>
          {mutation.isSuccess && <span className="text-sm text-primary">✓ Enregistré</span>}
        </div>
      </form>
    </div>
  );
}
