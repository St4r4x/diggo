"use client";

import { useEffect } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { ScanStatusResponse } from "@/lib/types";

async function fetchScanStatus(): Promise<ScanStatusResponse> {
  const res = await fetch("/api/scan/status");
  if (res.status === 401) {
    window.location.href = "/login";
    throw new Error("session expired");
  }
  if (!res.ok) throw new Error("failed to fetch scan status");
  return res.json();
}

async function startScan(): Promise<ScanStatusResponse> {
  const res = await fetch("/api/scan/start", { method: "POST" });
  if (res.status === 401) {
    window.location.href = "/login";
    throw new Error("session expired");
  }
  if (!res.ok) throw new Error("failed to start scan");
  return res.json();
}

export function ScanButton() {
  const queryClient = useQueryClient();

  const { data } = useQuery({
    queryKey: ["scan-status"],
    queryFn: fetchScanStatus,
    refetchInterval: (query) =>
      query.state.data?.status === "running" ? 2000 : false,
  });

  const startMutation = useMutation({
    mutationFn: startScan,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["scan-status"] });
    },
  });

  const status = data?.status ?? "idle";
  const result = data?.result;

  // Once a scan finishes, refresh the offers list so newly-imported
  // rows show up without a manual page reload.
  useEffect(() => {
    if (status === "done") {
      queryClient.invalidateQueries({ queryKey: ["offers"] });
    }
  }, [status, queryClient]);

  if (status === "running") {
    return (
      <button
        disabled
        className="w-full text-sm px-3 py-2 rounded-lg flex items-center justify-center gap-2 cursor-not-allowed opacity-60 bg-background border border-border text-muted-foreground"
      >
        <span className="inline-block w-3 h-3 border-2 border-primary border-t-transparent rounded-full animate-spin" />
        {result && result.found > 0
          ? `Scan… ${result.found} trouvées${result.scored > 0 ? `, ${result.scored} scorées` : ""}`
          : "Scan en cours…"}
      </button>
    );
  }

  if (status === "error") {
    return (
      <button
        onClick={() => startMutation.mutate()}
        className="w-full text-sm px-3 py-2 rounded-lg font-medium bg-red-900 text-red-200 hover:bg-red-800"
      >
        ✗ Erreur — Réessayer
      </button>
    );
  }

  if (status === "done" && result) {
    return (
      <button
        onClick={() => startMutation.mutate()}
        className="w-full text-sm px-3 py-2 rounded-lg font-medium text-primary-foreground bg-primary hover:opacity-90"
      >
        ✓ {result.inserted} nouvelle{result.inserted !== 1 ? "s" : ""}
        {result.abandoned > 0
          ? `, ${result.abandoned} expirée${result.abandoned !== 1 ? "s" : ""}`
          : ""}{" "}
        — Scanner
      </button>
    );
  }

  return (
    <button
      onClick={() => startMutation.mutate()}
      className="w-full text-sm px-3 py-2 rounded-lg font-medium text-primary-foreground bg-primary hover:opacity-90"
    >
      ⟳ Scanner
    </button>
  );
}
