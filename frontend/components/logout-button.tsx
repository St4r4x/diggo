"use client";

async function logout() {
  await fetch("/api/auth/session", { method: "DELETE" });
  window.location.href = "/login";
}

export function LogoutButton() {
  return (
    <button
      onClick={logout}
      className="text-xs px-3 py-1 rounded-md bg-card text-muted-foreground hover:text-foreground transition-colors"
    >
      Déconnexion
    </button>
  );
}
