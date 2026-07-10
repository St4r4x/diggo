"use client";

export function EditableSectionHeader({
  title,
  isEditing,
  showSuccess,
  errorMessage,
  onToggle,
  className = "mb-2",
}: {
  title: string;
  isEditing: boolean;
  showSuccess: boolean;
  errorMessage?: string;
  onToggle: () => void;
  className?: string;
}) {
  return (
    <>
      <div className={`flex items-center justify-between ${className}`}>
        <p className="text-sm font-semibold">{title}</p>
        <div className="flex items-center gap-2">
          {showSuccess && <span className="text-xs text-primary">✓ Enregistré</span>}
          <button
            type="button"
            onClick={onToggle}
            className="text-xs text-primary hover:underline"
          >
            {isEditing ? "Annuler" : "Modifier"}
          </button>
        </div>
      </div>
      {errorMessage && (
        <p className="text-xs text-destructive mb-2">{errorMessage}</p>
      )}
    </>
  );
}
