"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { CvHobby } from "@/lib/types";
import { redirectOnUnauthenticated } from "@/lib/api-errors";
import { EditableListForm } from "@/components/profile/editable-list-form";
import { EditableSectionHeader } from "@/components/profile/editable-section-header";

async function saveHobbies(
  lang: "fr" | "en",
  entries: { name: string; sort_order: number }[],
): Promise<void> {
  const res = await fetch(`/api/profile/cv/hobbies?lang=${lang}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(entries),
  });
  redirectOnUnauthenticated(res);
  if (!res.ok) throw new Error("failed to save hobbies");
}

export function CvHobbiesSection({
  hobbies,
  lang,
}: {
  hobbies: CvHobby[];
  lang: "fr" | "en";
}) {
  const [isEditing, setIsEditing] = useState(false);
  const queryClient = useQueryClient();
  const mutation = useMutation({
    mutationFn: (entries: { name: string; sort_order: number }[]) =>
      saveHobbies(lang, entries),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["profile"] }),
  });

  return (
    <div>
      <EditableSectionHeader
        title="Centres d'intérêt"
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
          entries={hobbies.map((h) => ({ name: h.name }))}
          fields={[{ key: "name", label: "Centre d'intérêt" }]}
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
      ) : hobbies.length === 0 ? (
        <p className="text-sm text-muted-foreground">Aucun centre d&apos;intérêt.</p>
      ) : (
        <p className="text-sm text-muted-foreground">
          {hobbies.map((h) => h.name).join(" · ")}
        </p>
      )}
    </div>
  );
}
