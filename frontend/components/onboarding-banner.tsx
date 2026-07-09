import type { OnboardingState } from "@/lib/types";

export function OnboardingBanner({ onboarding }: { onboarding: OnboardingState }) {
  if (onboarding.is_complete) return null;

  return (
    <div className="mb-6 px-4 py-3 rounded-lg text-sm flex flex-wrap items-center gap-x-2 gap-y-1 bg-card border border-border text-muted-foreground">
      <span>🚀 Pour démarrer :</span>
      <span>{onboarding.profile_complete ? "✓" : "✗"} Profil</span>
      <span>·</span>
      {onboarding.search_complete ? (
        <span>✓ Mots-clés de recherche</span>
      ) : (
        <a href="/settings#search" className="text-primary hover:underline">
          ✗ Mots-clés de recherche
        </a>
      )}
      <span>·</span>
      {onboarding.hf_token_complete ? (
        <span>✓ Token Hugging Face</span>
      ) : (
        <a href="/settings#hf-token" className="text-primary hover:underline">
          ✗ Token Hugging Face
        </a>
      )}
    </div>
  );
}
