"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { AtsTarget, SettingsResponse } from "@/lib/types";
import { redirectOnUnauthenticated } from "@/lib/api-errors";

async function addAtsTarget(target: {
  name: string;
  careers_url: string;
}): Promise<{ ats_targets: AtsTarget[] }> {
  const res = await fetch("/api/settings/ats", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(target),
  });
  redirectOnUnauthenticated(res);
  if (!res.ok) throw new Error("failed to add ATS target");
  return res.json();
}

async function deleteAtsTarget(id: number): Promise<{ ats_targets: AtsTarget[] }> {
  const res = await fetch(`/api/settings/ats/${id}`, { method: "DELETE" });
  redirectOnUnauthenticated(res);
  if (!res.ok) throw new Error("failed to delete ATS target");
  return res.json();
}

export function AtsTargetsSection({ atsTargets }: { atsTargets: AtsTarget[] }) {
  const [name, setName] = useState("");
  const [careersUrl, setCareersUrl] = useState("");
  const queryClient = useQueryClient();

  const addMutation = useMutation({
    mutationFn: addAtsTarget,
    onSuccess: (data) => {
      queryClient.setQueryData<SettingsResponse>(["settings"], (old) =>
        old ? { ...old, ats_targets: data.ats_targets } : old,
      );
      setName("");
      setCareersUrl("");
    },
  });
  const deleteMutation = useMutation({
    mutationFn: deleteAtsTarget,
    onSuccess: (data) => {
      queryClient.setQueryData<SettingsResponse>(["settings"], (old) =>
        old ? { ...old, ats_targets: data.ats_targets } : old,
      );
    },
  });

  return (
    <div className="rounded-xl p-6 bg-card border border-border">
      <h2 className="text-lg font-semibold mb-4">ATS Targets</h2>
      {(addMutation.isError || deleteMutation.isError) && (
        <p className="text-sm text-destructive mb-3">
          {(addMutation.error ?? deleteMutation.error)?.message}
        </p>
      )}
      {atsTargets.length === 0 ? (
        <p className="text-sm text-muted-foreground">Aucune cible ATS configurée.</p>
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="text-muted-foreground text-left">
              <th className="pb-2 pr-4">Entreprise</th>
              <th className="pb-2 pr-4">URL Careers</th>
              <th className="pb-2"></th>
            </tr>
          </thead>
          <tbody>
            {atsTargets.map((t) => (
              <tr key={t.id} className="border-t border-border">
                <td className="py-2 pr-4">{t.name}</td>
                <td className="py-2 pr-4 text-muted-foreground font-mono text-xs">
                  {t.careers_url}
                </td>
                <td className="py-2">
                  <button
                    type="button"
                    onClick={() => {
                      if (confirm(`Supprimer ${t.name} ?`)) deleteMutation.mutate(t.id);
                    }}
                    className="text-destructive hover:opacity-80 text-xs"
                  >
                    Supprimer
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (name.trim() && careersUrl.trim()) {
            addMutation.mutate({ name, careers_url: careersUrl });
          }
        }}
        className="flex gap-2 mt-4"
      >
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Nom de l'entreprise"
          required
          className="flex-1 text-sm rounded px-3 py-2 bg-background border border-border text-foreground"
        />
        <input
          value={careersUrl}
          onChange={(e) => setCareersUrl(e.target.value)}
          placeholder="https://jobs.lever.co/..."
          required
          className="flex-1 text-sm rounded px-3 py-2 bg-background border border-border text-foreground"
        />
        <button
          type="submit"
          className="text-sm px-4 py-2 rounded-lg font-medium bg-primary text-primary-foreground hover:opacity-90"
        >
          Ajouter
        </button>
      </form>
    </div>
  );
}
