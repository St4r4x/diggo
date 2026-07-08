import { headers } from "next/headers";
import { redirect } from "next/navigation";
import { CandidaturesClient } from "@/components/candidatures/candidatures-client";

async function isAuthenticated(): Promise<boolean> {
  const headersList = await headers();
  const cookie = headersList.get("cookie") ?? "";
  const apiUrl = process.env.INTERNAL_API_URL ?? "http://api:8000";
  try {
    const res = await fetch(`${apiUrl}/api/me`, {
      headers: { cookie },
      cache: "no-store",
    });
    return res.ok;
  } catch {
    return false;
  }
}

export default async function CandidaturesPage() {
  if (!(await isAuthenticated())) {
    redirect("/login");
  }

  return <CandidaturesClient />;
}
