"use client";

import { useState } from "react";
import type { Offer } from "@/lib/types";

type EditFields = {
  company: string;
  role: string;
  offer_url: string;
  send_date: string;
  follow_up_date: string;
  contacts: string;
};

const FIELD_LABEL: Record<keyof EditFields, string> = {
  company: "Entreprise",
  role: "Rôle",
  offer_url: "URL",
  send_date: "Date d'envoi",
  follow_up_date: "Date de relance",
  contacts: "Contacts",
};

const DATE_FIELDS = new Set<keyof EditFields>(["send_date", "follow_up_date"]);

export function OfferEditForm({
  offer,
  onSave,
  onCancel,
}: {
  offer: Offer;
  onSave: (fields: Record<string, unknown>) => void;
  onCancel: () => void;
}) {
  const [fields, setFields] = useState<EditFields>({
    company: offer.company,
    role: offer.role,
    offer_url: offer.offer_url,
    send_date: offer.send_date ?? "",
    follow_up_date: offer.follow_up_date ?? "",
    contacts: offer.contacts,
  });

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        onSave({
          company: fields.company,
          role: fields.role,
          offer_url: fields.offer_url,
          send_date: fields.send_date || null,
          follow_up_date: fields.follow_up_date || null,
          contacts: fields.contacts,
        });
      }}
      className="flex flex-col gap-3"
    >
      {(Object.keys(FIELD_LABEL) as (keyof EditFields)[]).map((key) => (
        <label key={key} className="text-xs text-primary">
          {FIELD_LABEL[key]}
          <input
            type={DATE_FIELDS.has(key) ? "date" : "text"}
            value={fields[key]}
            onChange={(e) =>
              setFields((f) => ({ ...f, [key]: e.target.value }))
            }
            className="mt-1 w-full text-sm rounded-lg px-3 py-2 bg-background border border-border text-foreground focus:outline-none focus:border-primary"
          />
        </label>
      ))}
      <div className="flex gap-2 mt-1">
        <button
          type="submit"
          className="text-xs px-3 py-1.5 rounded-lg font-medium bg-primary text-primary-foreground hover:opacity-90"
        >
          Enregistrer
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="text-xs px-3 py-1.5 rounded-lg font-medium bg-background border border-border text-foreground hover:bg-card"
        >
          Annuler
        </button>
      </div>
    </form>
  );
}
