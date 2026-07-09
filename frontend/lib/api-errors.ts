export function redirectOnUnauthenticated(res: Response): void {
  if (res.status === 401) {
    window.location.href = "/login";
    throw new Error("session expired");
  }
}
