"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { redirectOnUnauthenticated } from "@/lib/api-errors";
import { EditableSectionHeader } from "@/components/profile/editable-section-header";
import { TextEditBody } from "@/components/profile/text-edit-body";

async function saveText(profileMd: string): Promise<void> {
  const res = await fetch("/api/profile/text", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ profile_md: profileMd }),
  });
  redirectOnUnauthenticated(res);
  if (!res.ok) throw new Error("failed to save résumé");
}

export function SummarySection({ profileMd }: { profileMd: string }) {
  const [isEditing, setIsEditing] = useState(false);
  const [draft, setDraft] = useState(profileMd);
  const queryClient = useQueryClient();
  const mutation = useMutation({
    mutationFn: saveText,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["profile"] }),
  });

  return (
    <div className="rounded-xl p-5 mb-4 bg-card border border-border">
      <EditableSectionHeader
        title="Résumé"
        isEditing={isEditing}
        showSuccess={mutation.isSuccess && !isEditing}
        errorMessage={mutation.isError ? mutation.error.message : undefined}
        onToggle={() => {
          mutation.reset();
          if (!isEditing) setDraft(profileMd);
          setIsEditing((v) => !v);
        }}
      />
      <TextEditBody
        isEditing={isEditing}
        draft={draft}
        setDraft={setDraft}
        value={profileMd}
        emptyLabel="Aucun résumé."
        rows={6}
        onSave={() => {
          mutation.mutate(draft);
          setIsEditing(false);
        }}
        onCancel={() => setIsEditing(false)}
      />
    </div>
  );
}
