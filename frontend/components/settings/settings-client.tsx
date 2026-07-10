"use client";

import { useQuery } from "@tanstack/react-query";
import type { SettingsResponse } from "@/lib/types";
import { redirectOnUnauthenticated } from "@/lib/api-errors";
import { OnboardingBanner } from "@/components/onboarding-banner";
import { SearchSettingsSection } from "@/components/settings/search-settings-section";
import { AtsTargetsSection } from "@/components/settings/ats-targets-section";
import { HfTokenSection } from "@/components/settings/hf-token-section";

async function fetchSettings(): Promise<SettingsResponse> {
  const res = await fetch("/api/settings");
  redirectOnUnauthenticated(res);
  if (!res.ok) throw new Error("failed to fetch settings");
  return res.json();
}

export function SettingsClient() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["settings"],
    queryFn: fetchSettings,
  });

  if (isLoading) {
    return <div className="p-8 text-sm text-muted-foreground">Chargement…</div>;
  }
  if (isError || !data) {
    return (
      <div className="p-8 text-sm text-destructive">
        Erreur de chargement des paramètres.
      </div>
    );
  }

  return (
    <div className="overflow-y-auto h-full">
      <div className="max-w-3xl mx-auto py-8 px-4 space-y-8">
        <OnboardingBanner onboarding={data.onboarding} />
        <h1 className="text-2xl font-bold">Paramètres</h1>
        <SearchSettingsSection settings={data.settings} availablePortals={data.available_portals} />
        <HfTokenSection hfTokenSet={data.hf_token_set} />
        <AtsTargetsSection atsTargets={data.ats_targets} />
      </div>
    </div>
  );
}
