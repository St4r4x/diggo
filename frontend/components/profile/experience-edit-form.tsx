"use client";

import { useRef, useState } from "react";
import type { CvExperience } from "@/lib/types";

export type ExperienceRow = {
  title: string;
  company: string;
  type: string;
  period: string;
  bullets: string[];
};

type KeyedBullet = { key: number; value: string };
type KeyedRow = { key: number; row: ExperienceRow; bullets: KeyedBullet[] };

function toKeyedRow(exp: CvExperience, key: number): KeyedRow {
  return {
    key,
    row: {
      title: exp.title,
      company: exp.company,
      type: exp.type,
      period: exp.period,
      bullets: exp.bullets,
    },
    bullets: exp.bullets.map((value, i) => ({ key: i, value })),
  };
}

export function ExperienceEditForm({
  experience,
  onSave,
  onCancel,
}: {
  experience: CvExperience[];
  onSave: (rows: ExperienceRow[]) => void;
  onCancel: () => void;
}) {
  const nextRowKey = useRef(experience.length);
  const nextBulletKey = useRef(
    Math.max(0, ...experience.map((exp) => exp.bullets.length)),
  );
  const [rows, setRows] = useState<KeyedRow[]>(
    experience.map((exp, i) => toKeyedRow(exp, i)),
  );

  function updateRow(index: number, patch: Partial<ExperienceRow>) {
    setRows((prev) =>
      prev.map((r, i) => (i === index ? { ...r, row: { ...r.row, ...patch } } : r)),
    );
  }

  function updateBullet(rowIndex: number, bulletIndex: number, value: string) {
    setRows((prev) =>
      prev.map((r, i) =>
        i === rowIndex
          ? {
              ...r,
              bullets: r.bullets.map((b, bi) => (bi === bulletIndex ? { ...b, value } : b)),
            }
          : r,
      ),
    );
  }

  function addBullet(rowIndex: number) {
    setRows((prev) =>
      prev.map((r, i) =>
        i === rowIndex
          ? { ...r, bullets: [...r.bullets, { key: nextBulletKey.current++, value: "" }] }
          : r,
      ),
    );
  }

  function removeBullet(rowIndex: number, bulletIndex: number) {
    setRows((prev) =>
      prev.map((r, i) =>
        i === rowIndex
          ? { ...r, bullets: r.bullets.filter((_, bi) => bi !== bulletIndex) }
          : r,
      ),
    );
  }

  return (
    <div className="flex flex-col gap-3">
      {rows.map(({ key, row, bullets }, i) => (
        <div
          key={key}
          className="rounded-lg p-3 bg-background border border-border flex flex-col gap-2"
        >
          <div className="grid grid-cols-2 gap-2">
            <label className="text-xs text-primary">
              Titre
              <input
                value={row.title}
                onChange={(e) => updateRow(i, { title: e.target.value })}
                className="mt-1 w-full text-sm rounded px-2 py-1 bg-card border border-border text-foreground"
              />
            </label>
            <label className="text-xs text-primary">
              Entreprise
              <input
                value={row.company}
                onChange={(e) => updateRow(i, { company: e.target.value })}
                className="mt-1 w-full text-sm rounded px-2 py-1 bg-card border border-border text-foreground"
              />
            </label>
            <label className="text-xs text-primary">
              Type
              <input
                value={row.type}
                onChange={(e) => updateRow(i, { type: e.target.value })}
                className="mt-1 w-full text-sm rounded px-2 py-1 bg-card border border-border text-foreground"
              />
            </label>
            <label className="text-xs text-primary">
              Période
              <input
                value={row.period}
                onChange={(e) => updateRow(i, { period: e.target.value })}
                className="mt-1 w-full text-sm rounded px-2 py-1 bg-card border border-border text-foreground"
              />
            </label>
          </div>
          <div>
            <p className="text-xs text-primary mb-1">Points clés</p>
            <div className="flex flex-col gap-1">
              {bullets.map((b, bi) => (
                <div key={b.key} className="flex gap-1">
                  <input
                    value={b.value}
                    onChange={(e) => updateBullet(i, bi, e.target.value)}
                    className="flex-1 text-sm rounded px-2 py-1 bg-card border border-border text-foreground"
                  />
                  <button
                    type="button"
                    onClick={() => removeBullet(i, bi)}
                    className="text-xs text-destructive px-2"
                  >
                    🗑
                  </button>
                </div>
              ))}
            </div>
            <button
              type="button"
              onClick={() => addBullet(i)}
              className="text-xs text-muted-foreground hover:text-foreground mt-1"
            >
              + Point clé
            </button>
          </div>
          <button
            type="button"
            onClick={() => setRows((prev) => prev.filter((_, idx) => idx !== i))}
            className="text-xs text-destructive self-start"
          >
            🗑 Supprimer cette expérience
          </button>
        </div>
      ))}
      <button
        type="button"
        onClick={() =>
          setRows((prev) => [
            ...prev,
            {
              key: nextRowKey.current++,
              row: { title: "", company: "", type: "", period: "", bullets: [] },
              bullets: [],
            },
          ])
        }
        className="text-xs px-3 py-1.5 rounded-lg border border-dashed border-border text-muted-foreground hover:text-foreground self-start"
      >
        + Ajouter une expérience
      </button>
      <div className="flex gap-2 mt-1">
        <button
          type="button"
          onClick={() =>
            onSave(rows.map((r) => ({ ...r.row, bullets: r.bullets.map((b) => b.value) })))
          }
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
    </div>
  );
}
