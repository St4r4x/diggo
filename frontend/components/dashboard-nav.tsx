import { LogoutButton } from "./logout-button";

type DashboardNavProps = {
  email: string;
  activePath: string;
};

const LINKS = [
  { href: "/candidatures", label: "Candidatures" },
  { href: "/stats", label: "Stats" },
  { href: "/profile", label: "Profil" },
  { href: "/settings", label: "Paramètres" },
];

export function DashboardNav({ email, activePath }: DashboardNavProps) {
  return (
    <nav className="flex items-center px-6 py-3 border-b border-border shrink-0">
      <span className="font-bold text-lg">Diggo</span>
      <div className="ml-8 flex items-center gap-6">
        {LINKS.map((link) => (
          <a
            key={link.href}
            href={link.href}
            className={
              link.href === activePath
                ? "text-primary font-semibold border-b border-primary pb-0.5 text-sm"
                : "text-muted-foreground hover:text-foreground text-sm transition-colors"
            }
          >
            {link.label}
          </a>
        ))}
      </div>
      <div className="ml-auto flex items-center gap-3">
        <span className="text-xs text-muted-foreground">{email}</span>
        <LogoutButton />
      </div>
    </nav>
  );
}
