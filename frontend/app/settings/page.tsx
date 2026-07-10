import { redirect } from "next/navigation";
import { DashboardNav } from "@/components/dashboard-nav";
import { SettingsClient } from "@/components/settings/settings-client";
import { getSessionUser } from "@/lib/session";

export default async function SettingsPage() {
  const user = await getSessionUser();
  if (!user) {
    redirect("/login");
  }

  return (
    <div className="flex flex-col h-screen">
      <DashboardNav email={user.email} activePath="/settings" />
      <div className="flex-1 min-h-0">
        <SettingsClient />
      </div>
    </div>
  );
}
