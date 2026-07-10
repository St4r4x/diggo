"use client";

import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { LlmProvider, LlmProviderName, SettingsResponse } from "@/lib/types";
import { ALL_LLM_PROVIDERS, llmProviderLabel } from "@/lib/llm-providers";
import { redirectOnUnauthenticated } from "@/lib/api-errors";

async function saveProvider(
  provider: LlmProviderName,
  apiKey: string,
): Promise<{ llm_providers: LlmProvider[] }> {
  const res = await fetch(`/api/settings/llm-providers/${provider}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ api_key: apiKey }),
  });
  redirectOnUnauthenticated(res);
  if (res.status === 422) {
    const body = await res.json();
    throw new Error(body.detail?.message ?? "Clé invalide");
  }
  if (!res.ok) throw new Error("failed to save provider key");
  return res.json();
}

async function deleteProvider(
  provider: LlmProviderName,
): Promise<{ llm_providers: LlmProvider[] }> {
  const res = await fetch(`/api/settings/llm-providers/${provider}`, {
    method: "DELETE",
  });
  redirectOnUnauthenticated(res);
  if (!res.ok) throw new Error("failed to delete provider");
  return res.json();
}

async function reorderProviders(
  order: LlmProviderName[],
): Promise<{ llm_providers: LlmProvider[] }> {
  const res = await fetch("/api/settings/llm-providers/reorder", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ order }),
  });
  redirectOnUnauthenticated(res);
  if (!res.ok) throw new Error("failed to reorder providers");
  return res.json();
}

function ProviderRow({
  provider,
  configured,
  canMoveUp,
  canMoveDown,
  onMoveUp,
  onMoveDown,
  onSave,
  onDelete,
  errorMessage,
  savedNonce,
}: {
  provider: LlmProviderName;
  configured: boolean;
  canMoveUp: boolean;
  canMoveDown: boolean;
  onMoveUp: () => void;
  onMoveDown: () => void;
  onSave: (apiKey: string) => void;
  onDelete: () => void;
  errorMessage?: string;
  savedNonce: number;
}) {
  const [apiKey, setApiKey] = useState("");

  // Clear the input only once the save mutation for this row actually succeeds
  // (savedNonce is bumped by the parent's onSuccess), not optimistically on submit.
  useEffect(() => {
    setApiKey("");
  }, [savedNonce]);

  return (
    <div
      className={`rounded-lg p-3 border border-border flex flex-col gap-2 ${
        configured ? "bg-card" : "bg-background opacity-70"
      }`}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {configured && (
            <div className="flex flex-col">
              <button
                type="button"
                disabled={!canMoveUp}
                onClick={onMoveUp}
                className="text-xs px-1 text-muted-foreground disabled:opacity-30"
              >
                ▲
              </button>
              <button
                type="button"
                disabled={!canMoveDown}
                onClick={onMoveDown}
                className="text-xs px-1 text-muted-foreground disabled:opacity-30"
              >
                ▼
              </button>
            </div>
          )}
          <span className="text-sm font-medium">{llmProviderLabel(provider)}</span>
          {configured && <span className="text-xs text-primary">Configuré ✓</span>}
        </div>
      </div>
      {errorMessage && <p className="text-xs text-destructive">{errorMessage}</p>}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          onSave(apiKey);
        }}
        className="flex gap-2"
      >
        <input
          type="password"
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
          placeholder="Clé API…"
          autoComplete="off"
          className="flex-1 text-sm rounded px-3 py-2 bg-background border border-border text-foreground font-mono"
        />
        <button
          type="submit"
          className="text-sm px-4 py-2 rounded-lg font-medium bg-primary text-primary-foreground hover:opacity-90"
        >
          Enregistrer
        </button>
        {configured && (
          <button
            type="button"
            onClick={() => {
              if (confirm(`Supprimer la clé ${llmProviderLabel(provider)} ?`)) onDelete();
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

export function LlmProvidersSection({
  llmProviders,
}: {
  llmProviders: LlmProvider[];
}) {
  const queryClient = useQueryClient();
  const [rowError, setRowError] = useState<Record<string, string>>({});
  const [savedNonce, setSavedNonce] = useState<Record<string, number>>({});
  const [reorderError, setReorderError] = useState("");

  const saveMutation = useMutation({
    mutationFn: ({ provider, apiKey }: { provider: LlmProviderName; apiKey: string }) =>
      saveProvider(provider, apiKey),
    onSuccess: (data, { provider }) => {
      setRowError((prev) => ({ ...prev, [provider]: "" }));
      setSavedNonce((prev) => ({ ...prev, [provider]: (prev[provider] ?? 0) + 1 }));
      queryClient.setQueryData<SettingsResponse>(["settings"], (old) =>
        old ? { ...old, llm_providers: data.llm_providers } : old,
      );
    },
    onError: (err: Error, { provider }) => {
      setRowError((prev) => ({ ...prev, [provider]: err.message }));
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (provider: LlmProviderName) => deleteProvider(provider),
    onSuccess: (data, provider) => {
      setRowError((prev) => ({ ...prev, [provider]: "" }));
      queryClient.setQueryData<SettingsResponse>(["settings"], (old) =>
        old ? { ...old, llm_providers: data.llm_providers } : old,
      );
    },
    onError: (err: Error, provider) => {
      setRowError((prev) => ({ ...prev, [provider]: err.message }));
    },
  });

  const reorderMutation = useMutation({
    mutationFn: (order: LlmProviderName[]) => reorderProviders(order),
    onSuccess: (data) => {
      setReorderError("");
      queryClient.setQueryData<SettingsResponse>(["settings"], (old) =>
        old ? { ...old, llm_providers: data.llm_providers } : old,
      );
    },
    onError: (err: Error) => {
      setReorderError(err.message);
    },
  });

  const configuredOrder = [...llmProviders]
    .sort((a, b) => a.sort_order - b.sort_order)
    .map((p) => p.provider);
  const configuredSet = new Set(configuredOrder);
  const unconfigured = ALL_LLM_PROVIDERS.filter((p) => !configuredSet.has(p));

  function move(provider: LlmProviderName, direction: -1 | 1) {
    const index = configuredOrder.indexOf(provider);
    const target = index + direction;
    if (target < 0 || target >= configuredOrder.length) return;
    const next = [...configuredOrder];
    [next[index], next[target]] = [next[target], next[index]];
    reorderMutation.mutate(next);
  }

  return (
    <div id="llm-providers" className="rounded-xl p-6 bg-card border border-border">
      <h2 className="text-lg font-semibold mb-2">Fournisseurs LLM</h2>
      <p className="text-sm text-muted-foreground mb-4">
        Configure un ou plusieurs fournisseurs. La préparation de candidature (CV,
        lettre, fiche entretien) essaie chacun dans l&apos;ordre ci-dessous et bascule
        automatiquement sur le suivant en cas d&apos;échec.
      </p>
      {reorderError && <p className="text-xs text-destructive mb-2">{reorderError}</p>}
      <div className="flex flex-col gap-2">
        {configuredOrder.map((provider, i) => (
          <ProviderRow
            key={provider}
            provider={provider}
            configured
            canMoveUp={i > 0}
            canMoveDown={i < configuredOrder.length - 1}
            onMoveUp={() => move(provider, -1)}
            onMoveDown={() => move(provider, 1)}
            onSave={(apiKey) => saveMutation.mutate({ provider, apiKey })}
            onDelete={() => deleteMutation.mutate(provider)}
            errorMessage={rowError[provider]}
            savedNonce={savedNonce[provider] ?? 0}
          />
        ))}
        {unconfigured.map((provider) => (
          <ProviderRow
            key={provider}
            provider={provider}
            configured={false}
            canMoveUp={false}
            canMoveDown={false}
            onMoveUp={() => {}}
            onMoveDown={() => {}}
            onSave={(apiKey) => saveMutation.mutate({ provider, apiKey })}
            onDelete={() => {}}
            errorMessage={rowError[provider]}
            savedNonce={savedNonce[provider] ?? 0}
          />
        ))}
      </div>
    </div>
  );
}
