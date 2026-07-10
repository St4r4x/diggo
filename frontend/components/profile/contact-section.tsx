"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { ProfileContact } from "@/lib/types";
import { redirectOnUnauthenticated } from "@/lib/api-errors";
import { ContactEditForm } from "@/components/profile/contact-edit-form";
import { EditableSectionHeader } from "@/components/profile/editable-section-header";

async function saveContact(contact: ProfileContact): Promise<void> {
  const res = await fetch("/api/profile/contact", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(contact),
  });
  redirectOnUnauthenticated(res);
  if (!res.ok) throw new Error("failed to save contact");
}

function withProtocol(url: string): string {
  return url.startsWith("http") ? url : `https://${url}`;
}

export function ContactSection({ contact }: { contact: ProfileContact }) {
  const [isEditing, setIsEditing] = useState(false);
  const queryClient = useQueryClient();
  const mutation = useMutation({
    mutationFn: saveContact,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["profile"] }),
  });

  return (
    <div className="rounded-xl p-5 mb-4 bg-card border border-border">
      <EditableSectionHeader
        title="Coordonnées"
        isEditing={isEditing}
        showSuccess={mutation.isSuccess && !isEditing}
        errorMessage={mutation.isError ? mutation.error.message : undefined}
        onToggle={() => {
          mutation.reset();
          setIsEditing((v) => !v);
        }}
        className="mb-3"
      />
      {isEditing ? (
        <ContactEditForm
          contact={contact}
          onSave={(fields) => {
            mutation.mutate(fields);
            setIsEditing(false);
          }}
          onCancel={() => setIsEditing(false)}
        />
      ) : (
        <div className="grid grid-cols-2 gap-2 text-sm">
          {contact.email && <p>✉ {contact.email}</p>}
          {contact.phone && <p>☎ {contact.phone}</p>}
          {contact.location && <p>📍 {contact.location}</p>}
          {contact.linkedin && (
            <a href={withProtocol(contact.linkedin)} className="text-primary hover:underline">
              in {contact.linkedin}
            </a>
          )}
          {contact.github && (
            <a href={withProtocol(contact.github)} className="text-primary hover:underline">
              ⌥ {contact.github}
            </a>
          )}
        </div>
      )}
    </div>
  );
}
