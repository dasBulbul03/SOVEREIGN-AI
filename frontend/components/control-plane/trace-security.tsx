"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { Activity, Braces, Check, CheckCircle2, Clock3, Cpu, Database, Download, FileCheck2, HardDrive, Network, ShieldAlert, ShieldCheck, TerminalSquare, XCircle } from "lucide-react";

import type { Readiness } from "@/lib/api";
import { elapsedSeconds, isTaskActive, request, type AgentTask, type AuditEvent, type EgressTest, type SovereigntyStatus } from "./types";
import { Badge, Head, Title } from "./ui";

function retrievalSources(value: unknown): Array<Record<string, unknown>> {
  return Array.isArray(value) ? value.filter((item): item is Record<string, unknown> => typeof item === "object" && item !== null) : [];
}

function timeLabel(value: string) {
  return new Date(value).toLocaleString([], { dateStyle: "medium", timeStyle: "medium" });
}

export function Trace({ requestedTaskId }: { requestedTaskId?: string }) {
  const router = useRouter();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const tasks = useQuery({ queryKey: ["tasks"], queryFn: () => request<AgentTask[]>("/tasks?limit=50"), refetchInterval: (query) => query.state.data?.some((task) => isTaskActive(task.status)) ? 1000 : 5000 });
  const selected = tasks.data?.find((task) => task.id === selectedId) ?? tasks.data?.find((task) => task.id === requestedTaskId) ?? tasks.data?.[0];
  const run = selected?.latest_run;
  const audits = useQuery({ queryKey: ["audits", run?.id], queryFn: () => request<AuditEvent[]>(`/audit-events?run_id=${run?.id}`), enabled: Boolean(run?.id), refetchInterval: isTaskActive(selected?.status) ? 1000 : false });
  const exportAudit = () => {
    const blob = new Blob([JSON.stringify({ task: selected, audit_events: audits.data ?? [] }, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `sovereign-audit-${run?.id ?? "empty"}.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  };
  return <>
    <Title eyebrow="COMPLETE AUDIT TRAIL" title="Execution Trace" copy="Inspect persisted classification, routing, tool use, inference, artifacts, and terminal state for every local task." action={<button className="secondary" onClick={exportAudit} disabled={!run}><Download size={15} /> Export audit JSON</button>} />
    {tasks.error instanceof Error && <div className="api-error" role="alert">{tasks.error.message}</div>}
    <div className="trace-layout"><aside className="run-list"><span className="eyebrow">PERSISTED RUNS</span>{tasks.isPending && <p className="empty-copy">Loading durable runs…</p>}{tasks.data?.map((task) => <button className={selected?.id === task.id ? "active" : ""} onClick={() => { setSelectedId(task.id); router.replace(`/trace?task=${task.id}`, { scroll: false }); }} key={task.id}><span><b>{task.goal}</b><small>{task.latest_run?.agent_profile.replaceAll("_", " ") || "classifying"} · {elapsedSeconds(task.latest_run?.started_at, task.latest_run?.completed_at)}</small></span>{task.status === "completed" ? <Check size={13} /> : task.status === "failed" ? <XCircle size={13} /> : <i className="dot amber" />}</button>)}{!tasks.isPending && !tasks.data?.length && <p className="empty-copy">No task runs yet. Start one in the Workbench.</p>}</aside><section className="panel trace-detail"><div className="trace-head"><div><Badge tone={selected?.status === "completed" ? "green" : isTaskActive(selected?.status) ? "amber" : "neutral"}>{selected?.status?.toUpperCase() ?? "NO RUN"}</Badge><h2>{selected?.goal ?? "No execution selected"}</h2><p>{run ? `Run ${run.id} · attempt ${run.attempt} · durable local record` : "Submit a Workbench task to create a trace"}</p></div><dl><div><dt>RUNTIME</dt><dd>{elapsedSeconds(run?.started_at, run?.completed_at)}</dd></div><div><dt>STEPS</dt><dd>{run?.steps.length ?? 0}</dd></div><div><dt>PROFILE</dt><dd>{run?.agent_profile?.replace("_agent", "") || "—"}</dd></div><div><dt>RETRIES</dt><dd>{run?.retry_count ?? 0}</dd></div></dl></div><div className="timeline">{run?.steps.map((step) => { const sources = retrievalSources(step.output.used_sources); return <div className="event" key={step.id}><time>STEP {String(step.sequence).padStart(2, "0")}</time><i>{step.status === "failed" ? <XCircle size={11} /> : <Check size={11} />}</i><div><span>{step.kind.toUpperCase()}{step.tool_name ? ` · ${step.tool_name}` : ""}</span><h3>{step.title}</h3><p>{step.detail}{step.duration_ms == null ? "" : ` · ${step.duration_ms} ms`}</p>{step.kind === "routing" && <code>{String(run.route.selection_reason ?? "deterministic capability route")} · model = {run.route.selected_model_key ?? "unavailable"}</code>}{sources.length > 0 && <div className="trace-sources">{sources.map((source, index) => <div key={String(source.source_id ?? index)}><b>{String(source.source_id ?? "SOURCE")} · {String(source.display_name ?? "Document")}</b><small>Page {String(source.page_start ?? 1)}{source.page_end !== source.page_start ? `–${String(source.page_end ?? 1)}` : ""} · {String(source.retrieval_mode ?? "retrieval").replaceAll("_", " ")}{source.knowledge_base_name ? ` · ${String(source.knowledge_base_name)}` : ""}</small></div>)}</div>}</div></div>; })}{run?.error_message && <div className="api-error" role="alert">{run.error_category}: {run.error_message}</div>}{!run?.steps.length && <p className="empty-copy">Execution events will appear here as the worker commits them.</p>}</div></section></div>
    <section className="panel audit-log"><Head n="AUDIT" label="APPEND-ONLY" title="Run security and provenance events" action={<Badge tone={audits.isError ? "amber" : "blue"}>{audits.data?.length ?? 0} EVENTS</Badge>} />{audits.isPending && run && <p className="empty-copy">Loading audit evidence…</p>}{audits.error instanceof Error && <div className="api-error" role="alert">{audits.error.message}</div>}<div className="audit-event-list">{audits.data?.map((event) => <article key={event.id}><i>{event.event_type.includes("DENIED") || event.event_type.includes("FAILED") ? <ShieldAlert size={15} /> : <Activity size={15} />}</i><div><b>{event.event_type.replaceAll("_", " ")}</b><small>{timeLabel(event.occurred_at)} · {event.actor_type}{event.run_id ? ` · run ${event.run_id.slice(0, 8)}` : ""}</small><code>{JSON.stringify(event.payload)}</code></div></article>)}{run && !audits.isPending && !audits.data?.length && <p className="empty-copy">No audit events were recorded for this run.</p>}</div></section>
  </>;
}

const controlIcons = {
  api_egress: Network,
  ollama_gateway: Cpu,
  sandbox_network: Braces,
  cloud_models: Database,
  egress_probe: ShieldCheck,
} as const;

export function Security({ readiness }: { readiness?: Readiness }) {
  const client = useQueryClient();
  const sovereignty = useQuery({ queryKey: ["sovereignty"], queryFn: () => request<SovereigntyStatus>("/security/status"), refetchInterval: 15_000 });
  const egress = useMutation({ mutationFn: () => request<EgressTest>("/security/egress-test", { method: "POST" }), onSuccess: async () => { await client.invalidateQueries({ queryKey: ["sovereignty"] }); } });
  const dependencies = Object.entries(readiness?.details.dependencies ?? {});
  const status = sovereignty.data;
  const probe = egress.data ?? status?.latest_egress_probe;
  const metrics = status?.metrics;
  const overallTone = status?.overall === "verified" ? "green" : status?.overall === "attention" ? "amber" : "neutral";
  const metricCards = [
    [Activity, metrics?.task_runs ?? 0, "Task runs", `${metrics?.completed_runs ?? 0} complete · ${metrics?.failed_runs ?? 0} failed`],
    [Cpu, metrics?.model_requests ?? 0, "Model calls", metrics?.prompt_tokens == null ? "Token telemetry unknown" : `${metrics.prompt_tokens} input · ${metrics.completion_tokens ?? 0} output tokens`],
    [Clock3, metrics?.average_runtime_ms == null ? "Unknown" : `${(metrics.average_runtime_ms / 1000).toFixed(1)}s`, "Average runtime", metrics?.average_runtime_ms == null ? "No terminal run telemetry" : "Last 100 terminal runs"],
    [FileCheck2, metrics?.artifacts ?? 0, "Validated artifacts", `${metrics?.audit_events ?? 0} audit events`],
    [ShieldAlert, metrics?.policy_denials ?? 0, "Policy denials", "Retained as security evidence"],
    [Cpu, `${status?.ready_models ?? 0}/${status?.enabled_models ?? 0}`, "Ready models", "Latest persisted health observations"],
  ] as const;
  return <>
    <Title eyebrow="ZERO-EGRESS ASSURANCE" title="Sovereignty Monitor" copy="Inspect enforced controls, observed probes, honest unknowns, runtime telemetry, and security-relevant audit evidence." action={<button className="primary" disabled={egress.isPending} onClick={() => egress.mutate()}><TerminalSquare size={15} /> {egress.isPending ? "Testing…" : "Run egress test"}</button>} />
    {probe && <div className={`egress-result ${probe.status}`} role="status"><b>{probe.status === "blocked" ? "Outbound connection blocked" : probe.status === "egress_detected" ? "Outbound connection detected" : "Probe inconclusive"}</b><span>{probe.detail} Target: {probe.target} · {probe.duration_ms} ms · {timeLabel(probe.observed_at)}</span></div>}
    {egress.error instanceof Error && <div className="api-error" role="alert">{egress.error.message}</div>}
    {sovereignty.error instanceof Error && <div className="api-error" role="alert">{sovereignty.error.message}</div>}
    <section className={`sovereign ${status?.overall ?? "unknown"}`}><div className="orbit"><ShieldCheck size={43} /></div><div><Badge tone={overallTone}><i className="dot" /> {status?.overall?.toUpperCase() ?? "CHECKING"}</Badge><h2>{status?.overall === "verified" ? "Application egress is blocked" : status?.overall === "attention" ? "Security attention required" : "Awaiting measured evidence"}</h2><p>{status ? `Evidence refreshed ${timeLabel(status.generated_at)}` : "Loading enforced and observed controls…"}</p></div><div><span>READY DEPENDENCIES</span><b>{dependencies.filter(([, state]) => state.status === "ready").length}</b><small>of {dependencies.length} reported services</small></div></section>
    <div className="security-grid">{status?.controls.map((control) => { const Icon = controlIcons[control.key as keyof typeof controlIcons] ?? HardDrive; return <article className={`panel control ${control.status}`} key={control.key}><i><Icon size={19} /></i><div><small>{control.label}</small><h3>{control.status.toUpperCase()}</h3><p>{control.detail}</p></div>{control.status === "attention" ? <ShieldAlert size={18} /> : control.status === "unknown" ? <Clock3 size={18} /> : <CheckCircle2 size={18} />}</article>; })}{sovereignty.isPending && <article className="panel control"><i><Clock3 size={19} /></i><div><small>Evidence</small><h3>LOADING</h3><p>Reading persisted sovereignty controls.</p></div></article>}</div>
    <div className="security-metrics">{metricCards.map(([Icon, value, label, copy]) => <article className="metric" key={label}><Icon size={17} /><b>{value}</b><span>{label}</span><small>{copy}</small></article>)}</div>
    <div className="proof"><section className="panel"><Head n="READINESS" label="LIVE" title="Dependency verification" action={<Badge tone={readiness?.status === "ok" ? "green" : "amber"}>API DATA</Badge>} /><div className="terminal">{dependencies.map(([name, state]) => <p key={name}><span>$</span> {name} <em>{state.status}{state.latency_ms == null ? "" : ` · ${state.latency_ms} ms`}</em></p>)}{!dependencies.length && <em>Waiting for backend readiness response…</em>}<b>{probe ? `Last controlled probe: ${probe.status.replace("_", " ")} (${probe.probe_version}).` : "Run the egress probe to record observed connectivity evidence."}</b></div></section><section className="panel policies"><Head n="SECURITY" label="RECENT" title="Security-relevant events" action={<Badge tone={status?.recent_security_events.length ? "amber" : "green"}>{status?.recent_security_events.length ?? 0}</Badge>} />{status?.recent_security_events.map((event) => <div key={event.id}><ShieldAlert size={13} /><span><b>{event.event_type.replaceAll("_", " ")}</b><small>{event.detail} · {timeLabel(event.occurred_at)}</small></span><Badge tone={event.event_type.includes("EGRESS") && event.status === "blocked" ? "green" : "amber"}>{event.status.toUpperCase()}</Badge></div>)}{status && !status.recent_security_events.length && <p className="empty-copy">No security exceptions have been recorded.</p>}</section></div>
  </>;
}
