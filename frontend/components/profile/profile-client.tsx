"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import type { ProfileResponse } from "@/lib/types";
import { redirectOnUnauthenticated } from "@/lib/api-errors";
import { OnboardingBanner } from "@/components/onboarding-banner";
import { ContactSection } from "@/components/profile/contact-section";
import { SummarySection } from "@/components/profile/summary-section";
import { CvMetaSection } from "@/components/profile/cv-meta-section";
import { CvSkillsSection } from "@/components/profile/cv-skills-section";
import { CvCertificationsSection } from "@/components/profile/cv-certifications-section";
import { CvEducationSection } from "@/components/profile/cv-education-section";
import { CvExperienceSection } from "@/components/profile/cv-experience-section";
import { CvProjectsSection } from "@/components/profile/cv-projects-section";
import { CvLanguagesSection } from "@/components/profile/cv-languages-section";
import { CvHobbiesSection } from "@/components/profile/cv-hobbies-section";

async function fetchProfile(): Promise<ProfileResponse> {
  const res = await fetch("/api/profile");
  redirectOnUnauthenticated(res);
  if (!res.ok) throw new Error("failed to fetch profile");
  return res.json();
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

        <ContactSection contact={contact} />
        <SummarySection profileMd={profile_md} />

        <div className="rounded-xl p-5 bg-card border border-border">
          <div className="flex items-center justify-between mb-4">
            <p className="text-sm font-semibold">CV</p>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setLang("fr")}
                aria-pressed={lang === "fr"}
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
                aria-pressed={lang === "en"}
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
          <div className="space-y-6">
            <CvMetaSection key={lang} summary={cv.meta.summary} lang={lang} />
            <CvExperienceSection key={lang} experience={cv.experience} lang={lang} />
            <CvSkillsSection key={lang} skills={cv.skills} lang={lang} />
            <CvEducationSection key={lang} education={cv.education} lang={lang} />
            <CvCertificationsSection certifications={cv.certifications} />
            <CvProjectsSection key={lang} projects={cv.projects} lang={lang} />
            <CvLanguagesSection key={lang} languages={cv.languages} lang={lang} />
            <CvHobbiesSection key={lang} hobbies={cv.hobbies} lang={lang} />
          </div>
        </div>
      </div>
    </div>
  );
}
