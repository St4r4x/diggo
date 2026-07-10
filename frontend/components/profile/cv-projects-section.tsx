"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { CvProject } from "@/lib/types";
import { redirectOnUnauthenticated } from "@/lib/api-errors";
import { EditableListForm } from "@/components/profile/editable-list-form";
import { EditableSectionHeader } from "@/components/profile/editable-section-header";

async function saveProjects(
  lang: "fr" | "en",
  entries: { name: string; stack: string[]; desc: string; sort_order: number }[],
): Promise<void> {
  const res = await fetch(`/api/profile/cv/projects?lang=${lang}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(entries),
  });
  redirectOnUnauthenticated(res);
  if (!res.ok) throw new Error("failed to save projects");
}

export function CvProjectsSection({
  projects,
  lang,
}: {
  projects: CvProject[];
  lang: "fr" | "en";
}) {
  const [isEditing, setIsEditing] = useState(false);
  const queryClient = useQueryClient();
  const mutation = useMutation({
    mutationFn: (
      entries: { name: string; stack: string[]; desc: string; sort_order: number }[],
    ) => saveProjects(lang, entries),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["profile"] }),
  });

  return (
    <div>
      <EditableSectionHeader
        title="Projets"
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
          entries={projects.map((p) => ({
            name: p.name,
            stack: p.stack.join(", "),
            desc: p.desc,
          }))}
          fields={[
            { key: "name", label: "Nom" },
            { key: "stack", label: "Stack (séparé par des virgules)" },
            { key: "desc", label: "Description" },
          ]}
          emptyEntry={{ name: "", stack: "", desc: "" }}
          onSave={(rows) => {
            mutation.mutate(
              rows
                .filter((r) => r.name.trim())
                .map((r, i) => ({
                  name: r.name,
                  stack: r.stack
                    .split(",")
                    .map((s) => s.trim())
                    .filter(Boolean),
                  desc: r.desc,
                  sort_order: i,
                })),
            );
            setIsEditing(false);
          }}
          onCancel={() => setIsEditing(false)}
        />
      ) : projects.length === 0 ? (
        <p className="text-sm text-muted-foreground">Aucun projet.</p>
      ) : (
        <div className="space-y-1">
          {projects.map((p) => (
            <p key={p.id} className="text-sm">
              <span className="font-medium">{p.name}</span>
              {p.stack.length > 0 && (
                <span className="text-muted-foreground"> · {p.stack.join(", ")}</span>
              )}
              {p.desc && <span className="text-muted-foreground"> — {p.desc}</span>}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}
