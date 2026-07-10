"use client";

import { useRef, useState } from "react";

type FieldConfig = { key: string; label: string; type?: "text" | "number" };
type Row = Record<string, string>;
type KeyedRow = { key: number; row: Row };

export function EditableListForm({
  entries,
  fields,
  emptyEntry,
  onSave,
  onCancel,
}: {
  entries: Row[];
  fields: FieldConfig[];
  emptyEntry: Row;
  onSave: (rows: Row[]) => void;
  onCancel: () => void;
}) {
  const nextKey = useRef(entries.length);
  const [rows, setRows] = useState<KeyedRow[]>(
    entries.map((row, i) => ({ key: i, row })),
  );

  function updateRow(index: number, fieldKey: string, value: string) {
    setRows((prev) =>
      prev.map((r, i) => (i === index ? { ...r, row: { ...r.row, [fieldKey]: value } } : r)),
    );
  }

  return (
    <div className="flex flex-col gap-2">
      {rows.map(({ key, row }, i) => (
        <div
          key={key}
          className="flex gap-2 items-end rounded-lg p-2 bg-background border border-border"
        >
          {fields.map((f) => (
            <label key={f.key} className="text-xs text-primary flex-1">
              {f.label}
              <input
                type={f.type ?? "text"}
                value={row[f.key] ?? ""}
                onChange={(e) => updateRow(i, f.key, e.target.value)}
                className="mt-1 w-full text-sm rounded px-2 py-1 bg-card border border-border text-foreground"
              />
            </label>
          ))}
          <button
            type="button"
            onClick={() => setRows((prev) => prev.filter((_, idx) => idx !== i))}
            className="text-xs text-destructive px-2 py-1.5"
          >
            🗑
          </button>
        </div>
      ))}
      <button
        type="button"
        onClick={() =>
          setRows((prev) => [...prev, { key: nextKey.current++, row: { ...emptyEntry } }])
        }
        className="text-xs px-3 py-1.5 rounded-lg border border-dashed border-border text-muted-foreground hover:text-foreground self-start"
      >
        + Ajouter
      </button>
      <div className="flex gap-2 mt-1">
        <button
          type="button"
          onClick={() => onSave(rows.map((r) => r.row))}
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
