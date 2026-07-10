"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { redirectOnUnauthenticated } from "@/lib/api-errors";
import { EditableSectionHeader } from "@/components/profile/editable-section-header";
import { TextEditBody } from "@/components/profile/text-edit-body";

async function saveCvMeta(lang: "fr" | "en", summary: string): Promise<void> {
  const res = await fetch(`/api/profile/cv/meta?lang=${lang}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ summary }),
  });
  redirectOnUnauthenticated(res);
  if (!res.ok) throw new Error("failed to save CV summary");
}

export function CvMetaSection({ summary, lang }: { summary: string; lang: "fr" | "en" }) {
  const [isEditing, setIsEditing] = useState(false);
  const [draft, setDraft] = useState(summary);
  const queryClient = useQueryClient();
  const mutation = useMutation({
    mutationFn: (value: string) => saveCvMeta(lang, value),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["profile"] }),
  });

  return (
    <div>
      <EditableSectionHeader
        title="Résumé (CV)"
        isEditing={isEditing}
        showSuccess={mutation.isSuccess && !isEditing}
        errorMessage={mutation.isError ? mutation.error.message : undefined}
        onToggle={() => {
          mutation.reset();
          if (!isEditing) setDraft(summary);
          setIsEditing((v) => !v);
        }}
        className="mb-1"
      />
      <TextEditBody
        isEditing={isEditing}
        draft={draft}
        setDraft={setDraft}
        value={summary}
        emptyLabel="Aucun résumé."
        rows={4}
        onSave={() => {
          mutation.mutate(draft);
          setIsEditing(false);
        }}
        onCancel={() => setIsEditing(false)}
      />
    </div>
  );
}
