"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { CvCertification } from "@/lib/types";
import { redirectOnUnauthenticated } from "@/lib/api-errors";
import { EditableListForm } from "@/components/profile/editable-list-form";
import { EditableSectionHeader } from "@/components/profile/editable-section-header";

async function saveCertifications(
  entries: { name: string; issuer: string; year: number | null }[],
): Promise<void> {
  const res = await fetch("/api/profile/cv/certifications", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(entries),
  });
  redirectOnUnauthenticated(res);
  if (!res.ok) throw new Error("failed to save certifications");
}

export function CvCertificationsSection({
  certifications,
}: {
  certifications: CvCertification[];
}) {
  const [isEditing, setIsEditing] = useState(false);
  const queryClient = useQueryClient();
  const mutation = useMutation({
    mutationFn: saveCertifications,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["profile"] }),
  });

  return (
    <div>
      <EditableSectionHeader
        title="Certifications"
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
          entries={certifications.map((c) => ({
            name: c.name,
            issuer: c.issuer,
            year: c.year != null ? String(c.year) : "",
          }))}
          fields={[
            { key: "name", label: "Nom" },
            { key: "issuer", label: "Émetteur" },
            { key: "year", label: "Année", type: "number" },
          ]}
          emptyEntry={{ name: "", issuer: "", year: "" }}
          onSave={(rows) => {
            mutation.mutate(
              rows
                .filter((r) => r.name.trim())
                .map((r) => ({
                  name: r.name,
                  issuer: r.issuer,
                  year: r.year ? Number(r.year) : null,
                })),
            );
            setIsEditing(false);
          }}
          onCancel={() => setIsEditing(false)}
        />
      ) : certifications.length === 0 ? (
        <p className="text-sm text-muted-foreground">Aucune certification.</p>
      ) : (
        <div className="space-y-1">
          {certifications.map((c) => (
            <p key={c.id} className="text-sm">
              {c.name} — {c.issuer} {c.year ? `(${c.year})` : ""}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}
