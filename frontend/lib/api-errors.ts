export function redirectOnUnauthenticated(res: Response): void {
  if (res.status === 401) {
    window.location.href = "/login";
    throw new Error("session expired");
  }
}

export async function redirectOnOnboardingIncomplete(
  res: Response,
): Promise<void> {
  if (res.status === 403) {
    const body = await res.json();
    window.location.href = body.detail?.redirect ?? "/profile";
    throw new Error("onboarding incomplete");
  }
}
