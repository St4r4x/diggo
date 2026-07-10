"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { redirectOnUnauthenticated } from "@/lib/api-errors";

async function saveHfToken(token: string): Promise<{ hf_token_set: boolean }> {
  const res = await fetch("/api/settings/hf-token", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ hf_token: token }),
  });
  redirectOnUnauthenticated(res);
  if (res.status === 422) {
    const body = await res.json();
    throw new Error(body.detail?.message ?? "Token invalide");
  }
  if (!res.ok) throw new Error("failed to save token");
  return res.json();
}

async function deleteHfToken(): Promise<{ hf_token_set: boolean }> {
  const res = await fetch("/api/settings/hf-token", { method: "DELETE" });
  redirectOnUnauthenticated(res);
  if (!res.ok) throw new Error("failed to delete token");
  return res.json();
}

export function HfTokenSection({ hfTokenSet }: { hfTokenSet: boolean }) {
  const [token, setToken] = useState("");
  const queryClient = useQueryClient();

  const saveMutation = useMutation({
    mutationFn: saveHfToken,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["settings"] });
      setToken("");
    },
  });
  const deleteMutation = useMutation({
    mutationFn: deleteHfToken,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["settings"] }),
  });

  return (
    <div id="hf-token" className="rounded-xl p-6 bg-card border border-border">
      <h2 className="text-lg font-semibold mb-4">Clé API Hugging Face</h2>
      {hfTokenSet ? (
        <p className="text-sm text-primary mb-3">Configuré ✓</p>
      ) : (
        <p className="text-sm text-muted-foreground mb-3">
          Non configuré. Sans token, la préparation de candidature (CV, lettre, fiche
          entretien) est bloquée.
        </p>
      )}
      {saveMutation.isError && (
        <p className="text-sm text-destructive mb-3">{saveMutation.error.message}</p>
      )}
      <ol className="text-muted-foreground text-xs mb-3 leading-relaxed list-decimal list-inside space-y-1">
        <li>
          Ouvre{" "}
          <a
            href="https://huggingface.co/settings/tokens"
            target="_blank"
            rel="noopener noreferrer"
            className="text-primary hover:underline"
          >
            huggingface.co/settings/tokens
          </a>
        </li>
        <li>
          Clique sur <strong>&quot;New token&quot;</strong>
        </li>
        <li>
          Active la permission <strong>&quot;Inference Providers&quot;</strong> (obligatoire,
          sans elle le token sera refusé)
        </li>
        <li>
          Copie le token (commence par <code className="font-mono">hf_</code>) et colle-le
          ci-dessous
        </li>
      </ol>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          saveMutation.mutate(token);
        }}
        className="flex gap-2"
      >
        <input
          type="password"
          value={token}
          onChange={(e) => setToken(e.target.value)}
          placeholder="hf_..."
          autoComplete="off"
          pattern="hf_.{15,}"
          title="Le token doit commencer par hf_ et faire au moins 18 caractères"
          className="flex-1 text-sm rounded px-3 py-2 bg-background border border-border text-foreground font-mono"
        />
        <button
          type="submit"
          className="text-sm px-4 py-2 rounded-lg font-medium bg-primary text-primary-foreground hover:opacity-90"
        >
          Enregistrer
        </button>
        {hfTokenSet && (
          <button
            type="button"
            onClick={() => {
              if (confirm("Supprimer le token Hugging Face ?")) deleteMutation.mutate();
            }}
            className="text-sm px-4 py-2 rounded-lg font-medium bg-destructive text-white hover:opacity-90"
          >
            Supprimer
          </button>
        )}
      </form>
    </div>
  );
}
