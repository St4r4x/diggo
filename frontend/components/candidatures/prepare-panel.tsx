"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { Offer, PrepareStatusResponse } from "@/lib/types";
import { redirectOnUnauthenticated } from "@/lib/api-errors";

const APPLY_STATUSES = ["À envoyer", "Envoyée", "Relance"];
const INTERVIEW_STATUSES = ["Entretien RH", "Entretien tech", "Offre"];

async function fetchPrepareStatus(
  offerId: number,
): Promise<PrepareStatusResponse> {
  const res = await fetch(`/api/offers/${offerId}/prepare/status`);
  redirectOnUnauthenticated(res);
  if (!res.ok) throw new Error("failed to fetch prepare status");
  return res.json();
}

async function startPrepare(
  offerId: number,
  skipPrep: boolean,
): Promise<{ status: string }> {
  const res = await fetch(`/api/offers/${offerId}/prepare`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ skip_prep: skipPrep }),
  });
  redirectOnUnauthenticated(res);
  if (res.status === 422) {
    const body = await res.json();
    throw new Error(
      body.detail?.message ?? "Impossible de préparer la candidature",
    );
  }
  if (!res.ok) throw new Error("failed to start prepare");
  return res.json();
}

function copyInterviewCmd(offerId: number) {
  const cmd = `claude --system-prompt "$(cat modes/prepare-entretien.md)" "Prépare l'entretien pour l'offre ID ${offerId}"`;
  navigator.clipboard.writeText(cmd);
}

export function PreparePanel({ offer }: { offer: Offer }) {
  const queryClient = useQueryClient();
  const [skipPrep, setSkipPrep] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);
  const isApplyPhase = APPLY_STATUSES.includes(offer.status);
  const isInterviewPhase = INTERVIEW_STATUSES.includes(offer.status);

  const { data } = useQuery({
    queryKey: ["prepare-status", offer.id],
    queryFn: () => fetchPrepareStatus(offer.id),
    enabled: isApplyPhase,
    refetchInterval: (query) =>
      query.state.data?.status === "running" ? 2000 : false,
  });

  const startMutation = useMutation({
    mutationFn: () => startPrepare(offer.id, skipPrep),
    onSuccess: () => {
      setStartError(null);
      queryClient.invalidateQueries({
        queryKey: ["prepare-status", offer.id],
      });
    },
    onError: (err: Error) => setStartError(err.message),
  });

  const status = data?.status ?? "idle";
  const stage = data?.stage ?? "";
  const error = data?.error ?? "";

  useEffect(() => {
    if (status === "done") {
      queryClient.invalidateQueries({ queryKey: ["offer", offer.id] });
    }
  }, [status, offer.id, queryClient]);

  if (isInterviewPhase) {
    return (
      <button
        onClick={() => copyInterviewCmd(offer.id)}
        className="text-sm px-4 py-2 rounded-lg font-medium text-left text-primary-foreground bg-primary hover:opacity-90"
      >
        ✦ Préparer entretien
      </button>
    );
  }

  if (!isApplyPhase) return null;

  if (status === "running") {
    return (
      <button
        disabled
        className="w-full text-sm px-4 py-2 rounded-lg flex items-center gap-2 text-left cursor-not-allowed opacity-60 bg-background border border-border text-muted-foreground"
      >
        <span className="inline-block w-3 h-3 border-2 border-primary border-t-transparent rounded-full animate-spin" />
        {stage || "Préparation en cours…"}
      </button>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      {status === "error" && <p className="text-xs text-red-400">{error}</p>}
      {startError && <p className="text-xs text-red-400">{startError}</p>}
      <label className="flex items-center gap-2 text-sm cursor-pointer select-none text-primary">
        <input
          type="checkbox"
          checked={skipPrep}
          onChange={(e) => setSkipPrep(e.target.checked)}
          className="cursor-pointer"
        />
        Sans fiche de préparation d&apos;entretien
      </label>
      <button
        onClick={() => startMutation.mutate()}
        className="text-sm px-4 py-2 rounded-lg font-medium text-left text-primary-foreground bg-primary hover:opacity-90"
      >
        {status === "error"
          ? "✦ Réessayer"
          : "✦ Préparer candidature (IA)"}
      </button>
    </div>
  );
}
