export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

export type DependencyState = {
  status: "ready" | "unavailable";
  latency_ms?: number;
};

export type Readiness = {
  status: "ok" | "degraded" | "unavailable";
  service: string;
  details: { dependencies?: Record<string, DependencyState> };
};

export type ModelHealth = {
  status: "ready" | "unavailable" | "unknown";
  observed_at: string;
  latency_ms: number | null;
  details: Record<string, unknown>;
};

export type RegisteredModel = {
  id: string;
  name: string;
  provider: string;
  model_key: string;
  capabilities: string[];
  context_window: number | null;
  quantization: string | null;
  priority: number;
  enabled: boolean;
  latest_health: ModelHealth | null;
};

export async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    cache: "no-store",
    credentials: "include",
  });
  if (!response.ok) throw new Error(`Request failed (${response.status})`);
  return (await response.json()) as T;
}

export function formatContextWindow(value: number | null): string {
  if (value === null) return "Unknown";
  return value >= 1024 ? `${Math.round(value / 1024)}K` : String(value);
}

export function desiredIndexFileIds(
  files: Array<{ id: string; indexed: boolean }>,
  addedFileId: string,
): string[] {
  return Array.from(new Set([...files.filter((file) => file.indexed).map((file) => file.id), addedFileId]));
}
