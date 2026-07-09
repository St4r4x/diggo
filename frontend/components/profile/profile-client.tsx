"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import type { Cv, ProfileResponse } from "@/lib/types";
import { redirectOnUnauthenticated } from "@/lib/api-errors";
import { OnboardingBanner } from "@/components/onboarding-banner";

async function fetchProfile(): Promise<ProfileResponse> {
  const res = await fetch("/api/profile");
  redirectOnUnauthenticated(res);
  if (!res.ok) throw new Error("failed to fetch profile");
  return res.json();
}

function groupSkillsByCategory(skills: Cv["skills"]) {
  const byCategory = new Map<string, string[]>();
  for (const s of skills) {
    const list = byCategory.get(s.category) ?? [];
    list.push(s.skill);
    byCategory.set(s.category, list);
  }
  return Array.from(byCategory.entries());
}

function CvSection({ cv }: { cv: Cv }) {
  const skillGroups = groupSkillsByCategory(cv.skills);
  return (
    <div className="space-y-6">
      {cv.meta.summary && (
        <div>
          <p className="text-sm font-semibold mb-1">Résumé</p>
          <p className="text-sm text-muted-foreground whitespace-pre-wrap">
            {cv.meta.summary}
          </p>
        </div>
      )}

      <div>
        <p className="text-sm font-semibold mb-2">Expériences</p>
        {cv.experience.length === 0 && (
          <p className="text-sm text-muted-foreground">Aucune expérience.</p>
        )}
        <div className="space-y-3">
          {cv.experience.map((exp) => (
            <div key={exp.id} className="rounded-lg p-3 bg-background border border-border">
              <p className="text-sm font-medium">
                {exp.title} — {exp.company}
              </p>
              <p className="text-xs text-muted-foreground mb-2">
                {exp.type} · {exp.period}
              </p>
              <ul className="list-disc pl-4 space-y-0.5">
                {exp.bullets.map((b, i) => (
                  <li key={i} className="text-sm text-muted-foreground">
                    {b}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </div>

      <div>
        <p className="text-sm font-semibold mb-2">Compétences</p>
        {skillGroups.length === 0 && (
          <p className="text-sm text-muted-foreground">Aucune compétence.</p>
        )}
        <div className="space-y-1">
          {skillGroups.map(([category, skills]) => (
            <div key={category} className="flex gap-2 text-sm">
              <span className="w-28 shrink-0 text-muted-foreground">{category}</span>
              <span>{skills.join(", ")}</span>
            </div>
          ))}
        </div>
      </div>

      <div>
        <p className="text-sm font-semibold mb-2">Formation</p>
        {cv.education.length === 0 && (
          <p className="text-sm text-muted-foreground">Aucune formation.</p>
        )}
        <div className="space-y-1">
          {cv.education.map((e) => (
            <p key={e.id} className="text-sm">
              {e.degree} — {e.school} {e.year ? `(${e.year})` : ""}
            </p>
          ))}
        </div>
      </div>

      <div>
        <p className="text-sm font-semibold mb-2">Certifications</p>
        {cv.certifications.length === 0 && (
          <p className="text-sm text-muted-foreground">Aucune certification.</p>
        )}
        <div className="space-y-1">
          {cv.certifications.map((c) => (
            <p key={c.id} className="text-sm">
              {c.name} — {c.issuer} {c.year ? `(${c.year})` : ""}
            </p>
          ))}
        </div>
      </div>
    </div>
  );
}

export function ProfileClient() {
  const [lang, setLang] = useState<"fr" | "en">("fr");
  const { data, isLoading, isError } = useQuery({
    queryKey: ["profile"],
    queryFn: fetchProfile,
  });

  if (isLoading) {
    return <div className="p-8 text-sm text-muted-foreground">Chargement…</div>;
  }
  if (isError || !data) {
    return (
      <div className="p-8 text-sm text-destructive">
        Erreur de chargement du profil.
      </div>
    );
  }

  const { contact, profile_md } = data.profile;
  const cv = lang === "fr" ? data.cv : data.cv_en;

  return (
    <div className="overflow-y-auto h-full">
      <div className="p-8 max-w-3xl mx-auto">
        <OnboardingBanner onboarding={data.onboarding} />

        <div className="mb-6">
          <h1 className="text-2xl font-bold">{contact.name || "Votre nom"}</h1>
          <p className="text-sm text-muted-foreground">{contact.title}</p>
        </div>

        <div className="rounded-xl p-5 mb-4 bg-card border border-border">
          <p className="text-sm font-semibold mb-3">Coordonnées</p>
          <div className="grid grid-cols-2 gap-2 text-sm">
            {contact.email && <p>✉ {contact.email}</p>}
            {contact.phone && <p>☎ {contact.phone}</p>}
            {contact.location && <p>📍 {contact.location}</p>}
            {contact.linkedin && <p>in {contact.linkedin}</p>}
            {contact.github && <p>⌥ {contact.github}</p>}
          </div>
        </div>

        {profile_md && (
          <div className="rounded-xl p-5 mb-4 bg-card border border-border">
            <p className="text-sm font-semibold mb-2">Résumé</p>
            <p className="text-sm text-muted-foreground whitespace-pre-wrap">
              {profile_md}
            </p>
          </div>
        )}

        <div className="rounded-xl p-5 bg-card border border-border">
          <div className="flex items-center justify-between mb-4">
            <p className="text-sm font-semibold">CV</p>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setLang("fr")}
                className={`px-3 py-1 rounded text-sm ${
                  lang === "fr"
                    ? "bg-primary text-primary-foreground"
                    : "bg-background border border-border text-muted-foreground"
                }`}
              >
                FR
              </button>
              <button
                type="button"
                onClick={() => setLang("en")}
                className={`px-3 py-1 rounded text-sm ${
                  lang === "en"
                    ? "bg-primary text-primary-foreground"
                    : "bg-background border border-border text-muted-foreground"
                }`}
              >
                EN
              </button>
            </div>
          </div>
          <CvSection cv={cv} />
        </div>
      </div>
    </div>
  );
}
