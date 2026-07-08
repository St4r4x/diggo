const STATUS_COLORS: Record<string, string> = {
  "À envoyer": "bg-gray-700 text-gray-200",
  Envoyée: "bg-blue-700 text-white",
  Relance: "bg-amber-600 text-white",
  "Entretien RH": "bg-violet-700 text-white",
  "Entretien tech": "bg-violet-900 text-white",
  Offre: "bg-emerald-700 text-white",
  Acceptée: "bg-emerald-700 text-white",
  Refusée: "bg-red-700 text-white",
  Abandonnée: "bg-red-900 text-white",
};

const GRADE_COLORS: Record<string, string> = {
  A: "bg-green-600 text-white",
  B: "bg-green-700 text-white",
  C: "bg-yellow-600 text-white",
  D: "bg-orange-600 text-white",
  F: "bg-red-700 text-white",
};

export function statusColor(status: string): string {
  return STATUS_COLORS[status] ?? "bg-gray-700 text-gray-200";
}

export function gradeColor(grade: string): string {
  return GRADE_COLORS[grade] ?? "bg-gray-700 text-gray-200";
}
