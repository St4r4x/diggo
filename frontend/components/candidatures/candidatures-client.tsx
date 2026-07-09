"use client";

import { useState, useEffect } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { OffersResponse, OfferDetailResponse } from "@/lib/types";
import { gradeColor, statusColor } from "@/lib/status-colors";
import { redirectOnUnauthenticated } from "@/lib/api-errors";
import { OfferEditForm } from "@/components/candidatures/offer-edit-form";
import { ScanButton } from "@/components/candidatures/scan-button";
import { PreparePanel } from "@/components/candidatures/prepare-panel";

type Filters = {
  status: string;
  grade: string;
  q: string;
  sal_min: string;
};

async function fetchOffers(filters: Filters): Promise<OffersResponse> {
  const params = new URLSearchParams();
  if (filters.status) params.set("status", filters.status);
  if (filters.grade) params.set("grade", filters.grade);
  if (filters.q) params.set("q", filters.q);
  if (filters.sal_min) params.set("sal_min", filters.sal_min);
  const res = await fetch(`/api/offers?${params.toString()}`);
  redirectOnUnauthenticated(res);
  if (res.status === 403) {
    const body = await res.json();
    window.location.href = body.detail?.redirect ?? "/profile";
    throw new Error("onboarding incomplete");
  }
  if (!res.ok) throw new Error("failed to fetch offers");
  return res.json();
}

async function fetchOfferDetail(id: number): Promise<OfferDetailResponse> {
  const res = await fetch(`/api/offers/${id}`);
  redirectOnUnauthenticated(res);
  if (!res.ok) throw new Error("failed to fetch offer");
  return res.json();
}

async function patchOffer(
  id: number,
  fields: Record<string, unknown>,
): Promise<OfferDetailResponse> {
  const res = await fetch(`/api/offers/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(fields),
  });
  redirectOnUnauthenticated(res);
  if (!res.ok) throw new Error("failed to update offer");
  return res.json();
}

async function deleteOffer(id: number): Promise<void> {
  const res = await fetch(`/api/offers/${id}`, { method: "DELETE" });
  redirectOnUnauthenticated(res);
  if (!res.ok) throw new Error("failed to delete offer");
}

const DESCRIPTION_SECTIONS = [
  ["mission", "Missions"],
  ["profil", "Profil recherché"],
  ["stack", "Stack technique"],
  ["avantages", "Avantages"],
  ["contrat", "Contrat"],
  ["salaire", "Salaire"],
] as const;

export function CandidaturesClient() {
  const [filters, setFilters] = useState<Filters>({
    status: "",
    grade: "",
    q: "",
    sal_min: "",
  });
  const [searchInput, setSearchInput] = useState<string>("");
  const [selectedId, setSelectedId] = useState<number | null>(null);

  // Debounce search input by 300ms before updating the query cache key
  useEffect(() => {
    const timeoutId = setTimeout(() => {
      setFilters((f) => ({ ...f, q: searchInput }));
    }, 300);
    return () => clearTimeout(timeoutId);
  }, [searchInput]);

  const { data, isLoading } = useQuery({
    queryKey: ["offers", filters],
    queryFn: () => fetchOffers(filters),
  });

  const { data: detail } = useQuery({
    queryKey: ["offer", selectedId],
    queryFn: () => fetchOfferDetail(selectedId as number),
    enabled: selectedId !== null,
  });

  const queryClient = useQueryClient();

  const updateMutation = useMutation({
    mutationFn: (fields: Record<string, unknown>) =>
      patchOffer(selectedId as number, fields),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["offers"] });
      queryClient.invalidateQueries({ queryKey: ["offer", selectedId] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteOffer(selectedId as number),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["offers"] });
      setSelectedId(null);
    },
  });

  const [notesInput, setNotesInput] = useState<string>("");
  const [isEditing, setIsEditing] = useState<boolean>(false);

  // Reset the notes draft and edit mode when switching offers, so the
  // previous offer's text/form doesn't briefly show while the new detail
  // is still loading.
  // ponytail: syncing from an external system (the query cache), not
  // derived state — same shape as theme-toggle.tsx's suppression.
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setNotesInput(detail?.offer.notes ?? "");
    setIsEditing(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [detail?.offer.id]);

  useEffect(() => {
    if (!detail || notesInput === detail.offer.notes) return;
    const timeoutId = setTimeout(() => {
      updateMutation.mutate({ notes: notesInput });
    }, 800);
    return () => clearTimeout(timeoutId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [notesInput]);

  const offers = data?.offers ?? [];
  const followupIds = new Set(data?.followup_ids ?? []);
  const statuses = data?.statuses ?? [];

  return (
    <div className="flex flex-col h-full">
      {followupIds.size > 0 && (
        <div className="shrink-0 px-5 py-2 text-sm font-medium flex items-center gap-2 bg-amber-950 border-b border-amber-800 text-amber-300">
          <span>⏰</span>
          <span>
            {followupIds.size} offre{followupIds.size > 1 ? "s" : ""} à
            relancer
          </span>
          <button
            onClick={() => setFilters((f) => ({ ...f, status: "Envoyée" }))}
            className="ml-2 underline text-amber-400 hover:text-amber-300"
          >
            Voir
          </button>
        </div>
      )}

      <div className="flex flex-1 min-h-0">
        <div className="w-96 shrink-0 flex flex-col border-r border-border bg-card">
          <div className="p-3 flex flex-col gap-2 border-b border-border">
            <input
              type="text"
              placeholder="🔍  Rechercher entreprise ou rôle..."
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              className="w-full text-sm rounded-lg px-3 py-2 bg-background border border-border text-foreground focus:outline-none focus:border-primary"
            />
            <div className="flex gap-2">
              <select
                value={filters.status}
                onChange={(e) =>
                  setFilters((f) => ({ ...f, status: e.target.value }))
                }
                className="flex-1 text-sm rounded-lg px-2 py-2 bg-background border border-border text-foreground focus:outline-none focus:border-primary"
              >
                <option value="">Tous statuts</option>
                {statuses.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
              <select
                value={filters.grade}
                onChange={(e) =>
                  setFilters((f) => ({ ...f, grade: e.target.value }))
                }
                className="flex-1 text-sm rounded-lg px-2 py-2 bg-background border border-border text-foreground focus:outline-none focus:border-primary"
              >
                <option value="">Tous grades</option>
                {["A", "B", "C", "D", "F"].map((g) => (
                  <option key={g} value={g}>
                    {g}
                  </option>
                ))}
              </select>
            </div>
            <select
              value={filters.sal_min}
              onChange={(e) =>
                setFilters((f) => ({ ...f, sal_min: e.target.value }))
              }
              className="w-full text-sm rounded-lg px-2 py-2 bg-background border border-border text-foreground focus:outline-none focus:border-primary"
            >
              <option value="">Tous salaires</option>
              <option value="40">≥ 40k€</option>
              <option value="50">≥ 50k€</option>
              <option value="60">≥ 60k€</option>
              <option value="70">≥ 70k€</option>
              <option value="80">≥ 80k€</option>
            </select>
            <ScanButton />
          </div>

          <div className="flex-1 overflow-y-auto">
            {isLoading && (
              <div className="p-5 text-muted-foreground text-sm text-center mt-8">
                Chargement...
              </div>
            )}
            {!isLoading && offers.length === 0 && (
              <div className="p-5 text-muted-foreground text-sm text-center mt-8">
                Aucune offre trouvée.
              </div>
            )}
            {offers.map((offer) => (
              <div
                key={offer.id}
                onClick={() => setSelectedId(offer.id)}
                className="px-3 py-2.5 cursor-pointer transition-colors flex items-center gap-3 border-b border-border hover:bg-background"
              >
                <div className="shrink-0 relative w-8 h-8">
                  <div className="w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold text-primary-foreground bg-primary">
                    {offer.company ? offer.company[0].toUpperCase() : "?"}
                  </div>
                  {followupIds.has(offer.id) && (
                    <span className="absolute -top-1 -right-1 w-2.5 h-2.5 rounded-full bg-red-500 border-2 border-card" />
                  )}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-semibold truncate text-foreground">
                    {offer.company}
                  </div>
                  <div className="text-xs truncate text-primary">
                    {offer.role}
                  </div>
                </div>
                <div className="shrink-0 flex flex-col items-end gap-1">
                  <span
                    className={`text-xs px-2 py-0.5 rounded font-bold ${gradeColor(offer.score_grade)}`}
                  >
                    {offer.score_grade}
                  </span>
                  <span
                    className={`text-xs px-1.5 py-0.5 rounded font-medium ${statusColor(offer.status)}`}
                  >
                    {offer.status}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-6">
          {selectedId === null && (
            <p className="text-muted-foreground text-sm text-center mt-8">
              Sélectionne une offre pour voir le détail
            </p>
          )}
          {selectedId !== null && !detail && (
            <p className="text-muted-foreground text-sm text-center mt-8">
              Chargement...
            </p>
          )}
          {detail && (
            <div className="w-full h-full flex flex-col">
              <div className="flex items-start justify-between mb-4 shrink-0">
                <div className="flex items-center gap-3 min-w-0">
                  <div className="w-12 h-12 rounded-xl flex items-center justify-center text-xl font-bold text-primary-foreground bg-primary shrink-0">
                    {detail.offer.company
                      ? detail.offer.company[0].toUpperCase()
                      : "?"}
                  </div>
                  <div className="min-w-0">
                    <h2 className="text-xl font-bold truncate text-foreground">
                      {detail.offer.company}
                    </h2>
                    <p className="text-sm truncate text-primary">
                      {detail.offer.role}
                    </p>
                  </div>
                </div>
                <div className="flex gap-2 items-center shrink-0 ml-4">
                  <span
                    className={`text-sm px-3 py-1 rounded-lg font-bold ${gradeColor(detail.offer.score_grade)}`}
                  >
                    {detail.offer.score_grade}{" "}
                    {detail.offer.score_value.toFixed(1)}
                  </span>
                  <span
                    className={`text-sm px-3 py-1 rounded-lg font-medium ${statusColor(detail.offer.status)}`}
                  >
                    {detail.offer.status}
                  </span>
                  <button
                    onClick={() => setIsEditing((v) => !v)}
                    className="text-xs px-3 py-1.5 rounded-lg font-medium bg-background border border-border text-foreground hover:bg-card"
                  >
                    {isEditing ? "Annuler" : "Modifier"}
                  </button>
                  <button
                    onClick={() => {
                      if (window.confirm("Supprimer cette candidature ?")) {
                        deleteMutation.mutate();
                      }
                    }}
                    className="text-xs px-3 py-1.5 rounded-lg font-medium bg-red-900 text-red-200 hover:bg-red-800"
                  >
                    Supprimer
                  </button>
                </div>
              </div>

              <div className="flex flex-wrap gap-1.5 mb-4 shrink-0">
                {statuses.map((s) => (
                  <button
                    key={s}
                    onClick={() => updateMutation.mutate({ status: s })}
                    disabled={s === detail.offer.status}
                    className={`text-xs px-2 py-1 rounded font-medium disabled:opacity-40 disabled:cursor-default ${statusColor(s)}`}
                  >
                    {s}
                  </button>
                ))}
              </div>

              <div className="mb-4 shrink-0">
                <PreparePanel offer={detail.offer} />
              </div>

              <div className="flex gap-6 flex-1 min-h-0">
                <div className="w-72 shrink-0 flex flex-col gap-5 overflow-y-auto">
                  {isEditing ? (
                    <OfferEditForm
                      offer={detail.offer}
                      onSave={(fields) => {
                        updateMutation.mutate(fields);
                        setIsEditing(false);
                      }}
                      onCancel={() => setIsEditing(false)}
                    />
                  ) : (
                  <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
                    <dt className="text-primary">Détecté le</dt>
                    <dd className="text-foreground">
                      {detail.offer.detection_date}
                    </dd>
                    {detail.offer.send_date && (
                      <>
                        <dt className="text-primary">Envoyé le</dt>
                        <dd className="text-foreground">
                          {detail.offer.send_date}
                        </dd>
                      </>
                    )}
                    {detail.offer.follow_up_date && (
                      <>
                        <dt className="text-primary">Relance</dt>
                        <dd className="text-foreground">
                          {detail.offer.follow_up_date}
                        </dd>
                      </>
                    )}
                    {detail.offer.offer_url.startsWith("http") && (
                      <>
                        <dt className="text-primary">URL</dt>
                        <dd>
                          <a
                            href={detail.offer.offer_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="hover:text-primary underline break-all text-xs text-muted-foreground"
                          >
                            {detail.offer.offer_url}
                          </a>
                        </dd>
                      </>
                    )}
                    {detail.offer.contacts && (
                      <>
                        <dt className="text-primary">Contacts</dt>
                        <dd className="text-foreground">
                          {detail.offer.contacts}
                        </dd>
                      </>
                    )}
                    {detail.offer.cv_path && (
                      <>
                        <dt className="text-primary">CV</dt>
                        <dd>
                          <a
                            href={`/api/offers/${detail.offer.id}/cv`}
                            className="hover:text-primary underline text-xs text-muted-foreground"
                          >
                            Télécharger
                          </a>
                        </dd>
                      </>
                    )}
                    {detail.offer.cover_letter_path && (
                      <>
                        <dt className="text-primary">Lettre de motivation</dt>
                        <dd>
                          <a
                            href={`/api/offers/${detail.offer.id}/cover-letter`}
                            className="hover:text-primary underline text-xs text-muted-foreground"
                          >
                            Télécharger
                          </a>
                        </dd>
                      </>
                    )}
                    {detail.offer.prep_sheet_path && (
                      <>
                        <dt className="text-primary">Fiche prep</dt>
                        <dd>
                          <a
                            href={`/api/offers/${detail.offer.id}/prep-sheet`}
                            className="hover:text-primary underline text-xs text-muted-foreground"
                          >
                            Télécharger
                          </a>
                        </dd>
                      </>
                    )}
                  </dl>
                  )}
                </div>

                <div className="flex-1 flex flex-col gap-4 min-h-0 min-w-0 overflow-y-auto">
                  <div className="shrink-0">
                    <p className="text-sm font-semibold mb-2 text-primary">
                      Description
                    </p>
                    <div className="space-y-3">
                      {DESCRIPTION_SECTIONS.map(([key, label]) =>
                        detail.description[key] ? (
                          <div key={key}>
                            <p className="text-xs font-semibold mb-1 text-primary">
                              {label}
                            </p>
                            <p className="whitespace-pre-wrap rounded-lg p-2 text-xs text-muted-foreground bg-background border border-border">
                              {detail.description[key]}
                            </p>
                          </div>
                        ) : null,
                      )}
                    </div>
                  </div>

                  <div className="flex-1 flex flex-col min-h-0 shrink-0">
                    <p className="text-sm font-semibold mb-2 text-primary">
                      Notes
                    </p>
                    <textarea
                      value={notesInput}
                      onChange={(e) => setNotesInput(e.target.value)}
                      rows={5}
                      placeholder="Ajouter une note..."
                      className="w-full text-sm rounded-lg p-2 bg-background border border-border text-foreground focus:outline-none focus:border-primary resize-none"
                    />
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
