"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { CvExperience } from "@/lib/types";
import { redirectOnUnauthenticated } from "@/lib/api-errors";
import { ExperienceEditForm, type ExperienceRow } from "@/components/profile/experience-edit-form";

async function saveExperience(lang: "fr" | "en", entries: ExperienceRow[]): Promise<void> {
  const res = await fetch(`/api/profile/cv/experience?lang=${lang}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(entries),
  });
  redirectOnUnauthenticated(res);
  if (!res.ok) throw new Error("failed to save experience");
}

async function deleteExperience(id: number): Promise<void> {
  const res = await fetch(`/api/profile/cv/experience/${id}`, { method: "DELETE" });
  redirectOnUnauthenticated(res);
  if (!res.ok) throw new Error("failed to delete experience");
}

export function CvExperienceSection({
  experience,
  lang,
}: {
  experience: CvExperience[];
  lang: "fr" | "en";
}) {
  const [isEditing, setIsEditing] = useState(false);
  const queryClient = useQueryClient();
  const saveMutation = useMutation({
    mutationFn: (entries: ExperienceRow[]) => saveExperience(lang, entries),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["profile"] }),
  });
  const deleteMutation = useMutation({
    mutationFn: deleteExperience,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["profile"] }),
  });

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <p className="text-sm font-semibold">Expériences</p>
        <div className="flex items-center gap-2">
          {saveMutation.isSuccess && !isEditing && (
            <span className="text-xs text-primary">✓ Enregistré</span>
          )}
          <button
            type="button"
            onClick={() => {
              saveMutation.reset();
              setIsEditing((v) => !v);
            }}
            className="text-xs text-primary hover:underline"
          >
            {isEditing ? "Annuler" : "Modifier"}
          </button>
        </div>
      </div>
      {isEditing ? (
        <ExperienceEditForm
          experience={experience}
          onSave={(rows) => {
            saveMutation.mutate(rows.filter((r) => r.title.trim() || r.company.trim()));
            setIsEditing(false);
          }}
          onCancel={() => setIsEditing(false)}
        />
      ) : experience.length === 0 ? (
        <p className="text-sm text-muted-foreground">Aucune expérience.</p>
      ) : (
        <div className="space-y-3">
          {experience.map((exp) => (
            <div key={exp.id} className="rounded-lg p-3 bg-background border border-border">
              <div className="flex items-start justify-between">
                <p className="text-sm font-medium">
                  {exp.title} — {exp.company}
                </p>
                <button
                  type="button"
                  onClick={() => deleteMutation.mutate(exp.id)}
                  className="text-xs text-destructive"
                >
                  🗑
                </button>
              </div>
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
      )}
    </div>
  );
}
