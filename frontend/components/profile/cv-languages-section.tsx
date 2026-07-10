"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { CvLanguage } from "@/lib/types";
import { redirectOnUnauthenticated } from "@/lib/api-errors";
import { EditableListForm } from "@/components/profile/editable-list-form";
import { EditableSectionHeader } from "@/components/profile/editable-section-header";

async function saveLanguages(
  lang: "fr" | "en",
  entries: { name: string; sort_order: number }[],
): Promise<void> {
  const res = await fetch(`/api/profile/cv/languages?lang=${lang}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(entries),
  });
  redirectOnUnauthenticated(res);
  if (!res.ok) throw new Error("failed to save languages");
}

export function CvLanguagesSection({
  languages,
  lang,
}: {
  languages: CvLanguage[];
  lang: "fr" | "en";
}) {
  const [isEditing, setIsEditing] = useState(false);
  const queryClient = useQueryClient();
  const mutation = useMutation({
    mutationFn: (entries: { name: string; sort_order: number }[]) =>
      saveLanguages(lang, entries),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["profile"] }),
  });

  return (
    <div>
      <EditableSectionHeader
        title="Langues"
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
          entries={languages.map((l) => ({ name: l.name }))}
          fields={[{ key: "name", label: "Langue" }]}
          emptyEntry={{ name: "" }}
          onSave={(rows) => {
            mutation.mutate(
              rows
                .filter((r) => r.name.trim())
                .map((r, i) => ({ name: r.name, sort_order: i })),
            );
            setIsEditing(false);
          }}
          onCancel={() => setIsEditing(false)}
        />
      ) : languages.length === 0 ? (
        <p className="text-sm text-muted-foreground">Aucune langue.</p>
      ) : (
        <p className="text-sm text-muted-foreground">
          {languages.map((l) => l.name).join(" · ")}
        </p>
      )}
    </div>
  );
}
