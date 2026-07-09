import { redirect } from "next/navigation";
import { DashboardNav } from "@/components/dashboard-nav";
import { ProfileClient } from "@/components/profile/profile-client";
import { getSessionUser } from "@/lib/session";

export default async function ProfilePage() {
  const user = await getSessionUser();
  if (!user) {
    redirect("/login");
  }

  return (
    <div className="flex flex-col h-screen">
      <DashboardNav email={user.email} activePath="/profile" />
      <div className="flex-1 min-h-0">
        <ProfileClient />
      </div>
    </div>
  );
}
