import { API_URL } from "@/lib/api";

export type View = "workbench" | "overview" | "models" | "knowledge" | "trace" | "security";
export type Workspace = { id: string; name: string; status: string };
export type StoredFile = { id: string; display_name: string; media_type: string; size_bytes: number; status: string; indexed: boolean };
export type KnowledgeBase = { id: string; workspace_id: string; name: string; status: string; active_index_version: number | null };
export type Job = { id: string; status: string; completed_documents: number; total_documents: number; error_message: string | null };
export type Hit = { score: number; text: string; citation: { display_name: string; page_start: number; page_end: number } };
export type InferenceResult = { model_id: string; model_name: string; provider: "ollama"; content: string; duration_ms: number; local: true };
export type TaskStatus = "queued" | "running" | "cancel_requested" | "completed" | "failed" | "cancelled" | "timed_out";
export type TaskStep = { id: string; sequence: number; kind: string; status: string; title: string; detail: string; tool_name: string | null; input: Record<string, unknown>; output: Record<string, unknown>; duration_ms: number | null; created_at: string; completed_at: string | null };
export type Artifact = { id: string; display_name: string; media_type: string; size_bytes: number; sha256: string; validation_status: string; download_url: string };
export type ArtifactPreview = { artifact_id: string; display_name: string; media_type: string; preview_type: "document" | "spreadsheet" | "text" | "binary"; content: string; truncated: boolean };
export type TaskCitation = { source_id: string; document_id: string; display_name: string; page_start: number; page_end: number; score: number; retrieval_mode: string; source_type: string; file_id?: string; knowledge_base_id?: string; knowledge_base_name?: string };
export type TaskRun = { id: string; attempt: number; status: TaskStatus; selected_model_id: string | null; agent_profile: string; route: { selected_model_key?: string; selection_reason?: string; candidates?: Array<Record<string, unknown>> }; step_count: number; retry_count: number; cancel_requested: boolean; result_text: string | null; citations: TaskCitation[]; error_category: string | null; error_message: string | null; created_at: string; started_at: string | null; completed_at: string | null; steps: TaskStep[]; artifacts: Artifact[] };
export type AgentTask = { id: string; workspace_id: string; goal: string; mode: "auto" | "document" | "coding" | "procurement"; test_command: "pytest" | "unittest" | "compile"; task_type: string; required_capabilities: string[]; input_file_ids: string[]; knowledge_base_ids: string[]; requested_outputs: string[]; status: TaskStatus; queue_position: number | null; created_at: string; updated_at: string; latest_run: TaskRun | null };
export type TaskAccepted = { task_id: string; run_id: string; status: TaskStatus; created_at: string };
export type AuditEvent = { id: string; run_id: string | null; event_type: string; actor_type: string; payload: Record<string, unknown>; occurred_at: string };
export type UserSession = { id: string; current: boolean; created_at: string; last_used_at: string; expires_at: string };
export type EgressTest = { status: "blocked" | "egress_detected" | "error"; target: string; duration_ms: number; detail: string; observed_at: string; enforcement: "configured" | "unconfigured"; probe_version: string };
export type SecurityControl = { key: string; label: string; status: "enforced" | "verified" | "attention" | "unknown"; detail: string };
export type SovereigntyMetrics = { task_runs: number; completed_runs: number; failed_runs: number; audit_events: number; artifacts: number; policy_denials: number; model_requests: number; prompt_tokens: number | null; completion_tokens: number | null; average_runtime_ms: number | null };
export type SecurityEvent = { id: string; event_type: string; status: string; detail: string; occurred_at: string; run_id: string | null };
export type SovereigntyStatus = { overall: "verified" | "attention" | "unknown"; generated_at: string; controls: SecurityControl[]; metrics: SovereigntyMetrics; enabled_models: number; ready_models: number; latest_egress_probe: EgressTest | null; recent_security_events: SecurityEvent[] };

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, { ...init, credentials: "include" });
  const body = await response.json().catch(() => null) as ({ error?: { message?: string } } & T) | null;
  if (!response.ok) throw new Error(body?.error?.message ?? `Request failed (${response.status})`);
  return body as T;
}

export function formatBytes(value: number) {
  if (value >= 1024 * 1024) return `${(value / 1024 / 1024).toFixed(1)} MB`;
  return `${Math.max(1, Math.ceil(value / 1024))} KB`;
}

export const isTaskActive = (status?: string) => ["queued", "running", "cancel_requested"].includes(status ?? "");

export function elapsedSeconds(start?: string | null, end?: string | null) {
  if (!start) return "—";
  return `${Math.max(0, (new Date(end ?? Date.now()).getTime() - new Date(start).getTime()) / 1000).toFixed(1)}s`;
}
