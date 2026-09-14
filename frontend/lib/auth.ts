import { API_URL } from "./api";

export type AuthUser = {
  id: string;
  email: string;
  full_name: string;
  role: string;
  organization: { id: string; name: string; slug: string };
};

export async function getCurrentUser(): Promise<AuthUser | null> {
  const response = await fetch(`${API_URL}/auth/me`, { cache: "no-store", credentials: "include" });
  if (response.status === 401) return null;
  if (!response.ok) throw new Error("Authentication service is unavailable.");
  return response.json() as Promise<AuthUser>;
}

export async function authRequest(path: "/signin" | "/signup", payload: Record<string, string>): Promise<AuthUser> {
  const response = await fetch(`${API_URL}/auth${path}`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const body = await response.json().catch(() => null) as ({ error?: { message?: string } } & AuthUser) | null;
  if (!response.ok) throw new Error(body?.error?.message ?? `Authentication failed (${response.status})`);
  return body as AuthUser;
}

export async function signOut(): Promise<void> {
  const response = await fetch(`${API_URL}/auth/signout`, { method: "POST", credentials: "include" });
  if (!response.ok && response.status !== 401) throw new Error("Could not sign out.");
}
