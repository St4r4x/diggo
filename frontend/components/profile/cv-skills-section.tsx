"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { CvSkill } from "@/lib/types";
import { redirectOnUnauthenticated } from "@/lib/api-errors";
import { EditableListForm } from "@/components/profile/editable-list-form";
import { EditableSectionHeader } from "@/components/profile/editable-section-header";

async function saveSkills(
  lang: "fr" | "en",
  entries: { category: string; skill: string; sort_order: number }[],
): Promise<void> {
  const res = await fetch(`/api/profile/cv/skills?lang=${lang}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(entries),
  });
  redirectOnUnauthenticated(res);
  if (!res.ok) throw new Error("failed to save skills");
}

function groupSkillsByCategory(skills: CvSkill[]) {
  const byCategory = new Map<string, string[]>();
  for (const s of skills) {
    const list = byCategory.get(s.category) ?? [];
    list.push(s.skill);
    byCategory.set(s.category, list);
  }
  return Array.from(byCategory.entries());
}

export function CvSkillsSection({ skills, lang }: { skills: CvSkill[]; lang: "fr" | "en" }) {
  const [isEditing, setIsEditing] = useState(false);
  const queryClient = useQueryClient();
  const mutation = useMutation({
    mutationFn: (entries: { category: string; skill: string; sort_order: number }[]) =>
      saveSkills(lang, entries),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["profile"] }),
  });
  const skillGroups = groupSkillsByCategory(skills);

  return (
    <div>
      <EditableSectionHeader
        title="Compétences"
        isEditing={isEditing}
        showSuccess={mutation.isSuccess && !isEditing}
        errorMessage={mutation.isError ? mutation.error.message : undefined}
        onToggle={() => {
          mutation.reset();
          setIsEditing((v) => !v);
        }}
      />
      {isEditing ? (
        <EditableListForm
          entries={skills.map((s) => ({ category: s.category, skill: s.skill }))}
          fields={[
            { key: "category", label: "Catégorie" },
            { key: "skill", label: "Compétence" },
          ]}
          emptyEntry={{ category: "", skill: "" }}
          onSave={(rows) => {
            mutation.mutate(
              rows
                .filter((r) => r.skill.trim())
                .map((r, i) => ({ category: r.category, skill: r.skill, sort_order: i })),
            );
            setIsEditing(false);
          }}
          onCancel={() => setIsEditing(false)}
        />
      ) : skillGroups.length === 0 ? (
        <p className="text-sm text-muted-foreground">Aucune compétence.</p>
      ) : (
        <div className="space-y-1">
          {skillGroups.map(([category, catSkills]) => (
            <div key={category} className="flex gap-2 text-sm">
              <span className="w-28 shrink-0 text-muted-foreground">{category}</span>
              <span>{catSkills.join(", ")}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
