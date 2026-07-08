import { headers } from "next/headers";
import { redirect } from "next/navigation";
import { DashboardNav } from "@/components/dashboard-nav";
import { CandidaturesClient } from "@/components/candidatures/candidatures-client";

async function getSessionUser(): Promise<{ email: string } | null> {
  const headersList = await headers();
  const cookie = headersList.get("cookie") ?? "";
  const apiUrl = process.env.INTERNAL_API_URL ?? "http://api:8000";
  try {
    const res = await fetch(`${apiUrl}/api/me`, {
      headers: { cookie },
      cache: "no-store",
    });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export default async function CandidaturesPage() {
  const user = await getSessionUser();
  if (!user) {
    redirect("/login");
  }

  return (
    <div className="flex flex-col h-screen">
      <DashboardNav email={user.email} activePath="/candidatures" />
      <div className="flex-1 min-h-0">
        <CandidaturesClient />
      </div>
    </div>
  );
}
