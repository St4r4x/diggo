"use client";

import { useQuery } from "@tanstack/react-query";
import type { StatsResponse } from "@/lib/types";
import { statusColor } from "@/lib/status-colors";
import {
  redirectOnUnauthenticated,
  redirectOnOnboardingIncomplete,
} from "@/lib/api-errors";

async function fetchStats(): Promise<StatsResponse> {
  const res = await fetch("/api/stats");
  redirectOnUnauthenticated(res);
  await redirectOnOnboardingIncomplete(res);
  if (!res.ok) throw new Error("failed to fetch stats");
  return res.json();
}

export function StatsClient() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["stats"],
    queryFn: fetchStats,
  });

  if (isLoading) {
    return (
      <div className="p-8 text-sm text-muted-foreground">Chargement…</div>
    );
  }
  if (isError || !data) {
    return (
      <div className="p-8 text-sm text-destructive">
        Erreur de chargement des statistiques.
      </div>
    );
  }

  const { stats, funnel, exits, max_count, latest_report_html, latest_report_date } =
    data;
  const statuses = Object.keys(stats.by_status);

  return (
    <div className="overflow-y-auto h-full">
      <div className="p-8 max-w-2xl mx-auto">
        <h1 className="text-2xl font-bold mb-8">Statistiques</h1>

        <div className="grid grid-cols-2 gap-4 mb-8">
          <div className="rounded-xl p-5 bg-card border border-border border-t-2 border-t-primary">
            <p className="text-sm mb-1 text-muted-foreground">Total candidatures</p>
            <p className="text-3xl font-bold">{stats.total}</p>
          </div>
          <div className="rounded-xl p-5 bg-card border border-border border-t-2 border-t-primary">
            <p className="text-sm mb-1 text-muted-foreground">Taux de réponse</p>
            <p className="text-3xl font-bold">{stats.response_rate}%</p>
          </div>
          <div className="rounded-xl p-5 bg-card border border-border border-t-2 border-t-primary">
            <p className="text-sm mb-1 text-muted-foreground">Entretiens obtenus</p>
            <p className="text-3xl font-bold">{stats.interview_count}</p>
          </div>
          <div
            className={`rounded-xl p-5 bg-card border-t-2 border-t-primary ${
              stats.stale_count > 0 ? "border border-amber-500/40" : "border border-border"
            }`}
          >
            <p className="text-sm mb-1 text-muted-foreground">Relances en retard (+7j)</p>
            <p
              className={`text-3xl font-bold ${
                stats.stale_count > 0 ? "text-amber-400" : ""
              }`}
            >
              {stats.stale_count}
            </p>
          </div>
        </div>

        <h2 className="text-lg font-semibold mb-4">Funnel candidatures</h2>
        <div className="rounded-xl p-5 mb-8 bg-card border border-border">
          {funnel.map((step, i) => (
            <div className="mb-1" key={step.status}>
              {step.rate !== null && i > 0 && (
                <div className="text-xs mb-1 ml-36 text-primary">↓ {step.rate}%</div>
              )}
              <div className="flex items-center gap-3">
                <span
                  className={`w-32 text-xs px-2 py-1 rounded-lg font-medium text-center shrink-0 ${statusColor(
                    step.status,
                  )}`}
                >
                  {step.status}
                </span>
                <div className="flex-1 rounded-full h-2 bg-muted">
                  <div
                    className="h-2 rounded-full bg-primary"
                    style={{ width: `${Math.floor((step.count / max_count) * 100)}%` }}
                  />
                </div>
                <span className="text-sm w-6 text-right shrink-0 text-muted-foreground">
                  {step.count}
                </span>
              </div>
            </div>
          ))}

          <div className="mt-4 pt-4 border-t border-border">
            <p className="text-xs mb-2 text-muted-foreground">Sorties pipeline</p>
            {exits.map((exit) => (
              <div className="flex items-center gap-3 mb-1" key={exit.status}>
                <span
                  className={`w-32 text-xs px-2 py-1 rounded-lg font-medium text-center shrink-0 ${statusColor(
                    exit.status,
                  )}`}
                >
                  {exit.status}
                </span>
                <div className="flex-1 rounded-full h-2 bg-muted">
                  <div
                    className="h-2 rounded-full bg-destructive"
                    style={{ width: `${Math.floor((exit.count / max_count) * 100)}%` }}
                  />
                </div>
                <span className="text-sm w-6 text-right shrink-0 text-muted-foreground">
                  {exit.count}
                </span>
              </div>
            ))}
          </div>
        </div>

        <h2 className="text-lg font-semibold mb-4">Par statut</h2>
        <div className="flex flex-col gap-3">
          {statuses.map((s) => {
            const count = stats.by_status[s] ?? 0;
            const pct = stats.total > 0 ? Math.min((count / stats.total) * 100, 100) : 0;
            return (
              <div className="flex items-center gap-3" key={s}>
                <span
                  className={`w-36 text-xs px-2 py-1 rounded-lg font-medium text-center ${statusColor(
                    s,
                  )}`}
                >
                  {s}
                </span>
                <div className="flex-1 rounded-full h-2 bg-muted">
                  {stats.total > 0 && (
                    <div
                      className="h-2 rounded-full bg-primary"
                      style={{ width: `${pct}%` }}
                    />
                  )}
                </div>
                <span className="text-sm w-6 text-right text-muted-foreground">
                  {count}
                </span>
              </div>
            );
          })}
        </div>

        <h2 className="text-lg font-semibold mt-8 mb-4">Dernier rapport</h2>
        <div className="rounded-xl p-5 mb-6 bg-card border border-border">
          {latest_report_html ? (
            <>
              <p className="text-xs mb-3 text-muted-foreground">
                Rapport du {latest_report_date}
              </p>
              <div
                className="prose-report text-sm leading-relaxed"
                dangerouslySetInnerHTML={{ __html: latest_report_html }}
              />
            </>
          ) : (
            <p className="text-sm text-muted-foreground">
              Aucun rapport disponible — lancez un scan pour en générer un.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
