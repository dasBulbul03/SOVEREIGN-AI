"use client";

import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, ArrowRight, CheckCircle2, CircleGauge, Cpu, Database, Files, Layers3, Plus } from "lucide-react";

import { formatContextWindow, getJson, type Readiness, type RegisteredModel } from "@/lib/api";
import { getCurrentUser } from "@/lib/auth";
import { request, type AgentTask } from "./types";
import { Badge, Flow, Head, Metric, Title } from "./ui";

export function Overview({ go, readiness, models }: { go: () => void; readiness?: Readiness; models: RegisteredModel[] }) {
  const dependencies = Object.entries(readiness?.details.dependencies ?? {});
  const ready = models.filter((model) => model.enabled && model.latest_health?.status === "ready").length;
  return <>
    <Title eyebrow="OPERATIONS OVERVIEW" title="Local control plane." copy="Live health from the current SOVEREIGN AI API and model registry." action={<button className="primary" onClick={go}><Plus size={15} /> Start new task</button>} />
    <div className="metrics"><Metric icon={CheckCircle2} value={readiness?.status === "ok" ? "Ready" : readiness?.status ?? "Checking"} label="API readiness" note={`${dependencies.filter(([, value]) => value.status === "ready").length}/${dependencies.length} dependencies ready`} /><Metric icon={CircleGauge} value={`${models.length}`} label="Registered models" note={`${ready} currently ready`} /><Metric icon={Cpu} value={`${ready}`} label="Local models ready" note="Observed via health checks" /><Metric icon={Database} value="0" label="Cloud providers" note="Local API configuration" /></div>
    <div className="overview">
      <section className="panel activity-card"><Head n="LIVE" label="DEPENDENCIES" title="Service readiness" action={<Badge tone={readiness?.status === "ok" ? "green" : "amber"}>{readiness?.status ?? "CHECKING"}</Badge>} /><div className="service-live">{dependencies.map(([name, state]) => <div key={name}><i className={`dot ${state.status === "ready" ? "" : "amber"}`} /><span><b>{name}</b><small>{state.latency_ms == null ? "No latency reported" : `${state.latency_ms} ms latency`}</small></span><strong>{state.status}</strong></div>)}{!dependencies.length && <p className="empty-copy">Waiting for backend readiness data…</p>}</div></section>
      <section className="panel health"><Head n="MODEL" label="HEALTH" title="Local infrastructure" action={<i className="dot" />} />{models.slice(0, 4).map((model) => <div className="health-row" key={model.id}><i><Cpu size={17} /></i><span><b>{model.name}</b><small>{model.provider} · {model.model_key}</small></span><strong>{model.enabled ? model.latest_health?.status ?? "unknown" : "disabled"}</strong></div>)}{!models.length && <p className="empty-copy">No models registered.</p>}</section>
    </div>
    <section className="panel recent"><Head n="CURRENT" label="REGISTRY" title="Configured local models" /><table><thead><tr><th>Model</th><th>Provider</th><th>Status</th><th>Context</th><th>Priority</th></tr></thead><tbody>{models.map((model) => <tr key={model.id}><td><b>{model.name}</b></td><td>{model.provider}</td><td><Badge tone={model.enabled && model.latest_health?.status === "ready" ? "green" : "neutral"}>{model.enabled ? model.latest_health?.status ?? "UNKNOWN" : "DISABLED"}</Badge></td><td>{formatContextWindow(model.context_window)}</td><td><code>{model.priority}</code></td></tr>)}</tbody></table></section>
  </>;
}

export function Models() {
  const client = useQueryClient();
  const [showRegistration, setShowRegistration] = useState(false);
  const [registrationError, setRegistrationError] = useState("");
  const [stateError, setStateError] = useState("");
  const user = useQuery({ queryKey: ["auth", "me"], queryFn: getCurrentUser, retry: false });
  const models = useQuery({ queryKey: ["models"], queryFn: () => getJson<RegisteredModel[]>("/models") });
  const tasks = useQuery({ queryKey: ["tasks", "router"], queryFn: () => request<AgentTask[]>("/tasks?limit=20") });
  const health = useMutation({ mutationFn: (id: string) => request<RegisteredModel>(`/models/${id}/health-check`, { method: "POST" }), onSuccess: () => client.invalidateQueries({ queryKey: ["models"] }) });
  const register = useMutation({
    mutationFn: (payload: Record<string, unknown>) => request<RegisteredModel>("/models", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }),
    onSuccess: async () => { await client.invalidateQueries({ queryKey: ["models"] }); setShowRegistration(false); setRegistrationError(""); },
    onError: (reason) => setRegistrationError(reason instanceof Error ? reason.message : "Registration failed."),
  });
  const state = useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) => request<RegisteredModel>(`/models/${id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ enabled }) }),
    onSuccess: async () => { setStateError(""); await client.invalidateQueries({ queryKey: ["models"] }); },
    onError: (reason) => setStateError(reason instanceof Error ? reason.message : "Model state update failed."),
  });
  const isOwner = user.data?.role === "owner";
  const ready = models.data?.filter((model) => model.enabled && model.latest_health?.status === "ready").length ?? 0;
  const routedTask = tasks.data?.find((task) => task.latest_run?.route?.selected_model_key);
  const route = routedTask?.latest_run?.route;
  const candidates = route?.candidates ?? [];

  function submitRegistration(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    register.mutate({
      name: String(data.get("name") ?? "").trim(),
      model_key: String(data.get("model_key") ?? "").trim(),
      capabilities: String(data.get("capabilities") ?? "text,reasoning").split(",").map((item) => item.trim()).filter(Boolean),
      context_window: Number(data.get("context_window")) || null,
      quantization: String(data.get("quantization") ?? "").trim() || null,
      priority: Number(data.get("priority")) || 50,
    });
  }
  return <>
    <Title eyebrow="LOCAL INFERENCE" title="Model Registry" copy="Capability-based routing across the models registered by the current backend. Disabled models remain registered but are excluded from new routing decisions." action={<button className="primary" disabled={!isOwner} title={isOwner ? undefined : "Only an organization owner can register models"} onClick={() => setShowRegistration((shown) => !shown)}><Plus size={15} /> {showRegistration ? "Close registration" : "Register model"}</button>} />
    {showRegistration && <form className="panel registry-form" onSubmit={submitRegistration}><label><span>Display name</span><input name="name" required minLength={2} placeholder="Qwen 3 4B" /></label><label><span>Ollama model key</span><input name="model_key" required minLength={2} placeholder="qwen3:4b" /></label><label><span>Capabilities</span><input name="capabilities" required defaultValue="text,reasoning,general" placeholder="text,reasoning,coding" /></label><label><span>Context window</span><input name="context_window" type="number" min="512" defaultValue="32768" /></label><label><span>Quantization</span><input name="quantization" placeholder="Q4_K_M" /></label><label><span>Priority</span><input name="priority" type="number" min="0" max="1000" defaultValue="50" /></label><button className="primary" disabled={register.isPending}>{register.isPending ? "Registering and checking…" : "Register local model"}</button>{registrationError && <div className="api-error" role="alert">{registrationError}</div>}</form>}
    <div className="summary"><span><b>{models.data?.length ?? 0}</b> registered models</span><span><b>{ready}</b> currently ready</span><span><b>{models.data?.filter((model) => model.enabled).length ?? 0}</b> enabled</span><span><b>0</b> cloud providers</span></div>
    {models.isError && <div className="api-error">Could not load the model registry.</div>}
    {stateError && <div className="api-error" role="alert">{stateError}</div>}
    <div className="model-grid">{models.data?.map((model, index) => <article className={model.enabled ? "panel model-card" : "panel model-card disabled"} key={model.id}><div className="model-top"><i className={["blue", "amber", "green", "neutral"][index % 4]}>{model.name.charAt(0)}</i><div><small>{model.capabilities.join(" + ") || "GENERAL"}</small><h2>{model.name}</h2></div><Badge tone={model.enabled && model.latest_health?.status === "ready" ? "green" : "neutral"}>{model.enabled ? model.latest_health?.status ?? "UNKNOWN" : "DISABLED"}</Badge></div><p>{model.model_key}</p><dl><div><dt>CONTEXT</dt><dd>{formatContextWindow(model.context_window)}</dd></div><div><dt>PRIORITY</dt><dd>{model.priority}</dd></div><div><dt>QUANTIZATION</dt><dd>{model.quantization ?? "—"}</dd></div><div><dt>PROVIDER</dt><dd>{model.provider}</dd></div></dl><footer><span><Activity size={13} /> {model.latest_health ? `Checked ${new Date(model.latest_health.observed_at).toLocaleTimeString()}` : "Not checked"}</span><div className="model-actions"><button disabled={!isOwner || state.isPending} title={isOwner ? `${model.enabled ? "Disable" : "Enable"} this model for new routing decisions` : "Only an organization owner can manage models"} onClick={() => state.mutate({ id: model.id, enabled: !model.enabled })}>{state.isPending ? "Updating…" : model.enabled ? "Disable" : "Enable"}</button><button disabled={!model.enabled || health.isPending} onClick={() => health.mutate(model.id)}>{health.isPending ? "Checking…" : "Check readiness"} <ArrowRight size={13} /></button></div></footer></article>)}</div>
    <section className="panel routing"><Head n="EXPLAINABLE" label="ROUTING" title="Latest task routing decision" action={<Badge tone="blue">{routedTask ? `TASK ${routedTask.id.slice(0, 8)}` : "NO ROUTED TASK"}</Badge>} />{routedTask && route ? <><div className="flow"><Flow icon={Files} title={routedTask.task_type.replaceAll("_", " ")} copy={routedTask.goal} /><ArrowRight /><Flow icon={Layers3} title="Required capabilities" copy={routedTask.required_capabilities.join(" + ")} /><ArrowRight /><Flow icon={CircleGauge} title={`${candidates.length} candidates evaluated`} copy={String(route.selection_reason ?? "Deterministic ordering")} /><ArrowRight /><Flow icon={Cpu} title="Selected model" copy={String(route.selected_model_key ?? "Unavailable")} active /></div><div className="route-candidates">{candidates.map((candidate, index) => <div key={String(candidate.model_id ?? index)}><code>{String(candidate.model_key ?? "unknown")}</code><span>priority {String(candidate.priority ?? "—")}</span><Badge tone={candidate.eligible ? "green" : "neutral"}>{candidate.eligible ? "ELIGIBLE" : candidate.health ? String(candidate.health).toUpperCase() : "CAPABILITY MISMATCH"}</Badge></div>)}</div></> : <p className="empty-copy">Run a task to see its persisted candidate evaluation and selected model. This panel does not infer a route from registry order.</p>}</section>
  </>;
}
